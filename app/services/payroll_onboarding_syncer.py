"""Payroll onboarding sync — Gusto Embedded / Check HQ employee create after MBON clearance."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    EMPLOYMENT_TIER_W2,
    CaregiverProfile,
    CaregiverW2EmployeeAccount,
    LicenseVerificationLog,
    MarylandProvider,
)
from app.services.caregiver_accounts import get_w2_employee_account
from app.services.mbon_verification import MbonVerificationResult
from app.services.payroll_tax_intercept_bridge import _resolve_payroll_provider

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PAYROLL_DOCS = _REPO_ROOT / "docs" / "payroll"

PAYROLL_ONBOARDING_SYNCED = "SYNCED"
PAYROLL_ONBOARDING_DRY_RUN = "DRY_RUN"
PAYROLL_ONBOARDING_SKIPPED = "SKIPPED"
PAYROLL_ONBOARDING_VALIDATION_ERROR = "VALIDATION_ERROR"
PAYROLL_ONBOARDING_TRANSPORT_ERROR = "TRANSPORT_ERROR"
PAYROLL_ONBOARDING_NOT_W2 = "NOT_W2"
PAYROLL_ONBOARDING_ALREADY_SYNCED = "ALREADY_SYNCED"

FALLBACK_MANUAL_REVIEW = "QUEUE_MANUAL_PAYROLL_REVIEW"
FALLBACK_RETRY = "RETRY_PAYROLL_ONBOARDING"
FALLBACK_LOCAL_STUB = "LOCAL_PAYROLL_STUB"

GUSTO_CREATE_EMPLOYEE = {
    "provider": "gusto",
    "method": "POST",
    "path": "/v1/employees",
    "doc_file": "gusto/llms-index.txt (post-v1-employees.md)",
    "scope": "employees:manage",
}
CHECKHQ_CREATE_EMPLOYEE = {
    "provider": "checkhq",
    "method": "POST",
    "path": "/employees",
    "doc_file": "checkhq/checkhq-workplaces.md",
}


@dataclass(frozen=True)
class PayrollEmployeeEndpointConfig:
    provider: str
    method: str
    path: str
    base_url: str
    doc_file: str
    auth_header: str
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class PayrollOnboardingSyncResult:
    status: str
    payroll_provider: str
    gusto_employee_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    fallback_action: str | None = None
    endpoint: str | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = str(full_name or "").strip().split()
    if not parts:
        return "Caregiver", "Unknown"
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def is_mbon_realtime_clear(mbon: MbonVerificationResult) -> bool:
    """True when live MBON API returned ACTIVE (dry-run counts when enabled)."""
    if str(mbon.status or "").upper() != "ACTIVE":
        return False
    source = str(mbon.source or "").upper()
    if source == "MBON_API":
        return True
    if source == "MBON_DRY_RUN" and bool(getattr(settings, "PAYROLL_ONBOARDING_DRY_RUN", True)):
        return True
    return False


def resolve_payroll_employee_endpoint(provider: str | None = None) -> PayrollEmployeeEndpointConfig:
    selected = str(provider or _resolve_payroll_provider() or "local").strip().lower()
    if selected == "checkhq":
        return PayrollEmployeeEndpointConfig(
            provider="checkhq",
            method=CHECKHQ_CREATE_EMPLOYEE["method"],
            path=CHECKHQ_CREATE_EMPLOYEE["path"],
            base_url=str(settings.CHECKHQ_API_BASE or "https://sandbox.checkhq.com").rstrip("/"),
            doc_file=CHECKHQ_CREATE_EMPLOYEE["doc_file"],
            auth_header=f"Bearer {str(settings.CHECKHQ_API_KEY or '').strip()}",
        )
    return PayrollEmployeeEndpointConfig(
        provider="gusto",
        method=GUSTO_CREATE_EMPLOYEE["method"],
        path=GUSTO_CREATE_EMPLOYEE["path"],
        base_url=str(settings.GUSTO_API_BASE or "https://api.gusto-demo.com").rstrip("/"),
        doc_file=GUSTO_CREATE_EMPLOYEE["doc_file"],
        auth_header=f"Bearer {str(settings.GUSTO_API_TOKEN or '').strip()}",
        extra_headers={"X-Gusto-API-Version": str(settings.GUSTO_API_VERSION or "2024-04-01")},
    )


def _resolve_w2_bundle(
    db: Session,
    provider: MarylandProvider,
) -> tuple[CaregiverProfile, CaregiverW2EmployeeAccount] | None:
    profile = (
        db.query(CaregiverProfile)
        .filter(CaregiverProfile.provider_id == provider.provider_id)
        .filter(CaregiverProfile.employment_tier == EMPLOYMENT_TIER_W2)
        .first()
    )
    if profile is None:
        return None
    w2 = get_w2_employee_account(db, profile.caregiver_profile_id)
    if w2 is None:
        return None
    return profile, w2


def build_gusto_employee_payload(
    provider: MarylandProvider,
    profile: CaregiverProfile,
    w2_account: CaregiverW2EmployeeAccount,
) -> dict[str, Any]:
    first_name, last_name = _split_full_name(profile.full_name or provider.full_name)
    company_uuid = str(settings.GUSTO_COMPANY_ID or "").strip()
    if not company_uuid:
        raise ValueError("gusto_company_id_missing")

    payload: dict[str, Any] = {
        "company_uuid": company_uuid,
        "first_name": first_name,
        "last_name": last_name,
        "email": str(profile.email or provider.email or "").strip().lower(),
        "work_email": str(profile.email or provider.email or "").strip().lower(),
        "phone": str(profile.phone_number or provider.phone_number or "").strip(),
        "metadata": {
            "vettedme_provider_id": str(provider.provider_id),
            "mbon_license_number": profile.mbon_license_number,
            "credential_type": profile.credential_type,
            "maryland_residence_county": w2_account.maryland_residence_county,
        },
    }
    if provider.home_zip:
        payload["home_address"] = {
            "street_1": "On file with VettedMe",
            "city": "Baltimore",
            "state": "MD",
            "zip": str(provider.home_zip).strip()[:10],
        }
    return payload


def build_checkhq_employee_payload(
    provider: MarylandProvider,
    profile: CaregiverProfile,
    w2_account: CaregiverW2EmployeeAccount,
) -> dict[str, Any]:
    first_name, last_name = _split_full_name(profile.full_name or provider.full_name)
    company_id = str(getattr(settings, "CHECKHQ_COMPANY_ID", "") or "").strip()
    workplace_id = str(getattr(settings, "CHECKHQ_DEFAULT_WORKPLACE_ID", "") or "").strip()
    if not company_id:
        raise ValueError("checkhq_company_id_missing")
    if not workplace_id:
        raise ValueError("checkhq_workplace_id_missing")

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": str(profile.email or provider.email or "").strip().lower(),
        "company": company_id,
        "workplaces": [workplace_id],
        "primary_workplace": workplace_id,
        "metadata": {
            "vettedme_provider_id": str(provider.provider_id),
            "mbon_license_number": profile.mbon_license_number,
            "maryland_residence_county": w2_account.maryland_residence_county,
        },
    }


def build_payroll_employee_payload(
    provider: MarylandProvider,
    profile: CaregiverProfile,
    w2_account: CaregiverW2EmployeeAccount,
    *,
    payroll_provider: str | None = None,
) -> dict[str, Any]:
    selected = str(payroll_provider or _resolve_payroll_provider() or "gusto").strip().lower()
    if selected == "checkhq":
        return build_checkhq_employee_payload(provider, profile, w2_account)
    return build_gusto_employee_payload(provider, profile, w2_account)


def _parse_payroll_validation_errors(response: httpx.Response) -> list[dict[str, Any]]:
    try:
        body = response.json()
    except json.JSONDecodeError:
        return [{"message": response.text[:500]}]
    if isinstance(body, dict):
        errors = body.get("errors") or body.get("error") or body.get("details")
        if isinstance(errors, list):
            return [item if isinstance(item, dict) else {"message": str(item)} for item in errors]
        if isinstance(errors, dict):
            return [{"field": key, "message": str(value)} for key, value in errors.items()]
        message = body.get("message") or body.get("detail")
        if message:
            return [{"message": str(message)}]
    return [{"message": response.text[:500]}]


def _extract_employee_id(provider: str, payload: dict[str, Any]) -> str | None:
    if provider == "checkhq":
        token = payload.get("id") or payload.get("employee_id")
        return str(token).strip() if token else None
    token = payload.get("uuid") or payload.get("employee_uuid") or payload.get("id")
    return str(token).strip() if token else None


def _deterministic_dry_run_employee_id(provider: MarylandProvider) -> str:
    digest = re.sub(r"[^a-f0-9]", "", str(provider.provider_id).replace("-", ""))[:12]
    return f"dry_gusto_emp_{digest}"


def execute_payroll_employee_create(
    payload: dict[str, Any],
    *,
    payroll_provider: str | None = None,
) -> tuple[dict[str, Any], PayrollEmployeeEndpointConfig]:
    endpoint = resolve_payroll_employee_endpoint(payroll_provider)
    url = f"{endpoint.base_url}{endpoint.path}"
    headers = {"Content-Type": "application/json", "Authorization": endpoint.auth_header}
    headers.update(endpoint.extra_headers)

    if bool(getattr(settings, "PAYROLL_ONBOARDING_DRY_RUN", True)):
        employee_id = _deterministic_dry_run_employee_id_from_payload(payload)
        return (
            {
                "uuid": employee_id,
                "id": employee_id,
                "dry_run": True,
                "provider": endpoint.provider,
            },
            endpoint,
        )

    if endpoint.provider == "gusto" and not str(settings.GUSTO_API_TOKEN or "").strip():
        raise RuntimeError("gusto_api_token_missing")
    if endpoint.provider == "checkhq" and not str(settings.CHECKHQ_API_KEY or "").strip():
        raise RuntimeError("checkhq_api_key_missing")

    timeout = float(getattr(settings, "PAYROLL_ONBOARDING_TIMEOUT_SECONDS", 30.0))
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
        if response.status_code in {400, 422}:
            errors = _parse_payroll_validation_errors(response)
            raise PayrollValidationError(errors, status_code=response.status_code, endpoint=url)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("payroll_employee_create_invalid_response")
        return body, endpoint


def _deterministic_dry_run_employee_id_from_payload(payload: dict[str, Any]) -> str:
    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    provider_id = str(meta.get("vettedme_provider_id") or "unknown")
    digest = re.sub(r"[^a-f0-9]", "", provider_id.replace("-", ""))[:12]
    return f"dry_gusto_emp_{digest}"


class PayrollValidationError(Exception):
    def __init__(
        self,
        errors: list[dict[str, Any]],
        *,
        status_code: int = 422,
        endpoint: str | None = None,
    ) -> None:
        super().__init__("payroll_validation_error")
        self.errors = errors
        self.status_code = status_code
        self.endpoint = endpoint


def _record_payroll_onboarding_audit(
    db: Session,
    *,
    provider_id: UUID,
    result: PayrollOnboardingSyncResult,
) -> None:
    db.add(
        LicenseVerificationLog(
            provider_id=provider_id,
            event_type="PAYROLL_ONBOARDING_SYNC",
            check_result=result.status,
            notes=json.dumps(result.to_dict(), default=str)[:500],
            reviewer="payroll_onboarding_syncer",
        )
    )


def _apply_sync_result_to_w2_account(
    w2_account: CaregiverW2EmployeeAccount,
    result: PayrollOnboardingSyncResult,
) -> None:
    if result.gusto_employee_id:
        w2_account.gusto_employee_id = result.gusto_employee_id
        if not w2_account.employee_payroll_number:
            w2_account.employee_payroll_number = result.gusto_employee_id
    if result.status == PAYROLL_ONBOARDING_SYNCED:
        w2_account.payroll_withholding_status = "PAYROLL_EMPLOYEE_CREATED"
    elif result.status == PAYROLL_ONBOARDING_DRY_RUN:
        w2_account.payroll_withholding_status = "PAYROLL_DRY_RUN"
    elif result.status == PAYROLL_ONBOARDING_VALIDATION_ERROR:
        w2_account.payroll_withholding_status = "PAYROLL_VALIDATION_ERROR"
    elif result.status == PAYROLL_ONBOARDING_TRANSPORT_ERROR:
        w2_account.payroll_withholding_status = "PAYROLL_SYNC_RETRY"
    if result.error_message:
        w2_account.payroll_onboarding_error = result.error_message[:2000]


def sync_payroll_onboarding_after_mbon_clear(
    db: Session,
    provider: MarylandProvider,
    *,
    mbon_result: MbonVerificationResult,
    commit: bool = True,
) -> PayrollOnboardingSyncResult:
    """Hook listener — create Gusto/Check HQ employee when MBON realtime validation clears."""
    if not getattr(settings, "PAYROLL_ONBOARDING_SYNC_ENABLED", True):
        return PayrollOnboardingSyncResult(
            status=PAYROLL_ONBOARDING_SKIPPED,
            payroll_provider=_resolve_payroll_provider(),
            error_code="payroll_onboarding_disabled",
            fallback_action=FALLBACK_LOCAL_STUB,
        )

    if not is_mbon_realtime_clear(mbon_result):
        return PayrollOnboardingSyncResult(
            status=PAYROLL_ONBOARDING_SKIPPED,
            payroll_provider=_resolve_payroll_provider(),
            error_code="mbon_not_cleared",
            error_message=f"MBON status={mbon_result.status} source={mbon_result.source}",
            fallback_action=FALLBACK_RETRY,
        )

    bundle = _resolve_w2_bundle(db, provider)
    if bundle is None:
        return PayrollOnboardingSyncResult(
            status=PAYROLL_ONBOARDING_NOT_W2,
            payroll_provider=_resolve_payroll_provider(),
            error_code="tier1_w2_account_missing",
            fallback_action=FALLBACK_MANUAL_REVIEW,
        )

    profile, w2_account = bundle
    if str(w2_account.gusto_employee_id or "").strip():
        return PayrollOnboardingSyncResult(
            status=PAYROLL_ONBOARDING_ALREADY_SYNCED,
            payroll_provider=_resolve_payroll_provider(),
            gusto_employee_id=str(w2_account.gusto_employee_id),
        )

    payroll_provider = _resolve_payroll_provider()
    if payroll_provider == "local":
        employee_id = _deterministic_dry_run_employee_id(provider)
        result = PayrollOnboardingSyncResult(
            status=PAYROLL_ONBOARDING_DRY_RUN,
            payroll_provider="local",
            gusto_employee_id=employee_id,
            dry_run=True,
            fallback_action=FALLBACK_LOCAL_STUB,
            endpoint="local://payroll/employees",
        )
        _apply_sync_result_to_w2_account(w2_account, result)
        _record_payroll_onboarding_audit(db, provider_id=provider.provider_id, result=result)
        if commit:
            db.commit()
        return result

    try:
        payload = build_payroll_employee_payload(provider, profile, w2_account, payroll_provider=payroll_provider)
        response_body, endpoint = execute_payroll_employee_create(payload, payroll_provider=payroll_provider)
        employee_id = _extract_employee_id(endpoint.provider, response_body)
        if not employee_id:
            raise RuntimeError("payroll_employee_id_missing")

        dry_run = bool(response_body.get("dry_run"))
        result = PayrollOnboardingSyncResult(
            status=PAYROLL_ONBOARDING_DRY_RUN if dry_run else PAYROLL_ONBOARDING_SYNCED,
            payroll_provider=endpoint.provider,
            gusto_employee_id=employee_id,
            dry_run=dry_run,
            endpoint=f"{endpoint.base_url}{endpoint.path}",
        )
    except PayrollValidationError as exc:
        logger.warning(
            "payroll onboarding validation error provider=%s errors=%s",
            provider.provider_id,
            exc.errors,
        )
        result = PayrollOnboardingSyncResult(
            status=PAYROLL_ONBOARDING_VALIDATION_ERROR,
            payroll_provider=payroll_provider,
            error_code="payroll_validation_error",
            error_message="; ".join(
                str(item.get("message") or item) for item in exc.errors[:5]
            )[:500],
            validation_errors=exc.errors,
            fallback_action=FALLBACK_MANUAL_REVIEW,
            endpoint=exc.endpoint,
        )
    except httpx.HTTPError as exc:
        logger.warning("payroll onboarding transport error provider=%s error=%s", provider.provider_id, exc)
        result = PayrollOnboardingSyncResult(
            status=PAYROLL_ONBOARDING_TRANSPORT_ERROR,
            payroll_provider=payroll_provider,
            error_code="payroll_transport_error",
            error_message=str(exc)[:500],
            fallback_action=FALLBACK_RETRY,
        )
    except ValueError as exc:
        result = PayrollOnboardingSyncResult(
            status=PAYROLL_ONBOARDING_SKIPPED,
            payroll_provider=payroll_provider,
            error_code=str(exc),
            fallback_action=FALLBACK_MANUAL_REVIEW,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("payroll onboarding unexpected error provider=%s", provider.provider_id)
        result = PayrollOnboardingSyncResult(
            status=PAYROLL_ONBOARDING_TRANSPORT_ERROR,
            payroll_provider=payroll_provider,
            error_code="payroll_onboarding_unexpected",
            error_message=str(exc)[:500],
            fallback_action=FALLBACK_RETRY,
        )

    _apply_sync_result_to_w2_account(w2_account, result)
    _record_payroll_onboarding_audit(db, provider_id=provider.provider_id, result=result)
    if commit:
        db.commit()
    return result
