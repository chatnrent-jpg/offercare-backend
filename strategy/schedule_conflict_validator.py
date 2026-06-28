"""Schedule conflict validator — time sentinel for clinician calendar vault overlaps."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_CONFLICT_CLEAR = "CLEAR"
_CONFLICT_HARD = "HARD_OVERLAP"
_CONFLICT_SOFT = "SOFT_PREFERENCE_HIT"
_CONFLICT_FATIGUE_HARD = "FATIGUE_CAP_EXCEEDED"
_CONFLICT_FATIGUE_SOFT = "FATIGUE_ELEVATED"

_HARD_BLOCK_EVENT_TYPES = frozenset({"SHIFT_COMMITMENT", "BLACKOUT_UNAVAILABLE"})
_SOFT_BLOCK_EVENT_TYPE = "SOFT_BLOCK_PREFERENCE"


class ScheduleConflictValidatorHardStop(RuntimeError):
    """Hive halt — schedule conflict validator import or DB failure."""


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _intervals_overlap(
    start_time: datetime,
    end_time: datetime,
    existing_start: datetime,
    existing_end: datetime,
) -> bool:
    start = _utc(start_time)
    end = _utc(end_time)
    existing_start_norm = _utc(existing_start)
    existing_end_norm = _utc(existing_end)
    return start < existing_end_norm and end > existing_start_norm


def _import_clinician_calendar_event() -> Any:
    from app.models import ClinicianCalendarEvent

    return ClinicianCalendarEvent


class ScheduleConflictValidator:
    """PostgreSQL-backed schedule clearance broker for provider calendar events."""

    def __init__(self, db: Session | None = None) -> None:
        self._db = db
        self._owns_session = False

    @property
    def db(self) -> Session:
        if self._db is None:
            try:
                from app.database import SessionLocal
            except Exception as exc:  # noqa: BLE001
                raise ScheduleConflictValidatorHardStop("database_session_import_failed") from exc
            self._db = SessionLocal()
            self._owns_session = True
        return self._db

    def close(self) -> None:
        if self._owns_session and self._db is not None:
            self._db.close()
            self._db = None
            self._owns_session = False

    def _fetch_overlapping_events(
        self,
        provider_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[Any]:
        ClinicianCalendarEvent = _import_clinician_calendar_event()
        token = str(provider_id or "").strip()
        if not token:
            raise ValueError("provider_id is required")

        start = _utc(start_time)
        end = _utc(end_time)
        if end <= start:
            raise ValueError("end_time must be after start_time")

        try:
            rows = (
                self.db.query(ClinicianCalendarEvent)
                .filter(ClinicianCalendarEvent.provider_id == token)
                .filter(ClinicianCalendarEvent.start_time < end)
                .filter(ClinicianCalendarEvent.end_time > start)
                .order_by(ClinicianCalendarEvent.start_time.asc())
                .all()
            )
        except SQLAlchemyError as exc:
            raise ScheduleConflictValidatorHardStop("calendar_overlap_query_failed") from exc

        overlapping: list[Any] = []
        for row in rows:
            if _intervals_overlap(start, end, row.start_time, row.end_time):
                overlapping.append(row)
        return overlapping

    def _resolve_provider(self, provider_token: str) -> Any | None:
        from app.models import MarylandProvider

        token = str(provider_token or "").strip()
        if not token:
            return None
        try:
            provider_uuid = UUID(token)
        except ValueError:
            provider_uuid = None
        if provider_uuid is not None:
            row = (
                self.db.query(MarylandProvider)
                .filter(MarylandProvider.provider_id == provider_uuid)
                .first()
            )
            if row is not None:
                return row
        return (
            self.db.query(MarylandProvider)
            .filter(MarylandProvider.md_license_number.ilike(token))
            .first()
        )

    def _evaluate_fatigue_clearance(self, provider_token: str) -> dict[str, Any]:
        from app.config import settings

        if not settings.SCHEDULE_FATIGUE_CAP_ENABLED:
            return {
                "fatigue_blocked": False,
                "fatigue_warn": False,
                "fatigue_score": None,
            }

        provider = self._resolve_provider(provider_token)
        if provider is None:
            return {
                "fatigue_blocked": False,
                "fatigue_warn": False,
                "fatigue_score": None,
            }

        score = float(provider.fatigue_score or 0)
        hard_threshold = float(settings.SCHEDULE_FATIGUE_HARD_BLOCK_THRESHOLD)
        soft_threshold = float(settings.SCHEDULE_FATIGUE_SOFT_WARN_THRESHOLD)
        if score >= hard_threshold:
            logger.warning(
                "HIVE_TIME_SENTINEL: fatigue hard cap provider=%s score=%.2f threshold=%.2f",
                provider_token,
                score,
                hard_threshold,
            )
            return {
                "fatigue_blocked": True,
                "fatigue_warn": False,
                "fatigue_score": score,
            }
        if score >= soft_threshold:
            logger.info(
                "HIVE_TIME_SENTINEL: fatigue elevated provider=%s score=%.2f threshold=%.2f",
                provider_token,
                score,
                soft_threshold,
            )
            return {
                "fatigue_blocked": False,
                "fatigue_warn": True,
                "fatigue_score": score,
            }
        return {
            "fatigue_blocked": False,
            "fatigue_warn": False,
            "fatigue_score": score,
        }

    def is_provider_conflicted(
        self,
        provider_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Scan calendar vault rows and classify overlap severity."""
        overlapping = self._fetch_overlapping_events(provider_id, start_time, end_time)
        if not overlapping:
            return {
                "hard_conflict": False,
                "soft_conflict": False,
                "conflicting_event_id": None,
                "conflicting_event_type": None,
                "overlap_count": 0,
            }

        hard_event: Any | None = None
        soft_event: Any | None = None
        for row in overlapping:
            event_type = str(row.event_type or "").strip().upper()
            if event_type in _HARD_BLOCK_EVENT_TYPES:
                hard_event = row
                break
            if event_type == _SOFT_BLOCK_EVENT_TYPE and soft_event is None:
                soft_event = row

        if hard_event is not None:
            return {
                "hard_conflict": True,
                "soft_conflict": False,
                "conflicting_event_id": str(hard_event.id),
                "conflicting_event_type": str(hard_event.event_type),
                "overlap_count": len(overlapping),
            }

        if soft_event is not None:
            logger.info(
                "HIVE_TIME_SENTINEL: soft preference overlap provider=%s event_id=%s",
                provider_id,
                soft_event.id,
            )
            return {
                "hard_conflict": False,
                "soft_conflict": True,
                "conflicting_event_id": str(soft_event.id),
                "conflicting_event_type": str(soft_event.event_type),
                "overlap_count": len(overlapping),
            }

        return {
            "hard_conflict": False,
            "soft_conflict": False,
            "conflicting_event_id": str(overlapping[0].id),
            "conflicting_event_type": str(overlapping[0].event_type),
            "overlap_count": len(overlapping),
        }

    def evaluate_schedule_clearance(
        self,
        provider_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Return structured schedule clearance payload for dispatch routing."""
        scan = self.is_provider_conflicted(provider_id, start_time, end_time)
        fatigue = self._evaluate_fatigue_clearance(provider_id)
        fatigue_score = fatigue.get("fatigue_score")

        if scan["hard_conflict"]:
            return {
                "has_conflict": True,
                "conflict_type": _CONFLICT_HARD,
                "conflicting_event_id": scan["conflicting_event_id"],
                "fatigue_score": fatigue_score,
            }
        if fatigue["fatigue_blocked"]:
            return {
                "has_conflict": True,
                "conflict_type": _CONFLICT_FATIGUE_HARD,
                "conflicting_event_id": None,
                "fatigue_score": fatigue_score,
            }
        if scan["soft_conflict"]:
            return {
                "has_conflict": False,
                "conflict_type": _CONFLICT_SOFT,
                "conflicting_event_id": scan["conflicting_event_id"],
                "fatigue_score": fatigue_score,
            }
        if fatigue["fatigue_warn"]:
            return {
                "has_conflict": False,
                "conflict_type": _CONFLICT_FATIGUE_SOFT,
                "conflicting_event_id": None,
                "fatigue_score": fatigue_score,
            }
        return {
            "has_conflict": False,
            "conflict_type": _CONFLICT_CLEAR,
            "conflicting_event_id": None,
            "fatigue_score": fatigue_score,
        }


if __name__ == "__main__":
    print("COMPILE_OK schedule_conflict_validator")
    start_a = datetime(2026, 6, 27, 7, 0, tzinfo=timezone.utc)
    end_a = datetime(2026, 6, 27, 15, 0, tzinfo=timezone.utc)
    start_b = datetime(2026, 6, 27, 14, 30, tzinfo=timezone.utc)
    end_b = datetime(2026, 6, 27, 22, 30, tzinfo=timezone.utc)
    start_c = datetime(2026, 6, 28, 7, 0, tzinfo=timezone.utc)
    end_c = datetime(2026, 6, 28, 15, 0, tzinfo=timezone.utc)
    print(f"overlap_detected={_intervals_overlap(start_a, end_a, start_b, end_b)}")
    print(f"clear_window={not _intervals_overlap(start_a, end_a, start_c, end_c)}")
    validator = ScheduleConflictValidator(db=None)
    print(f"validator={validator.__class__.__name__}")
