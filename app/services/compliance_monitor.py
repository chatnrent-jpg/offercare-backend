"""COMAR 10.07.12 compliance document tracking and dispatch suspension."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import ClinicianComplianceDocument, ExclusionScreening, MarylandProvider

REQUIRED_DOCUMENT_TYPES = ("LICENSE", "CPR_BLS", "PPD", "PHYSICAL")
EXCLUSION_BLOCK_STATUSES = {"EXCLUDED", "FLAGGED"}


def seed_default_compliance_documents(
    db: Session,
    provider: MarylandProvider,
    *,
    license_expires_on: datetime | None = None,
) -> list[ClinicianComplianceDocument]:
    now = datetime.now(timezone.utc)
    defaults = {
        "LICENSE": license_expires_on or now + timedelta(days=365),
        "CPR_BLS": now + timedelta(days=730),
        "PPD": now + timedelta(days=365),
        "PHYSICAL": now + timedelta(days=365),
    }
    rows: list[ClinicianComplianceDocument] = []
    for document_type, expires_on in defaults.items():
        row = ClinicianComplianceDocument(
            provider_id=provider.provider_id,
            document_type=document_type,
            status="VALID",
            expires_on=expires_on,
            source="ONBOARDING",
        )
        db.add(row)
        rows.append(row)
    return rows


def _document_status(expires_on: datetime | None, now: datetime) -> str:
    if expires_on is None:
        return "PENDING"
    if expires_on <= now:
        return "EXPIRED"
    days = (expires_on - now).days
    if days <= settings.COMPLIANCE_ALERT_DAYS:
        return "EXPIRING"
    return "VALID"


def has_active_exclusion(db: Session, provider_id: UUID) -> bool:
    rows = (
        db.query(ExclusionScreening)
        .filter(ExclusionScreening.provider_id == provider_id)
        .order_by(ExclusionScreening.checked_at.desc())
        .all()
    )
    latest_by_source: dict[str, ExclusionScreening] = {}
    for row in rows:
        latest_by_source.setdefault(row.source, row)
    return any(row.status in EXCLUSION_BLOCK_STATUSES for row in latest_by_source.values())


def has_expired_required_documents(db: Session, provider_id: UUID) -> bool:
    rows = (
        db.query(ClinicianComplianceDocument)
        .filter(ClinicianComplianceDocument.provider_id == provider_id)
        .all()
    )
    by_type = {row.document_type: row for row in rows}
    for document_type in REQUIRED_DOCUMENT_TYPES:
        row = by_type.get(document_type)
        if row is None or row.status == "EXPIRED":
            return True
    return False


def provider_dispatch_eligible(db: Session, provider: MarylandProvider) -> bool:
    if str(provider.dispatch_status or "ACTIVE").upper() == "SUSPENDED":
        return False
    if str(provider.license_status or "").upper() != "VERIFIED":
        return False
    if has_active_exclusion(db, provider.provider_id):
        return False
    if has_expired_required_documents(db, provider.provider_id):
        return False
    from app.services.vetted_status import VETTED_CLEAR, compute_vetted_status

    if compute_vetted_status(db, provider) != VETTED_CLEAR:
        return False
    return True


def run_compliance_monitor(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    alert_days = settings.COMPLIANCE_ALERT_DAYS
    expiring: list[dict] = []
    suspended: list[str] = []

    documents = db.query(ClinicianComplianceDocument).all()
    for row in documents:
        row.status = _document_status(row.expires_on, now)
        if row.status == "EXPIRING" and row.expires_on is not None:
            days_left = (row.expires_on - now).days
            if days_left in {60, 30, 14} or days_left <= alert_days:
                expiring.append(
                    {
                        "provider_id": str(row.provider_id),
                        "document_type": row.document_type,
                        "days_left": days_left,
                    }
                )

    providers = db.query(MarylandProvider).all()
    for provider in providers:
        if has_expired_required_documents(db, provider.provider_id) or has_active_exclusion(
            db, provider.provider_id
        ):
            provider.dispatch_status = "SUSPENDED"
            suspended.append(str(provider.provider_id))
        elif provider.dispatch_status == "SUSPENDED" and provider_dispatch_eligible(db, provider):
            provider.dispatch_status = "ACTIVE"

    db.commit()
    return {
        "documents_checked": len(documents),
        "expiring_alerts": expiring,
        "suspended_provider_ids": suspended,
    }


def build_provider_compliance_status(db: Session, provider_id: UUID) -> dict:
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise ValueError("provider_not_found")
    documents = (
        db.query(ClinicianComplianceDocument)
        .filter(ClinicianComplianceDocument.provider_id == provider_id)
        .order_by(ClinicianComplianceDocument.document_type.asc())
        .all()
    )
    screenings = (
        db.query(ExclusionScreening)
        .filter(ExclusionScreening.provider_id == provider_id)
        .order_by(ExclusionScreening.checked_at.desc())
        .all()
    )
    return {
        "provider_id": str(provider.provider_id),
        "full_name": provider.full_name,
        "license_status": provider.license_status,
        "dispatch_status": provider.dispatch_status,
        "dispatch_eligible": provider_dispatch_eligible(db, provider),
        "documents": [
            {
                "document_type": row.document_type,
                "status": row.status,
                "expires_on": row.expires_on.isoformat() if row.expires_on else None,
            }
            for row in documents
        ],
        "screenings": [
            {
                "source": row.source,
                "status": row.status,
                "checked_at": row.checked_at.isoformat() if row.checked_at else None,
            }
            for row in screenings
        ],
    }
