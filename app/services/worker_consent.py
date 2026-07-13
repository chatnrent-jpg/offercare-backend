"""Opt-in worker consent recording and SMS dispatch eligibility."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import LicenseVerificationLog, MarylandProvider
from app.services.sms_compliance import provider_is_sms_opted_out
from app.services.worker_privacy_policy import (
    CONSENT_PRIVACY_POLICY,
    WORKER_PRIVACY_VERSION,
    build_worker_privacy_policy,
)
from app.services.worker_terms_of_service import (
    CONSENT_TERMS_OF_SERVICE,
    WORKER_TERMS_VERSION,
    build_worker_terms_of_service,
)

WORKER_CONSENT_VERSION = "2026-06-21"

CONSENT_CREDENTIAL_SCREENING = (
    "I authorize VettedMe.ai to verify my Maryland license/certification through MBON, "
    "OIG LEIE, and Maryland judiciary exclusion databases."
)
CONSENT_SMS_DISPATCH = (
    "I agree to receive automated shift-offer text messages at the mobile number I provided. "
    "Message and data rates may apply. Reply STOP to opt out or YES to accept a shift."
)
CONSENT_HB1106_AUTOMATED_HIRING_ANTI_BIAS = (
    "Under Maryland HB 1106, I acknowledge that VettedMe.ai may use automated tools in "
    "hiring and shift-matching decisions. I consent to the 10-day automated hiring anti-bias "
    "disclosure and authorize storage of this consent for Maryland compliance reporting."
)

CONSENT_MARYLAND_AEDT_30_DAY = (
    "Maryland Automated Employment Decision Tool (AEDT) — 30-day notice: I understand that "
    "VettedMe.ai uses an automated AI tool to process my Maryland license credentials, "
    "geographic proximity to open shifts, and experience parameters solely for per-diem shift "
    "routing. I consent to this automated processing and authorize VettedMe.ai to store a "
    "timestamped record of this disclosure for Maryland compliance reporting."
)

CONSENT_EVENT_TYPES: tuple[tuple[str, str], ...] = (
    ("CONSENT_CREDENTIAL_SCREENING", CONSENT_CREDENTIAL_SCREENING),
    ("CONSENT_SMS_DISPATCH", CONSENT_SMS_DISPATCH),
    ("CONSENT_TERMS_OF_SERVICE", CONSENT_TERMS_OF_SERVICE),
    ("CONSENT_PRIVACY_POLICY", CONSENT_PRIVACY_POLICY),
)


def build_consent_disclosures() -> dict:
    terms = build_worker_terms_of_service()
    privacy = build_worker_privacy_policy()
    return {
        "version": WORKER_CONSENT_VERSION,
        "credential_screening": CONSENT_CREDENTIAL_SCREENING,
        "sms_dispatch": CONSENT_SMS_DISPATCH,
        "terms_of_service": CONSENT_TERMS_OF_SERVICE,
        "terms_of_service_version": terms["version"],
        "terms_of_service_effective_date": terms["effective_date"],
        "terms_of_service_url": "/api/landing/maryland/terms-of-service",
        "privacy_policy": CONSENT_PRIVACY_POLICY,
        "privacy_policy_version": privacy["version"],
        "privacy_policy_effective_date": privacy["effective_date"],
        "privacy_policy_url": "/api/landing/maryland/privacy-policy",
        "hb1106_automated_hiring_anti_bias": CONSENT_HB1106_AUTOMATED_HIRING_ANTI_BIAS,
        "maryland_aedt_30_day": CONSENT_MARYLAND_AEDT_30_DAY,
    }


def _consent_note(*, consent_version: str, disclosure: str, client_ip: str | None) -> str:
    ip_token = client_ip or "unknown"
    return f"v={consent_version}; ip={ip_token}; {disclosure[:380]}"


def record_apply_consents(
    db: Session,
    provider_id: UUID,
    *,
    consent_version: str,
    client_ip: str | None = None,
    commit: bool = False,
) -> None:
    for event_type, disclosure in CONSENT_EVENT_TYPES:
        db.add(
            LicenseVerificationLog(
                provider_id=provider_id,
                event_type=event_type,
                check_result="PASS",
                notes=_consent_note(
                    consent_version=consent_version,
                    disclosure=disclosure,
                    client_ip=client_ip,
                ),
                reviewer="worker_apply",
            )
        )
    if commit:
        db.commit()


def provider_has_sms_dispatch_consent(
    db: Session,
    provider_id: UUID,
    *,
    email: str | None = None,
    provider: MarylandProvider | None = None,
) -> bool:
    if email and str(email).lower().endswith("@offercare.demo"):
        return True
    row = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if row is not None and provider_is_sms_opted_out(row):
        return False
    if provider is not None and provider_is_sms_opted_out(provider):
        return False
    consent_row = (
        db.query(LicenseVerificationLog.log_id)
        .filter(
            LicenseVerificationLog.provider_id == provider_id,
            LicenseVerificationLog.event_type == "CONSENT_SMS_DISPATCH",
            LicenseVerificationLog.check_result == "PASS",
        )
        .first()
    )
    return consent_row is not None


def provider_has_hb1106_automated_hiring_consent(
    db: Session,
    provider_id: UUID,
) -> LicenseVerificationLog | None:
    return (
        db.query(LicenseVerificationLog)
        .filter(
            LicenseVerificationLog.provider_id == provider_id,
            LicenseVerificationLog.event_type.in_(
                ("CONSENT_HB1106_ANTI_BIAS", "CONSENT_MARYLAND_AEDT_30_DAY")
            ),
            LicenseVerificationLog.check_result == "PASS",
        )
        .order_by(LicenseVerificationLog.created_at.desc())
        .first()
    )


def resolve_provider_consent_signed_at(
    db: Session,
    provider_id: UUID,
) -> datetime | None:
    """Authoritative AEDT consent timestamp — profile column first, audit log fallback."""
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is not None and provider.consent_signed_at is not None:
        value = provider.consent_signed_at
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    consent_row = provider_has_hb1106_automated_hiring_consent(db, provider_id)
    if consent_row is None or consent_row.created_at is None:
        return None
    value = consent_row.created_at
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def record_maryland_aedt_consent(
    db: Session,
    provider_id: UUID,
    *,
    consent_version: str,
    client_ip: str | None = None,
    signed_at: datetime | None = None,
    commit: bool = False,
) -> datetime:
    """Persist mandatory Maryland AEDT disclosure — profile consent_signed_at + audit logs."""
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise ValueError("provider_not_found")

    signed = signed_at or datetime.now(timezone.utc)
    if signed.tzinfo is None:
        signed = signed.replace(tzinfo=timezone.utc)
    else:
        signed = signed.astimezone(timezone.utc)

    provider.consent_signed_at = signed
    for event_type, disclosure in (
        ("CONSENT_MARYLAND_AEDT_30_DAY", CONSENT_MARYLAND_AEDT_30_DAY),
        ("CONSENT_HB1106_ANTI_BIAS", CONSENT_HB1106_AUTOMATED_HIRING_ANTI_BIAS),
    ):
        db.add(
            LicenseVerificationLog(
                provider_id=provider_id,
                event_type=event_type,
                check_result="PASS",
                notes=_consent_note(
                    consent_version=consent_version,
                    disclosure=disclosure,
                    client_ip=client_ip,
                ),
                reviewer="maryland_aedt_disclosure",
            )
        )
    if commit:
        db.commit()
    return signed


def build_worker_inflow_summary(db: Session) -> dict:
    real_providers = (
        db.query(MarylandProvider)
        .filter(~MarylandProvider.email.like("%@offercare.demo"))
        .all()
    )
    consented_ids = {
        row[0]
        for row in db.query(LicenseVerificationLog.provider_id)
        .filter(
            LicenseVerificationLog.event_type == "CONSENT_SMS_DISPATCH",
            LicenseVerificationLog.check_result == "PASS",
        )
        .distinct()
        .all()
    }
    tos_accepted_ids = {
        row[0]
        for row in db.query(LicenseVerificationLog.provider_id)
        .filter(
            LicenseVerificationLog.event_type == "CONSENT_TERMS_OF_SERVICE",
            LicenseVerificationLog.check_result == "PASS",
        )
        .distinct()
        .all()
    }
    privacy_accepted_ids = {
        row[0]
        for row in db.query(LicenseVerificationLog.provider_id)
        .filter(
            LicenseVerificationLog.event_type == "CONSENT_PRIVACY_POLICY",
            LicenseVerificationLog.check_result == "PASS",
        )
        .distinct()
        .all()
    }
    sms_opt_out_count = sum(1 for row in real_providers if provider_is_sms_opted_out(row))
    verified = sum(1 for row in real_providers if str(row.license_status).upper() == "VERIFIED")
    pending = sum(1 for row in real_providers if str(row.license_status).upper() == "UNVERIFIED")
    return {
        "join_url": "/join",
        "consent_version": WORKER_CONSENT_VERSION,
        "terms_of_service_version": WORKER_TERMS_VERSION,
        "privacy_policy_version": WORKER_PRIVACY_VERSION,
        "opt_in_applicants": len(real_providers),
        "pending_review": pending,
        "verified_workers": verified,
        "sms_consent_recorded": sum(1 for row in real_providers if row.provider_id in consented_ids),
        "terms_accepted": sum(1 for row in real_providers if row.provider_id in tos_accepted_ids),
        "privacy_accepted": sum(1 for row in real_providers if row.provider_id in privacy_accepted_ids),
        "sms_opt_out_count": sms_opt_out_count,
        "legal_model": "opt_in_apply_only",
        "playbook": [
            "Share /join — nurses apply voluntarily with SMS, Privacy Policy, and Terms acceptance.",
            "Review Pending clinicians — verify MBON/OIG before dispatching shifts.",
            "STOP/HELP SMS keywords are handled automatically on inbound Twilio webhook.",
            "Use B2B outreach pipeline for facility administrators only (email, not SMS).",
        ],
    }
