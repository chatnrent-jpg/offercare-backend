"""Cross-facility schedule conflict engine — isolated anti-collision math (staging)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

TRAVEL_BUFFER_MINUTES = 60


def _parse_timestamp(value: str) -> datetime:
    token = str(value or "").strip()
    if not token:
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    parsed = datetime.fromisoformat(token)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_county(county: str) -> str:
    return str(county or "").strip().lower()


class ScheduleConflictEngine:
    """Validates proposed bookings against active provider commitments."""

    def __init__(self, commitments: list[dict[str, Any]]) -> None:
        if not isinstance(commitments, list):
            raise TypeError("commitments must be a list of assignment dicts")
        self.commitments = list(commitments)

    def _commitments_for_provider_on_day(
        self,
        provider_id: str,
        calendar_day: datetime,
    ) -> list[dict[str, Any]]:
        day = calendar_day.date()
        matched: list[dict[str, Any]] = []
        for row in self.commitments:
            if str(row.get("provider_id") or "") != str(provider_id):
                continue
            start = _parse_timestamp(str(row["shift_start"]))
            if start.date() == day:
                matched.append(row)
        return matched

    @staticmethod
    def _intervals_overlap(
        start_a: datetime,
        end_a: datetime,
        start_b: datetime,
        end_b: datetime,
    ) -> bool:
        return start_a < end_b and start_b < end_a

    @staticmethod
    def _travel_buffer_violation(
        earlier_end: datetime,
        later_start: datetime,
    ) -> bool:
        gap_minutes = (later_start - earlier_end).total_seconds() / 60.0
        return gap_minutes < TRAVEL_BUFFER_MINUTES

    def validate_booking_safety(
        self,
        provider_id: str,
        proposed_shift: dict[str, Any],
    ) -> tuple[bool, str]:
        if not provider_id:
            raise ValueError("provider_id is required")
        if not isinstance(proposed_shift, dict):
            raise TypeError("proposed_shift must be a dict")

        proposed_start = _parse_timestamp(str(proposed_shift["shift_start"]))
        proposed_end = _parse_timestamp(str(proposed_shift["shift_end"]))
        if proposed_end <= proposed_start:
            raise ValueError("proposed_shift end must be after start")

        proposed_county = _normalize_county(str(proposed_shift.get("county") or ""))
        existing_rows = self._commitments_for_provider_on_day(provider_id, proposed_start)

        for existing in existing_rows:
            existing_start = _parse_timestamp(str(existing["shift_start"]))
            existing_end = _parse_timestamp(str(existing["shift_end"]))
            existing_county = _normalize_county(str(existing.get("county") or ""))

            if self._intervals_overlap(
                proposed_start,
                proposed_end,
                existing_start,
                existing_end,
            ):
                return (
                    False,
                    "CRITICAL_COLLISION: Provider already committed to overlapping hours at another facility.",
                )

            if proposed_county and existing_county and proposed_county != existing_county:
                if existing_end <= proposed_start:
                    if self._travel_buffer_violation(existing_end, proposed_start):
                        return (
                            False,
                            "BUFFER_VIOLATION: Insufficient cross-county transit buffer.",
                        )
                elif proposed_end <= existing_start:
                    if self._travel_buffer_violation(proposed_end, existing_start):
                        return (
                            False,
                            "BUFFER_VIOLATION: Insufficient cross-county transit buffer.",
                        )

        return True, "BOOKING_SAFE"


def _mock_commitments() -> list[dict[str, Any]]:
    """Active assignments aligned to staging provider + shift identifiers."""
    return [
        {
            "provider_id": "CNA-MD-88421",
            "provider_name": "Aisha Thompson",
            "order_id": "eb1ac566-7331-4af0-aa14-6a7077614773",
            "facility_name": "Arbor Ridge at Riderwood",
            "county": "Montgomery",
            "shift_start": "2026-06-27T07:00:00+00:00",
            "shift_end": "2026-06-27T15:00:00+00:00",
        }
    ]


if __name__ == "__main__":
    engine = ScheduleConflictEngine(_mock_commitments())

    # Safe: same provider, different day.
    safe_shift = {
        "shift_start": "2026-06-28T07:00:00+00:00",
        "shift_end": "2026-06-28T15:00:00+00:00",
        "county": "Montgomery",
        "facility_name": "FutureCare Northpoint",
    }
    ok, reason = engine.validate_booking_safety("CNA-MD-88421", safe_shift)
    assert ok is True
    assert reason == "BOOKING_SAFE"

    # Collision: overlaps existing Montgomery shift on 2026-06-27.
    collision_shift = {
        "shift_start": "2026-06-27T14:30:00+00:00",
        "shift_end": "2026-06-27T22:30:00+00:00",
        "county": "Montgomery",
        "facility_name": "Autumn Lake Healthcare at Arlington West",
    }
    ok, reason = engine.validate_booking_safety("CNA-MD-88421", collision_shift)
    assert ok is False
    assert reason.startswith("CRITICAL_COLLISION")

    # Buffer violation: different county, only 30 minutes between shifts.
    buffer_fail_shift = {
        "shift_start": "2026-06-27T15:30:00+00:00",
        "shift_end": "2026-06-27T23:30:00+00:00",
        "county": "Baltimore",
        "facility_name": "Anchorage Healthcare Center",
    }
    ok, reason = engine.validate_booking_safety("CNA-MD-88421", buffer_fail_shift)
    assert ok is False
    assert reason.startswith("BUFFER_VIOLATION")

    # Buffer pass: different county, 90-minute travel window.
    buffer_pass_shift = {
        "shift_start": "2026-06-27T16:30:00+00:00",
        "shift_end": "2026-06-28T00:30:00+00:00",
        "county": "Baltimore",
        "facility_name": "Anchorage Healthcare Center",
    }
    ok, reason = engine.validate_booking_safety("CNA-MD-88421", buffer_pass_shift)
    assert ok is True
    assert reason == "BOOKING_SAFE"

    print("ScheduleConflictEngine self-test passed.")
    print("  safe booking -> BOOKING_SAFE")
    print("  overlap -> CRITICAL_COLLISION")
    print("  30m cross-county gap -> BUFFER_VIOLATION")
    print("  90m cross-county gap -> BOOKING_SAFE")
