"""Immutable VettedMe audit trail for credential safety events."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import VettedMeAuditLog


def log_vetted_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    provider_id: UUID | None = None,
    actor: str = "system",
    previous_status: str | None = None,
    new_status: str | None = None,
    metadata: dict | None = None,
    commit: bool = False,
) -> VettedMeAuditLog:
    row = VettedMeAuditLog(
        provider_id=provider_id,
        event_type=event_type,
        actor=actor,
        previous_status=previous_status,
        new_status=new_status,
        summary=summary[:500],
        metadata_json=json.dumps(metadata or {}, default=str)[:4000],
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def list_vetted_audit(
    db: Session,
    *,
    provider_id: UUID | None = None,
    limit: int = 50,
) -> list[dict]:
    query = db.query(VettedMeAuditLog).order_by(VettedMeAuditLog.created_at.desc())
    if provider_id is not None:
        query = query.filter(VettedMeAuditLog.provider_id == provider_id)
    rows = query.limit(min(limit, 200)).all()
    return [
        {
            "audit_id": str(row.audit_id),
            "provider_id": str(row.provider_id) if row.provider_id else None,
            "event_type": row.event_type,
            "actor": row.actor,
            "previous_status": row.previous_status,
            "new_status": row.new_status,
            "summary": row.summary,
            "metadata": json.loads(row.metadata_json) if row.metadata_json else {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
