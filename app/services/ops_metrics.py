"""Operations metrics and audit trail."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    ClinicalPlacementLedger,
    MarylandFacility,
    MarylandProvider,
    OfferCareJobOffer,
    OpsAuditLog,
    ShiftNotificationLog,
)


def log_ops_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    actor: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> OpsAuditLog | None:
    if not settings.OPS_AUDIT_ENABLED:
        return None
    row = OpsAuditLog(
        event_type=str(event_type).strip().upper(),
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary[:500],
        metadata_json=json.dumps(metadata)[:2000] if metadata else None,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def list_ops_audit_events(db: Session, *, limit: int = 50) -> list[OpsAuditLog]:
    return (
        db.query(OpsAuditLog)
        .order_by(OpsAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


def get_ops_metrics(db: Session) -> dict[str, Any]:
    pending_clinicians = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.license_status == "UNVERIFIED")
        .count()
    )
    verified_clinicians = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.license_status == "VERIFIED")
        .count()
    )
    open_shifts = (
        db.query(OfferCareJobOffer)
        .filter(OfferCareJobOffer.compliance_lock_status != "LOCKED")
        .count()
    )
    locked_shifts = (
        db.query(OfferCareJobOffer)
        .filter(OfferCareJobOffer.compliance_lock_status == "LOCKED")
        .count()
    )
    total_sms_sent = (
        db.query(ShiftNotificationLog)
        .filter(ShiftNotificationLog.channel == "SMS")
        .count()
    )
    total_emails_sent = (
        db.query(ShiftNotificationLog)
        .filter(ShiftNotificationLog.channel == "EMAIL")
        .count()
    )
    total_placements = db.query(ClinicalPlacementLedger).count()
    vms_pending = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.vms_submission_status == "PENDING")
        .count()
    )
    vms_submitted = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.vms_submission_status == "SUBMITTED")
        .count()
    )
    facilities = db.query(MarylandFacility).count()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    audit_events_24h = (
        db.query(OpsAuditLog)
        .filter(OpsAuditLog.created_at >= cutoff)
        .count()
    )
    raw_lock_rate = total_placements / total_sms_sent if total_sms_sent else 0.0
    lock_rate = round(min(1.0, raw_lock_rate), 4)
    return {
        "pending_clinicians": pending_clinicians,
        "verified_clinicians": verified_clinicians,
        "open_shifts": open_shifts,
        "locked_shifts": locked_shifts,
        "total_sms_sent": total_sms_sent,
        "total_emails_sent": total_emails_sent,
        "total_placements": total_placements,
        "vms_pending": vms_pending,
        "vms_submitted": vms_submitted,
        "facilities": facilities,
        "audit_events_24h": audit_events_24h,
        "lock_rate": lock_rate,
    }
