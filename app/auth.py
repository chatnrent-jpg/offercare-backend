"""Clinician portal token auth (stdlib — no extra JWT dependency)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import MarylandProvider

_bearer = HTTPBearer(auto_error=False)

PBKDF2_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations_raw, salt_hex, digest_hex = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_access_token(provider_id: UUID) -> str:
    payload = {
        "sub": str(provider_id),
        "exp": int(time.time()) + settings.JWT_EXPIRE_MINUTES * 60,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{signature}"


def decode_access_token(token: str) -> UUID:
    try:
        body, signature = token.rsplit(".", 1)
        expected = hmac.new(
            settings.JWT_SECRET_KEY.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad_signature")
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        return UUID(str(payload["sub"]))
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_token") from exc


def get_current_clinician(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> MarylandProvider:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="not_authenticated")
    try:
        provider_id = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid_token") from exc
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise HTTPException(status_code=401, detail="provider_not_found")
    return provider


def require_admin_api_key(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    configured = str(settings.ADMIN_API_KEY or "").strip()
    if not configured:
        return
    if not x_admin_key or not hmac.compare_digest(x_admin_key.strip(), configured):
        raise HTTPException(status_code=401, detail="admin_unauthorized")


def require_manus_api_key(
    x_manus_key: str | None = Header(default=None, alias="X-Manus-Key"),
) -> None:
    configured = str(settings.MANUS_API_KEY or "").strip()
    if not configured:
        raise HTTPException(status_code=503, detail="manus_not_configured")
    if not x_manus_key or not hmac.compare_digest(x_manus_key.strip(), configured):
        raise HTTPException(status_code=401, detail="manus_unauthorized")
