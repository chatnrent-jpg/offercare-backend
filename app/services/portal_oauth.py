"""Google and Facebook OAuth for the clinician portal."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import settings
from app.models import ClinicianOAuthIdentity, ClinicianPortalAccount, MarylandProvider
from app.services.clinician_auth import create_portal_account
from app.services.demo_portal_accounts import ensure_demo_portal_accounts, ensure_demo_seed_clinician


@dataclass(frozen=True)
class OAuthProfile:
    provider: str
    subject: str
    email: str
    name: str | None = None


def normalize_absolute_url(url: str, *, fallback: str = "http://127.0.0.1:8000") -> str:
    """Ensure OAuth/callback bases always use a valid http(s):// prefix."""
    raw = str(url or "").strip().rstrip("/")
    if not raw:
        return fallback
    if raw.startswith("http:/") and not raw.startswith("http://"):
        raw = f"http://{raw[len('http:/'):].lstrip('/')}"
    elif raw.startswith("https:/") and not raw.startswith("https://"):
        raw = f"https://{raw[len('https:/'):].lstrip('/')}"
    elif not raw.startswith(("http://", "https://")):
        raw = f"http://{raw.lstrip('/')}"
    return raw.rstrip("/")


def oauth_redirect_base() -> str:
    configured = str(settings.PORTAL_OAUTH_REDIRECT_BASE or settings.PUBLIC_BASE_URL or "").strip()
    return normalize_absolute_url(configured)


def portal_home_url(*, query: str = "") -> str:
    suffix = f"?{query.lstrip('?')}" if query else ""
    return f"{oauth_redirect_base()}/portal/{suffix}"


def oauth_callback_url(provider: str) -> str:
    return f"{oauth_redirect_base()}/api/portal/auth/{provider}/callback"


def oauth_providers_enabled() -> dict[str, bool]:
    return {
        "google": bool(str(settings.GOOGLE_OAUTH_CLIENT_ID or "").strip()),
        "facebook": bool(str(settings.FACEBOOK_APP_ID or "").strip()),
    }


