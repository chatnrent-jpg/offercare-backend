"""Clinician self-apply and Maryland license verification workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LicenseVerificationLog, MarylandProvider
from app.schemas import ClinicianApplyRequest
from app.services.care_taxonomy import (
    default_service_lines_for_credential,
    infer_credential_from_license,
    normalize_credential_type,
    requires_npi,
    synthetic_npi_for_caregiver,
)
from app.services.clinician_auth import create_portal_account
from app.services.states import normalize_state
from app.services.ops_metrics import log_ops_event
from app.services.shift_lock import normalize_phone


@dataclass(frozen=True)
class AutoCheckResult:
    result: str
    message: str


def is_valid_npi(npi_number: str) -> bool:
    digits = re.sub(r"\D", "", str(npi_number or ""))
    if len(digits) != 10 or not digits.isdigit():
        return False
    total = 0
    payload = f"80840{digits}"
    for index, char in enumerate(reversed(payload)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def is_regional_license_format(license_number: str) -> bool:
    token = str(license_number or "").strip().upper()
    if len(token) < 5:
        return False
    return bool(re.match(r"^[A-Z0-9][A-Z0-9\- ]{3,48}$", token))


def is_maryland_license_format(license_number: str) -> bool:
    return is_regional_license_format(license_number)


def run_license_auto_check(
    *,
    npi_number: str | None,
    md_license_number: str,
    state: str = "MD",
    credential_type: str = "RN",
) -> AutoCheckResult:
    from app.services.states import is_supported_state, normalize_state

    cred = normalize_credential_type(credential_type)
    npi_required = requires_npi(cred)
    npi_ok = True if not npi_required and not str(npi_number or "").strip() else is_valid_npi(str(npi_number or ""))
    license_ok = is_regional_license_format(md_license_number)
    state_ok = is_supported_state(state)
    normalized_state = normalize_state(state)
    if npi_ok and license_ok and state_ok:
        if settings.LICENSE_VERIFY_DRY_RUN:
            return AutoCheckResult(
                result="STUB_PASS",
                message=f"Format checks passed for {cred} in {normalized_state}. Awaiting admin verification.",
            )
        return AutoCheckResult(result="PASS", message="Automated checks passed.")
    reasons: list[str] = []
    if not npi_ok:
        reasons.append("invalid NPI checksum")
    if not license_ok:
        reasons.append("invalid license format")
    if not state_ok:
        reasons.append("unsupported state")
    return AutoCheckResult(result="FAIL", message="; ".join(reasons))


def _log_event(
    db: Session,
    *,
    provider_id: UUID,
    event_type: str,
    check_result: str | None = None,
    notes: str | None = None,
    reviewer: str | None = None,
) -> LicenseVerificationLog:
    row = LicenseVerificationLog(
        provider_id=provider_id,
        event_type=event_type,
        check_result=check_result,
        notes=notes,
        reviewer=reviewer,
    )
    db.add(row)
    return row


def apply_as_clinician(db: Session, payload: ClinicianApplyRequest) -> tuple[MarylandProvider, AutoCheckResult]:
    credential_type = normalize_credential_type(payload.credential_type)
    if credential_type == "RN":
        inferred = infer_credential_from_license(payload.md_license_number)
        if inferred:
            credential_type = inferred
    npi_number = str(payload.npi_number or "").strip()
    if not npi_number:
        npi_number = synthetic_npi_for_caregiver(str(payload.email))
    auto_check = run_license_auto_check(
        npi_number=npi_number,
        md_license_number=payload.md_license_number,
        state=payload.state,
        credential_type=credential_type,
    )
    provider = MarylandProvider(
        full_name=payload.full_name.strip(),
        email=str(payload.email).strip().lower(),
        phone_number=normalize_phone(payload.phone_number),
        npi_number=npi_number,
        md_license_number=payload.md_license_number.strip().upper(),
        state=normalize_state(payload.state),
        credential_type=credential_type,
        service_lines=str(payload.service_lines or default_service_lines_for_credential(credential_type)).upper(),
        license_status="UNVERIFIED",
        min_hourly_rate=payload.min_hourly_rate,
        response_propensity=payload.response_propensity,
        fatigue_score=payload.fatigue_score,
        verification_notes=auto_check.message,
    )
    db.add(provider)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("duplicate_application") from exc

    _log_event(
        db,
        provider_id=provider.provider_id,
        event_type="APPLIED",
        check_result=auto_check.result,
        notes=auto_check.message,
    )
    if payload.password:
        create_portal_account(db, provider.provider_id, payload.password, commit=False)
    db.commit()
    db.refresh(provider)
    if settings.CREDENTIALING_AUTO_SCREEN_ON_APPLY:
        from app.services.credentialing_pipeline import run_full_credentialing_screen

        run_full_credentialing_screen(db, provider.provider_id)
        db.refresh(provider)
    return provider, auto_check


def list_pending_clinicians(db: Session) -> list[MarylandProvider]:
    return (
        db.query(MarylandProvider)
        .filter(MarylandProvider.license_status == "UNVERIFIED")
        .order_by(MarylandProvider.applied_at.asc())
        .all()
    )


def verify_clinician(
    db: Session,
    provider_id: UUID,
    *,
    action: str,
    notes: str | None = None,
    reviewer: str = "admin",
) -> tuple[MarylandProvider, LicenseVerificationLog]:
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise ValueError("provider_not_found")

    action_token = action.strip().upper()
    if action_token == "VERIFY":
        if str(provider.license_status).upper() == "VERIFIED":
            raise ValueError("already_verified")
        provider.license_status = "VERIFIED"
        provider.last_verified_timestamp = datetime.now(timezone.utc)
        event_type = "VERIFIED"
        check_result = "MANUAL_APPROVED"
    elif action_token == "REJECT":
        provider.license_status = "REJECTED"
        event_type = "REJECTED"
        check_result = "MANUAL_REJECTED"
    elif action_token == "EXPIRE":
        provider.license_status = "EXPIRED"
        event_type = "EXPIRED"
        check_result = "MANUAL_EXPIRED"
    else:
        raise ValueError("invalid_action")

    if notes:
        provider.verification_notes = notes.strip()

    log = _log_event(
        db,
        provider_id=provider.provider_id,
        event_type=event_type,
        check_result=check_result,
        notes=notes,
        reviewer=reviewer,
    )
    log_ops_event(
        db,
        event_type="CLINICIAN_VERIFY",
        actor=reviewer,
        entity_type="provider",
        entity_id=provider.provider_id,
        summary=f"Clinician {provider.full_name} {event_type.lower()}",
        metadata={"action": action_token, "check_result": check_result},
        commit=False,
    )
    db.commit()
    db.refresh(provider)
    db.refresh(log)
    return provider, log


def list_verification_history(db: Session, provider_id: UUID) -> list[LicenseVerificationLog]:
    return (
        db.query(LicenseVerificationLog)
        .filter(LicenseVerificationLog.provider_id == provider_id)
        .order_by(LicenseVerificationLog.created_at.asc())
        .all()
    )
