"""End-to-end Maryland credentialing pipeline for new applicants."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ClinicianComplianceDocument, ExclusionScreening, LicenseVerificationLog, MarylandProvider
from app.services.compliance_monitor import seed_default_compliance_documents
from app.services.license_verification import run_license_auto_check
from app.services.mbon_verification import mbon_result_to_json, verify_mbon_license
from app.services.md_judiciary_screen import judiciary_result_to_json, screen_md_judiciary
from app.services.oig_exclusion import oig_result_to_json, screen_oig_exclusion


def _log_screening(
    db: Session,
    *,
    provider_id: UUID,
    source: str,
    status: str,
    payload_json: str,
) -> ExclusionScreening:
    row = ExclusionScreening(
        provider_id=provider_id,
        source=source,
        status=status,
        expires_on=datetime.now(timezone.utc) + timedelta(days=30),
        payload_json=payload_json,
    )
    db.add(row)
    return row


def run_full_credentialing_screen(db: Session, provider_id: UUID) -> dict:
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise ValueError("provider_not_found")

    format_check = run_license_auto_check(
        npi_number=provider.npi_number,
        md_license_number=provider.md_license_number,
        state=provider.state,
        credential_type=provider.credential_type,
    )
    mbon = verify_mbon_license(provider)
    oig = screen_oig_exclusion(provider)
    judiciary = screen_md_judiciary(provider)

    _log_screening(
        db,
        provider_id=provider.provider_id,
        source="MBON",
        status="EXCLUDED" if mbon.status in {"EXPIRED", "DISCIPLINE", "NOT_FOUND"} else "CLEAR",
        payload_json=mbon_result_to_json(mbon),
    )
    _log_screening(
        db,
        provider_id=provider.provider_id,
        source="OIG_LEIE",
        status=oig.status,
        payload_json=oig_result_to_json(oig),
    )
    _log_screening(
        db,
        provider_id=provider.provider_id,
        source="MD_JUDICIARY",
        status=judiciary.status,
        payload_json=judiciary_result_to_json(judiciary),
    )

    if mbon.expires_on:
        provider.license_expires_on = mbon.expires_on

    blocked = (
        format_check.result == "FAIL"
        or mbon.status != "ACTIVE"
        or oig.status == "EXCLUDED"
        or judiciary.status == "FLAGGED"
    )
    if blocked:
        provider.license_status = "REJECTED"
        provider.dispatch_status = "SUSPENDED"
        provider.verification_notes = "Automated credentialing screen blocked dispatch."
    else:
        provider.license_status = "VERIFIED"
        provider.dispatch_status = "ACTIVE"
        provider.last_verified_timestamp = datetime.now(timezone.utc)
        provider.verification_notes = "Automated Maryland credentialing screen passed."
        if (
            db.query(ClinicianComplianceDocument)
            .filter(ClinicianComplianceDocument.provider_id == provider.provider_id)
            .count()
            == 0
        ):
            seed_default_compliance_documents(db, provider, license_expires_on=mbon.expires_on)

    db.add(
        LicenseVerificationLog(
            provider_id=provider.provider_id,
            event_type="CREDENTIALING_SCREEN",
            check_result="BLOCKED" if blocked else "PASSED",
            notes=provider.verification_notes,
            reviewer="credentialing_pipeline",
        )
    )
    db.commit()
    db.refresh(provider)

    return {
        "provider_id": str(provider.provider_id),
        "format_check": format_check.result,
        "mbon_status": mbon.status,
        "oig_status": oig.status,
        "judiciary_status": judiciary.status,
        "license_status": provider.license_status,
        "dispatch_status": provider.dispatch_status,
        "blocked": blocked,
    }
