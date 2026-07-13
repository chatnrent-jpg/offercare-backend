"""VettedMe.ai — credential safety status engine (CLEAR / EXPIRING / ACTION_NEEDED / BLOCKED)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import ClinicianComplianceDocument, MarylandProvider
from app.services.compliance_monitor import (
    REQUIRED_DOCUMENT_TYPES,
    build_provider_compliance_status,
    has_active_exclusion,
    provider_dispatch_eligible,
    _document_status,
)

VETTED_CLEAR = "CLEAR"
VETTED_EXPIRING = "EXPIRING"
VETTED_ACTION_NEEDED = "ACTION_NEEDED"
VETTED_BLOCKED = "BLOCKED"

ALL_VETTED_STATUSES = (VETTED_CLEAR, VETTED_EXPIRING, VETTED_ACTION_NEEDED, VETTED_BLOCKED)

_LICENSE_BLOCK_STATUSES = {"EXPIRED", "REVOKED", "SUSPENDED", "DENIED"}


def compute_vetted_status(db: Session, provider: MarylandProvider) -> str:
    """Derive safety status from license, documents, exclusions, and dispatch state."""
    now = datetime.now(timezone.utc)
    provider_id = provider.provider_id

    if has_active_exclusion(db, provider_id):
        return VETTED_BLOCKED

    license_status = str(provider.license_status or "UNVERIFIED").upper()
    if license_status in _LICENSE_BLOCK_STATUSES:
        return VETTED_BLOCKED

    documents = (
        db.query(ClinicianComplianceDocument)
        .filter(ClinicianComplianceDocument.provider_id == provider_id)
        .all()
    )
    by_type = {row.document_type: row for row in documents}

    for document_type in REQUIRED_DOCUMENT_TYPES:
        row = by_type.get(document_type)
        if row is None:
            return VETTED_ACTION_NEEDED
        doc_status = _document_status(row.expires_on, now)
        if doc_status == "EXPIRED":
            return VETTED_BLOCKED
        if doc_status == "PENDING":
            return VETTED_ACTION_NEEDED

    if license_status != "VERIFIED":
        return VETTED_ACTION_NEEDED

    has_expiring = False
    for row in documents:
        doc_status = _document_status(row.expires_on, now)
        if doc_status == "EXPIRING":
            has_expiring = True
            break

    if provider.license_expires_on is not None:
        days_to_license = (provider.license_expires_on - now).days
        if days_to_license <= settings.COMPLIANCE_ALERT_DAYS:
            has_expiring = True

    if has_expiring:
        return VETTED_EXPIRING

    if str(provider.dispatch_status or "ACTIVE").upper() == "SUSPENDED":
        return VETTED_BLOCKED

    return VETTED_CLEAR


def sync_provider_vetted_status(
    db: Session,
    provider: MarylandProvider,
    *,
    actor: str = "vetted_status_engine",
) -> tuple[str, str | None]:
    """Update cached vetted_status; return (new_status, previous_status if changed)."""
    previous = str(provider.vetted_status or VETTED_ACTION_NEEDED).upper()
    new_status = compute_vetted_status(db, provider)
    if new_status != previous:
        provider.vetted_status = new_status
        provider.vetted_status_updated_at = datetime.now(timezone.utc)
        return new_status, previous
    if provider.vetted_status_updated_at is None:
        provider.vetted_status = new_status
        provider.vetted_status_updated_at = datetime.now(timezone.utc)
    return new_status, None


def sync_all_vetted_statuses(db: Session, *, actor: str = "vetted_status_engine") -> dict:
    providers = db.query(MarylandProvider).all()
    changes: list[dict] = []
    counts = {status: 0 for status in ALL_VETTED_STATUSES}

    for provider in providers:
        new_status, previous = sync_provider_vetted_status(db, provider, actor=actor)
        counts[new_status] = counts.get(new_status, 0) + 1
        if previous is not None:
            changes.append(
                {
                    "provider_id": str(provider.provider_id),
                    "full_name": provider.full_name,
                    "previous_status": previous,
                    "new_status": new_status,
                }
            )

    db.commit()
    return {
        "providers_synced": len(providers),
        "status_counts": counts,
        "status_changes": changes,
    }


def build_provider_vetted_profile(db: Session, provider_id: UUID) -> dict:
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise ValueError("provider_not_found")

    computed = compute_vetted_status(db, provider)
    compliance = build_provider_compliance_status(db, provider_id)
    return {
        "provider_id": str(provider.provider_id),
        "full_name": provider.full_name,
        "credential_type": provider.credential_type,
        "email": provider.email,
        "phone_number": provider.phone_number,
        "npi_number": provider.npi_number,
        "md_license_number": provider.md_license_number,
        "license_status": provider.license_status,
        "dispatch_status": provider.dispatch_status,
        "dispatch_eligible": provider_dispatch_eligible(db, provider),
        "vetted_status": str(provider.vetted_status or computed).upper(),
        "computed_status": computed,
        "vetted_status_updated_at": provider.vetted_status_updated_at.isoformat()
        if provider.vetted_status_updated_at
        else None,
        "license_expires_on": provider.license_expires_on.isoformat() if provider.license_expires_on else None,
        "last_verified_timestamp": provider.last_verified_timestamp.isoformat()
        if provider.last_verified_timestamp
        else None,
        "documents": compliance["documents"],
        "screenings": compliance["screenings"],
    }
