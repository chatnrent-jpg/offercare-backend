"""Skyflow Vault PII tokenization — SSN, DOB, and Stripe routing tokens for caregiver onboarding."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DRY_VAULT_PATH = REPO_ROOT / "logs" / "skyflow_dry_vault.json"
DEFAULT_VAULT_TABLE = "caregivers"

_SSN_DIGITS = re.compile(r"\D")
_STRIPE_TOKEN = re.compile(r"^(tok|ba|rt|acct)_[A-Za-z0-9]+$")


@dataclass(frozen=True)
class CaregiverPiiPayload:
    ssn: str | None = None
    date_of_birth: str | None = None
    stripe_routing_token: str | None = None


@dataclass(frozen=True)
class CaregiverPiiTokens:
    ssn_token: str | None = None
    dob_token: str | None = None
    stripe_routing_token: str | None = None
    vault_record_id: str | None = None
    tokenization_mode: str = "dry_run"


@dataclass
class CaregiverPiiCleartext:
    ssn: str | None = None
    date_of_birth: str | None = None
    stripe_routing_token: str | None = None
    detokenization_mode: str = "dry_run"


def _vault_table() -> str:
    return str(getattr(settings, "SKYFLOW_VAULT_TABLE", "") or DEFAULT_VAULT_TABLE).strip()


def _dry_vault_path() -> Path:
    configured = str(getattr(settings, "SKYFLOW_DRY_VAULT_PATH", "") or "").strip()
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else REPO_ROOT / path
    return DEFAULT_DRY_VAULT_PATH


def _skyflow_base_url() -> str:
    return str(getattr(settings, "SKYFLOW_VAULT_URL", "") or "").strip().rstrip("/")


def _skyflow_bearer_token() -> str:
    return str(
        getattr(settings, "SKYFLOW_BEARER_TOKEN", "")
        or os.environ.get("SKYFLOW_BEARER_TOKEN")
        or ""
    ).strip()


def _normalize_ssn(raw: str | None) -> str | None:
    if raw is None:
        return None
    digits = _SSN_DIGITS.sub("", str(raw))
    if not digits:
        return None
    if len(digits) != 9:
        raise ValueError("invalid_ssn")
    return digits


def _normalize_dob(raw: str | None) -> str | None:
    if raw is None:
        return None
    token = str(raw).strip()
    if not token:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        date.fromisoformat(token)
        return token
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(token, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError("invalid_date_of_birth")


def _normalize_stripe_routing_token(raw: str | None) -> str | None:
    if raw is None:
        return None
    token = str(raw).strip()
    if not token:
        return None
    if not _STRIPE_TOKEN.match(token):
        raise ValueError("invalid_stripe_routing_token")
    return token


def _payload_from_dict(payload: dict[str, Any] | CaregiverPiiPayload) -> CaregiverPiiPayload:
    if isinstance(payload, CaregiverPiiPayload):
        return payload
    return CaregiverPiiPayload(
        ssn=payload.get("ssn"),
        date_of_birth=payload.get("date_of_birth") or payload.get("dob"),
        stripe_routing_token=payload.get("stripe_routing_token"),
    )


def _normalized_fields(payload: CaregiverPiiPayload) -> dict[str, str]:
    fields: dict[str, str] = {}
    ssn = _normalize_ssn(payload.ssn)
    dob = _normalize_dob(payload.date_of_birth)
    stripe = _normalize_stripe_routing_token(payload.stripe_routing_token)
    if ssn:
        fields["ssn"] = ssn
    if dob:
        fields["date_of_birth"] = dob
    if stripe:
        fields["stripe_routing_token"] = stripe
    return fields


def _deterministic_token(field_name: str, value: str) -> str:
    digest = hashlib.sha256(f"{field_name}:{value}".encode("utf-8")).hexdigest()
    return f"skyflow_dry_{field_name}_{digest[:24]}"


def _load_dry_vault() -> dict[str, str]:
    path = _dry_vault_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("skyflow: corrupt dry vault at %s — resetting", path)
        return {}


def _save_dry_vault(mapping: dict[str, str]) -> None:
    path = _dry_vault_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")


def _tokenize_dry_run(fields: dict[str, str]) -> CaregiverPiiTokens:
    vault = _load_dry_vault()
    tokens: dict[str, str] = {}
    for field_name, value in fields.items():
        token = _deterministic_token(field_name, value)
        vault[token] = value
        tokens[field_name] = token
    _save_dry_vault(vault)
    record_id = f"dry_rec_{uuid.uuid4().hex[:16]}"
    return CaregiverPiiTokens(
        ssn_token=tokens.get("ssn"),
        dob_token=tokens.get("date_of_birth"),
        stripe_routing_token=tokens.get("stripe_routing_token"),
        vault_record_id=record_id,
        tokenization_mode="dry_run",
    )


def _invoke_skyflow_insert(fields: dict[str, str]) -> CaregiverPiiTokens:
    base_url = _skyflow_base_url()
    vault_id = str(getattr(settings, "SKYFLOW_VAULT_ID", "") or "").strip()
    bearer = _skyflow_bearer_token()
    if not base_url or not vault_id or not bearer:
        raise RuntimeError("skyflow_vault_not_configured")

    table = _vault_table()
    timeout = float(getattr(settings, "SKYFLOW_VAULT_TIMEOUT_SECONDS", 30.0))
    url = f"{base_url}/v1/vaults/{vault_id}/{table}"

    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {bearer}",
                "Content-Type": "application/json",
            },
            json={
                "quorum": False,
                "tokenization": True,
                "records": [{"fields": fields}],
            },
        )
        response.raise_for_status()
        payload = response.json()

    records = payload.get("records") or []
    if not records:
        raise RuntimeError("skyflow_insert_empty_response")

    record = records[0] if isinstance(records[0], dict) else {}
    record_fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    tokens_block = record.get("tokens") if isinstance(record.get("tokens"), dict) else {}

    def _field_token(name: str) -> str | None:
        token = tokens_block.get(name) or record_fields.get(name)
        return str(token).strip() if token else None

    vault_record_id = str(record.get("skyflow_id") or record.get("id") or "").strip() or None
    return CaregiverPiiTokens(
        ssn_token=_field_token("ssn"),
        dob_token=_field_token("date_of_birth"),
        stripe_routing_token=_field_token("stripe_routing_token"),
        vault_record_id=vault_record_id,
        tokenization_mode="skyflow_live",
    )


def _invoke_skyflow_detokenize(tokens: dict[str, str | None]) -> dict[str, str]:
    base_url = _skyflow_base_url()
    vault_id = str(getattr(settings, "SKYFLOW_VAULT_ID", "") or "").strip()
    bearer = _skyflow_bearer_token()
    if not base_url or not vault_id or not bearer:
        raise RuntimeError("skyflow_vault_not_configured")

    table = _vault_table()
    timeout = float(getattr(settings, "SKYFLOW_VAULT_TIMEOUT_SECONDS", 30.0))
    url = f"{base_url}/v1/vaults/{vault_id}/{table}/detokenize"

    parameters = [
        {"token": token, "redaction": "PLAIN_TEXT"}
        for token in tokens.values()
        if token
    ]
    if not parameters:
        return {}

    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {bearer}",
                "Content-Type": "application/json",
            },
            json={"detokenizationParameters": parameters},
        )
        response.raise_for_status()
        payload = response.json()

    resolved: dict[str, str] = {}
    records = payload.get("records") or payload.get("responses") or []
    token_list = [token for token in tokens.values() if token]
    if isinstance(records, list):
        for index, item in enumerate(records):
            if not isinstance(item, dict):
                continue
            value = item.get("value") or item.get("plainText") or item.get("plain_text")
            if value is None:
                continue
            if index < len(token_list):
                resolved[token_list[index]] = str(value)
    return resolved


def tokenize_caregiver_pii(payload: dict[str, Any] | CaregiverPiiPayload) -> CaregiverPiiTokens:
    """Intercept inbound onboarding PII and return Skyflow vault tokens (never persist cleartext)."""
    if not getattr(settings, "SKYFLOW_VAULT_ENABLED", True):
        raise RuntimeError("skyflow_vault_disabled")

    normalized = _normalized_fields(_payload_from_dict(payload))
    if not normalized:
        raise ValueError("caregiver_pii_empty")

    dry_run = bool(getattr(settings, "SKYFLOW_VAULT_DRY_RUN", True))
    if dry_run:
        return _tokenize_dry_run(normalized)
    return _invoke_skyflow_insert(normalized)


def detokenize_caregiver_pii(
    tokens: dict[str, Any] | CaregiverPiiTokens,
) -> CaregiverPiiCleartext:
    """Resolve Skyflow tokens back to cleartext for authorized payroll/payout flows."""
    if isinstance(tokens, CaregiverPiiTokens):
        token_map = {
            "ssn": tokens.ssn_token,
            "date_of_birth": tokens.dob_token,
            "stripe_routing_token": tokens.stripe_routing_token,
        }
    else:
        token_map = {
            "ssn": tokens.get("ssn_token") or tokens.get("skyflow_ssn_token"),
            "date_of_birth": tokens.get("dob_token") or tokens.get("skyflow_dob_token"),
            "stripe_routing_token": tokens.get("stripe_routing_token")
            or tokens.get("skyflow_stripe_routing_token"),
        }

    active = {key: str(value).strip() for key, value in token_map.items() if value}
    if not active:
        raise ValueError("caregiver_pii_tokens_empty")

    dry_run = bool(getattr(settings, "SKYFLOW_VAULT_DRY_RUN", True))
    if dry_run:
        vault = _load_dry_vault()
        return CaregiverPiiCleartext(
            ssn=vault.get(active["ssn"]) if "ssn" in active else None,
            date_of_birth=vault.get(active["date_of_birth"]) if "date_of_birth" in active else None,
            stripe_routing_token=(
                vault.get(active["stripe_routing_token"]) if "stripe_routing_token" in active else None
            ),
            detokenization_mode="dry_run",
        )

    resolved = _invoke_skyflow_detokenize(active)
    reverse = {token: field for field, token in active.items()}
    cleartext: dict[str, str | None] = {
        "ssn": None,
        "date_of_birth": None,
        "stripe_routing_token": None,
    }
    for token, value in resolved.items():
        field_name = reverse.get(token)
        if field_name:
            cleartext[field_name] = value
    return CaregiverPiiCleartext(
        ssn=cleartext.get("ssn"),
        date_of_birth=cleartext.get("date_of_birth"),
        stripe_routing_token=cleartext.get("stripe_routing_token"),
        detokenization_mode="skyflow_live",
    )


def strip_cleartext_pii_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove raw PII keys from an onboarding payload after tokenization."""
    sanitized = dict(payload)
    for key in ("ssn", "social_security_number", "date_of_birth", "dob", "stripe_routing_token"):
        sanitized.pop(key, None)
    return sanitized


def tokens_to_profile_fields(tokens: CaregiverPiiTokens) -> dict[str, str | None]:
    """Map tokenization output to caregiver profile column kwargs."""
    return {
        "skyflow_vault_record_id": tokens.vault_record_id,
        "skyflow_ssn_token": tokens.ssn_token,
        "skyflow_dob_token": tokens.dob_token,
    }


def tokens_to_w2_fields(tokens: CaregiverPiiTokens) -> dict[str, str | None]:
    return {"skyflow_stripe_routing_token": tokens.stripe_routing_token}
