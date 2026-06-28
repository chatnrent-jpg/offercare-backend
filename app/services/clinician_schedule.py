"""Clinician schedule — time vault read/write for portal and API."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import MarylandProvider

logger = logging.getLogger(__name__)

ALLOWED_SELF_SERVICE_BLOCK_TYPES = frozenset(
    {
        "BLACKOUT_UNAVAILABLE",
        "SOFT_BLOCK_PREFERENCE",
    }
)


def provider_calendar_token(provider: MarylandProvider) -> str:
    license_number = str(getattr(provider, "md_license_number", "") or "").strip()
    if license_number:
        return license_number.upper()
    return str(getattr(provider, "provider_id", "") or "").strip()


def _parse_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _serialize_event_row(row: Any) -> dict[str, Any]:
    meta = _parse_metadata(getattr(row, "metadata_json", None))
    return {
        "event_id": row.id,
        "event_type": str(row.event_type),
        "shift_id": str(row.shift_id) if row.shift_id else None,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "facility_name": meta.get("facility_name"),
        "shift_role": meta.get("shift_role"),
        "created_at": row.created_at,
    }


def list_clinician_schedule_events(
    db: Session,
    provider: MarylandProvider,
    *,
    limit: int = 50,
    upcoming_only: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    """Return calendar vault rows for the signed-in clinician."""
    token = provider_calendar_token(provider)
    if not token:
        return token, []

    try:
        from app.models import ClinicianCalendarEvent
    except Exception:
        logger.warning("clinician_calendar model unavailable")
        return token, []

    try:
        query = db.query(ClinicianCalendarEvent).filter(ClinicianCalendarEvent.provider_id == token)
        if upcoming_only:
            now = datetime.now(timezone.utc)
            query = query.filter(ClinicianCalendarEvent.end_time >= now)
        rows = (
            query.order_by(ClinicianCalendarEvent.start_time.asc())
            .limit(max(1, min(int(limit), 200)))
            .all()
        )
    except SQLAlchemyError as exc:
        logger.warning("clinician schedule query failed provider=%s error=%s", token, exc)
        return token, []

    return token, [_serialize_event_row(row) for row in rows]


def resolve_provider_by_calendar_token(db: Session, token: str) -> MarylandProvider | None:
    """Resolve clinician by license number (vault key) or provider UUID."""
    raw = str(token or "").strip()
    if not raw:
        return None
    try:
        provider_uuid = UUID(raw)
    except ValueError:
        provider_uuid = None
    if provider_uuid is not None:
        row = (
            db.query(MarylandProvider)
            .filter(MarylandProvider.provider_id == provider_uuid)
            .first()
        )
        if row is not None:
            return row
    return (
        db.query(MarylandProvider)
        .filter(MarylandProvider.md_license_number.ilike(raw))
        .first()
    )


def create_clinician_schedule_block(
    db: Session,
    provider: MarylandProvider,
    *,
    event_type: str,
    start_time: datetime,
    end_time: datetime,
    channel: str = "portal",
) -> dict[str, Any]:
    """Create blackout or soft preference — reject hard calendar conflicts."""
    token = str(event_type or "").strip().upper()
    if token not in ALLOWED_SELF_SERVICE_BLOCK_TYPES:
        raise ValueError("invalid_self_service_event_type")

    calendar_token = provider_calendar_token(provider)
    if not calendar_token:
        raise ValueError("provider calendar token is required")

    from strategy.clinician_calendar_writer import ClinicianCalendarWriter
    from strategy.schedule_conflict_validator import ScheduleConflictValidator

    validator = ScheduleConflictValidator(db=db)
    try:
        clearance = validator.evaluate_schedule_clearance(calendar_token, start_time, end_time)
        if clearance.get("has_conflict") or clearance.get("conflict_type") == "HARD_OVERLAP":
            raise ValueError("schedule_conflict")
    finally:
        validator.close()

    writer = ClinicianCalendarWriter(db)
    payload = writer.record_availability_block(
        provider=provider,
        event_type=token,
        start_time=start_time,
        end_time=end_time,
        channel=channel,
    )
    db.commit()
    return {
        "event_id": payload["event_id"],
        "event_type": payload["event_type"],
        "shift_id": None,
        "start_time": payload["start_time"],
        "end_time": payload["end_time"],
        "facility_name": None,
        "shift_role": None,
        "created_at": payload.get("created_at"),
    }


def delete_clinician_schedule_block(
    db: Session,
    provider: MarylandProvider,
    *,
    event_id: UUID,
) -> UUID:
    """Delete self-service block owned by the signed-in clinician."""
    from strategy.clinician_calendar_writer import ClinicianCalendarWriter

    writer = ClinicianCalendarWriter(db)
    payload = writer.delete_self_service_event(provider=provider, event_id=event_id)
    db.commit()
    return UUID(str(payload["event_id"]))


def ops_create_schedule_block(
    db: Session,
    *,
    provider_token: str,
    event_type: str,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, Any]:
    """Ops console write — blackout or soft preference for a provider vault token."""
    provider = resolve_provider_by_calendar_token(db, provider_token)
    if provider is None:
        raise ValueError("provider_not_found")
    return create_clinician_schedule_block(
        db,
        provider,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
        channel="ops_console",
    )


def ops_delete_schedule_block(
    db: Session,
    *,
    provider_token: str,
    event_id: UUID,
) -> UUID:
    """Ops console delete — self-service blocks only."""
    provider = resolve_provider_by_calendar_token(db, provider_token)
    if provider is None:
        raise ValueError("provider_not_found")
    return delete_clinician_schedule_block(db, provider, event_id=event_id)
