"""Clinician calendar writer — persist shift commitments to the time vault."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DEFAULT_SHIFT_HOURS = 8.0
_EVENT_TYPE_SHIFT_COMMITMENT = "SHIFT_COMMITMENT"
_SELF_SERVICE_EVENT_TYPES = frozenset(
    {
        "BLACKOUT_UNAVAILABLE",
        "SOFT_BLOCK_PREFERENCE",
    }
)


class ClinicianCalendarWriterHardStop(RuntimeError):
    """Hive halt — calendar writer import or DB failure."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return _utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _import_clinician_calendar_event() -> Any:
    from app.models import ClinicianCalendarEvent

    return ClinicianCalendarEvent


def _provider_calendar_token(provider: Any) -> str:
    license_number = str(getattr(provider, "md_license_number", "") or "").strip()
    if license_number:
        return license_number.upper()
    return str(getattr(provider, "provider_id", "") or "").strip()


def _shift_interval_for_offer(offer: Any) -> tuple[datetime, datetime]:
    start = _utc(getattr(offer, "shift_starts_at", None))
    end_raw = getattr(offer, "shift_ends_at", None)
    if end_raw is not None:
        end = _utc(end_raw)
    else:
        end = start + timedelta(hours=_DEFAULT_SHIFT_HOURS)
    if end <= start:
        end = start + timedelta(hours=_DEFAULT_SHIFT_HOURS)
    return start, end


class ClinicianCalendarWriter:
    """Write clinician calendar events on shift lock and related lifecycle hooks."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_shift_commitment(
        self,
        *,
        provider: Any,
        offer: Any,
        facility: Any | None = None,
        channel: str,
        placement_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Insert SHIFT_COMMITMENT row for a locked shift."""
        ClinicianCalendarEvent = _import_clinician_calendar_event()
        provider_token = _provider_calendar_token(provider)
        if not provider_token:
            raise ValueError("provider calendar token is required")

        start_time, end_time = _shift_interval_for_offer(offer)
        facility_name = str(getattr(facility, "name", "") or "Maryland facility")
        metadata = {
            "event_source": "ClinicianCalendarWriter",
            "channel": str(channel or ""),
            "provider_uuid": str(getattr(provider, "provider_id", "") or ""),
            "provider_license_number": str(getattr(provider, "md_license_number", "") or ""),
            "facility_id": str(getattr(facility, "facility_id", "") or ""),
            "facility_name": facility_name,
            "shift_role": str(getattr(offer, "shift_role", "") or ""),
            "placement_id": str(placement_id) if placement_id is not None else None,
            "compliance_lock_status": str(getattr(offer, "compliance_lock_status", "") or ""),
        }

        row = ClinicianCalendarEvent(
            provider_id=provider_token,
            shift_id=str(getattr(offer, "offer_id", "") or ""),
            event_type=_EVENT_TYPE_SHIFT_COMMITMENT,
            start_time=start_time,
            end_time=end_time,
        )
        row.metadata_json = json.dumps(metadata, default=str)
        self.db.add(row)
        return {
            "ok": True,
            "provider_id": provider_token,
            "shift_id": str(getattr(offer, "offer_id", "") or ""),
            "event_type": _EVENT_TYPE_SHIFT_COMMITMENT,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }

    def record_availability_block(
        self,
        *,
        provider: Any,
        event_type: str,
        start_time: datetime,
        end_time: datetime,
        channel: str = "portal",
    ) -> dict[str, Any]:
        """Insert clinician self-service blackout or soft preference block."""
        ClinicianCalendarEvent = _import_clinician_calendar_event()
        provider_token = _provider_calendar_token(provider)
        if not provider_token:
            raise ValueError("provider calendar token is required")

        token = str(event_type or "").strip().upper()
        if token not in _SELF_SERVICE_EVENT_TYPES:
            raise ValueError("invalid_self_service_event_type")

        start = _utc(start_time)
        end = _utc(end_time)
        if end <= start:
            raise ValueError("end_time must be after start_time")

        metadata = {
            "event_source": "ClinicianCalendarWriter",
            "channel": str(channel or "portal"),
            "provider_uuid": str(getattr(provider, "provider_id", "") or ""),
            "provider_license_number": str(getattr(provider, "md_license_number", "") or ""),
        }

        row = ClinicianCalendarEvent(
            provider_id=provider_token,
            shift_id=None,
            event_type=token,
            start_time=start,
            end_time=end,
        )
        row.metadata_json = json.dumps(metadata, default=str)
        self.db.add(row)
        self.db.flush()
        return {
            "ok": True,
            "event_id": row.id,
            "provider_id": provider_token,
            "event_type": token,
            "start_time": start,
            "end_time": end,
            "created_at": row.created_at,
        }

    def delete_self_service_event(
        self,
        *,
        provider: Any,
        event_id: UUID,
    ) -> dict[str, Any]:
        """Delete portal-owned blackout or soft preference — never shift commitments."""
        ClinicianCalendarEvent = _import_clinician_calendar_event()
        provider_token = _provider_calendar_token(provider)
        if not provider_token:
            raise ValueError("provider calendar token is required")

        row = (
            self.db.query(ClinicianCalendarEvent)
            .filter(ClinicianCalendarEvent.id == event_id)
            .filter(ClinicianCalendarEvent.provider_id == provider_token)
            .first()
        )
        if row is None:
            raise ValueError("event_not_found")

        event_type = str(row.event_type or "").strip().upper()
        if event_type not in _SELF_SERVICE_EVENT_TYPES:
            raise ValueError("event_not_deletable")

        self.db.delete(row)
        return {
            "ok": True,
            "event_id": event_id,
            "event_type": event_type,
        }


def record_shift_commitment_safe(
    db: Session,
    *,
    provider: Any,
    offer: Any,
    facility: Any | None = None,
    channel: str,
    placement_id: UUID | None = None,
) -> dict[str, Any]:
    """Fail-open calendar write — shift lock must not break if vault insert fails."""
    try:
        writer = ClinicianCalendarWriter(db)
        return writer.record_shift_commitment(
            provider=provider,
            offer=offer,
            facility=facility,
            channel=channel,
            placement_id=placement_id,
        )
    except SQLAlchemyError as exc:
        logger.warning(
            "HIVE_CALENDAR_WRITE: shift commitment failed provider=%s offer=%s error=%s",
            getattr(provider, "provider_id", None),
            getattr(offer, "offer_id", None),
            exc,
        )
        return {"ok": False, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "HIVE_CALENDAR_WRITE: shift commitment fault provider=%s offer=%s error=%s",
            getattr(provider, "provider_id", None),
            getattr(offer, "offer_id", None),
            exc,
        )
        return {"ok": False, "message": str(exc)}


if __name__ == "__main__":
    print("COMPILE_OK clinician_calendar_writer")
    print(f"event_type={_EVENT_TYPE_SHIFT_COMMITMENT}")