def create_oauth_state(oauth_provider: str) -> str:
    payload = {
        "provider": oauth_provider,
        "exp": int(time.time()) + 600,
        "nonce": secrets.token_urlsafe(12),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{signature}"


def verify_oauth_state(state: str, expected_provider: str) -> None:
    try:
        body, signature = state.rsplit(".", 1)
        expected = hmac.new(
            settings.JWT_SECRET_KEY.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad_oauth_state")
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if str(payload.get("provider")) != expected_provider:
            raise ValueError("oauth_provider_mismatch")
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("oauth_state_expired")
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_oauth_state") from exc


def google_authorize_url() -> str:
    client_id = str(settings.GOOGLE_OAUTH_CLIENT_ID or "").strip()
    if not client_id:
        raise ValueError("google_oauth_not_configured")
    params = {
        "client_id": client_id,
        "redirect_uri": oauth_callback_url("google"),
        "response_type": "code",
        "scope": "openid email profile",
        "state": create_oauth_state("google"),
        "prompt": "select_account",
    }
    query = httpx.QueryParams(params)
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def facebook_authorize_url() -> str:
    app_id = str(settings.FACEBOOK_APP_ID or "").strip()
    if not app_id:
        raise ValueError("facebook_oauth_not_configured")
    params = {
        "client_id": app_id,
        "redirect_uri": oauth_callback_url("facebook"),
        "state": create_oauth_state("facebook"),
        "scope": "email,public_profile",
    }
    query = httpx.QueryParams(params)
    return f"https://www.facebook.com/v19.0/dialog/oauth?{query}"


async def _exchange_google_code(code: str) -> OAuthProfile:
    client_id = str(settings.GOOGLE_OAUTH_CLIENT_ID or "").strip()
    client_secret = str(settings.GOOGLE_OAUTH_CLIENT_SECRET or "").strip()
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": oauth_callback_url("google"),
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise ValueError("google_token_missing")
        profile_resp = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile_resp.raise_for_status()
        data = profile_resp.json()
    email = str(data.get("email") or "").strip().lower()
    subject = str(data.get("sub") or "").strip()
    if not email or not subject:
        raise ValueError("google_profile_incomplete")
    return OAuthProfile(provider="google", subject=subject, email=email, name=data.get("name"))


async def _exchange_facebook_code(code: str) -> OAuthProfile:
    app_id = str(settings.FACEBOOK_APP_ID or "").strip()
    app_secret = str(settings.FACEBOOK_APP_SECRET or "").strip()
    redirect_uri = oauth_callback_url("facebook")
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise ValueError("facebook_token_missing")
        profile_resp = await client.get(
            "https://graph.facebook.com/me",
            params={"fields": "id,name,email", "access_token": access_token},
        )
        profile_resp.raise_for_status()
        data = profile_resp.json()
    email = str(data.get("email") or "").strip().lower()
    subject = str(data.get("id") or "").strip()
    if not subject:
        raise ValueError("facebook_profile_incomplete")
    if not email:
        raise ValueError("facebook_email_missing")
    return OAuthProfile(provider="facebook", subject=subject, email=email, name=data.get("name"))


async def exchange_oauth_code(provider: str, code: str) -> OAuthProfile:
    if provider == "google":
        return await _exchange_google_code(code)
    if provider == "facebook":
        return await _exchange_facebook_code(code)
    raise ValueError("unsupported_oauth_provider")


def _ensure_portal_account(db: Session, provider_id: UUID) -> None:
    account = (
        db.query(ClinicianPortalAccount)
        .filter(ClinicianPortalAccount.provider_id == provider_id)
        .first()
    )
    if account is None:
        create_portal_account(db, provider_id, secrets.token_urlsafe(32), commit=False)


def resolve_oauth_login(db: Session, profile: OAuthProfile) -> MarylandProvider:
    """Link OAuth identity to an existing clinician row by email."""
    email_norm = profile.email.strip().lower()
    identity = (
        db.query(ClinicianOAuthIdentity)
        .filter(
            ClinicianOAuthIdentity.oauth_provider == profile.provider,
            ClinicianOAuthIdentity.oauth_subject == profile.subject,
        )
        .first()
    )
    if identity is not None:
        clinician = (
            db.query(MarylandProvider)
            .filter(MarylandProvider.provider_id == identity.provider_id)
            .first()
        )
        if clinician is not None:
            identity.email = email_norm
            db.commit()
            return clinician

    clinician = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email.ilike(email_norm))
        .first()
    )
    if clinician is None and email_norm.endswith("@offercare.demo"):
        ensure_demo_seed_clinician(db, email_norm)
        ensure_demo_portal_accounts(db)
        clinician = (
            db.query(MarylandProvider)
            .filter(MarylandProvider.email.ilike(email_norm))
            .first()
        )
    if clinician is None:
        raise ValueError("oauth_account_not_found")

    _ensure_portal_account(db, clinician.provider_id)
    if identity is None:
        db.add(
            ClinicianOAuthIdentity(
                provider_id=clinician.provider_id,
                oauth_provider=profile.provider,
                oauth_subject=profile.subject,
                email=email_norm,
            )
        )
    db.commit()
    db.refresh(clinician)
    return clinician


def portal_oauth_login(db: Session, profile: OAuthProfile) -> tuple[MarylandProvider, str]:
    clinician = resolve_oauth_login(db, profile=profile)
    return clinician, create_access_token(clinician.provider_id)


def oauth_error_message(code: str) -> str:
    messages = {
        "oauth_account_not_found": "No VettedMe clinician account matches that email. Apply first, then link social sign-in.",
        "google_oauth_not_configured": "Google sign-in is not configured on this server.",
        "facebook_oauth_not_configured": "Facebook sign-in is not configured on this server.",
        "invalid_oauth_state": "Sign-in expired. Please try again.",
        "oauth_state_expired": "Sign-in expired. Please try again.",
        "google_profile_incomplete": "Google did not return an email address for this account.",
        "facebook_email_missing": "Facebook did not return an email. Allow email permission or use password sign-in.",
        "oauth_exchange_failed": "Social sign-in failed. Try again or use email/password.",
    }
    return messages.get(code, "Sign-in failed. Try again.")
