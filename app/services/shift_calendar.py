"""Build iCalendar (.ics) feeds for placements and open shifts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.services.shift_schedule import resolve_offer_shift_window


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return _utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_ics_datetime(value: datetime) -> str:
    return _as_utc(value).strftime("%Y%m%dT%H%M%SZ")


def _escape_ics_text(value: str) -> str:
    text = str(value or "")
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold_ics_line(line: str) -> str:
    if len(line) <= 75:
        return line
    parts = [line[:75]]
    rest = line[75:]
    while rest:
        parts.append(" " + rest[:74])
        rest = rest[74:]
    return "\r\n".join(parts)


def _row_shift_window(row: dict[str, Any]) -> tuple[datetime, datetime]:
    start = row.get("shift_starts_at")
    end = row.get("shift_ends_at")
    if start is not None and end is not None:
        return _as_utc(start), _as_utc(end)
    from app.models import OfferCareJobOffer

    offer = OfferCareJobOffer(
        shift_starts_at=start,
        shift_ends_at=end,
        created_at=row.get("created_at") or row.get("outbound_payload_timestamp"),
    )
    return resolve_offer_shift_window(offer, fallback_anchor=row.get("outbound_payload_timestamp"))


def build_calendar_event(
    *,
    uid: str,
    summary: str,
    description: str,
    location: str,
    dtstart: datetime,
    dtend: datetime,
    status: str = "CONFIRMED",
) -> str:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{_escape_ics_text(uid)}",
        f"DTSTAMP:{_format_ics_datetime(_utc_now())}",
        f"DTSTART:{_format_ics_datetime(dtstart)}",
        f"DTEND:{_format_ics_datetime(dtend)}",
        f"SUMMARY:{_escape_ics_text(summary)}",
        f"DESCRIPTION:{_escape_ics_text(description)}",
        f"LOCATION:{_escape_ics_text(location)}",
        f"STATUS:{status}",
        "END:VEVENT",
    ]
    return "\r\n".join(_fold_ics_line(line) for line in lines)


def build_ics_calendar(*, calendar_name: str, events: list[str]) -> str:
    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//VettedCare.ai//Grid//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_ics_text(calendar_name)}",
    ]
    footer = ["END:VCALENDAR"]
    body = header + events + footer
    return "\r\n".join(_fold_ics_line(line) for line in body) + "\r\n"


def _placement_calendar_events(rows: list[dict[str, Any]]) -> list[str]:
    events: list[str] = []
    for row in rows:
        placement_id = row["placement_id"]
        start, end = _row_shift_window(row)
        summary = f"{row['clinical_unit']} @ {row['facility_name']}"
        description = (
            f"Locked VettedCare.ai placement\\n"
            f"Rate: ${float(row['hourly_bill_rate']):.2f}/hr\\n"
            f"VMS: {row.get('vms_submission_status', 'PENDING')}"
        )
        events.append(
            build_calendar_event(
                uid=f"placement-{placement_id}@offercare.ai",
                summary=summary,
                description=description,
                location=f"{row['facility_name']}",
                dtstart=start,
                dtend=end,
                status="CONFIRMED",
            )
        )
    return events


def _schedule_calendar_events(rows: list[dict[str, Any]]) -> list[str]:
    events: list[str] = []
    for row in rows:
        event_id = row.get("event_id") or row.get("id")
        event_type = str(row.get("event_type") or "EVENT").upper()
        start = _as_utc(row.get("start_time"))
        end = _as_utc(row.get("end_time"))
        facility = str(row.get("facility_name") or "").strip()
        role = str(row.get("shift_role") or "").strip()

        if event_type == "SHIFT_COMMITMENT":
            summary = f"{role or 'Shift'} @ {facility or 'Facility'}"
            description = "Locked shift commitment on VettedCare.ai"
            status = "CONFIRMED"
        elif event_type == "BLACKOUT_UNAVAILABLE":
            summary = "Blackout — not available"
            description = "Clinician blackout block"
            status = "CONFIRMED"
        elif event_type == "SOFT_BLOCK_PREFERENCE":
            summary = "Soft preference block"
            description = "Clinician soft scheduling preference"
            status = "TENTATIVE"
        else:
            summary = event_type.replace("_", " ").title()
            description = event_type
            status = "TENTATIVE"

        location = facility or "VettedCare.ai"
        events.append(
            build_calendar_event(
                uid=f"schedule-{event_id}@offercare.ai",
                summary=summary,
                description=description,
                location=location,
                dtstart=start,
                dtend=end,
                status=status,
            )
        )
    return events


def placements_to_ics(rows: list[dict[str, Any]]) -> str:
    return build_ics_calendar(
        calendar_name="VettedCare.ai Placements",
        events=_placement_calendar_events(rows),
    )


def open_shifts_to_ics(rows: list[dict[str, Any]]) -> str:
    events: list[str] = []
    for row in rows:
        offer_id = row["offer_id"]
        start, end = _row_shift_window(row)
        summary = f"{row['shift_role']} @ {row['facility_name']}"
        description = (
            f"Open shift on VettedCare.ai\\n"
            f"Pay: ${float(row['hourly_pay_rate']):.2f}/hr\\n"
            f"Reply YES via SMS to lock."
        )
        location = f"{row['facility_name']}, {row.get('county', '')}, {row.get('state', 'MD')}"
        events.append(
            build_calendar_event(
                uid=f"offer-{offer_id}@offercare.ai",
                summary=summary,
                description=description,
                location=location,
                dtstart=start,
                dtend=end,
                status="TENTATIVE",
            )
        )
    return build_ics_calendar(calendar_name="VettedCare.ai Open Shifts", events=events)


def placement_calendar_filename(provider_id: UUID) -> str:
    return f"offercare-placements-{str(provider_id)[:8]}.ics"


def open_shifts_calendar_filename(*, prefix: str = "offercare-open-shifts") -> str:
    token = prefix if prefix.endswith(".ics") else f"{prefix}.ics"
    return token


def schedule_events_to_ics(rows: list[dict[str, Any]], *, calendar_token: str = "clinician") -> str:
    safe_token = str(calendar_token or "clinician").replace(" ", "-")[:32]
    return build_ics_calendar(
        calendar_name=f"VettedCare.ai Schedule ({safe_token})",
        events=_schedule_calendar_events(rows),
    )


def unified_clinician_calendar_to_ics(
    *,
    placements: list[dict[str, Any]],
    schedule_events: list[dict[str, Any]],
    calendar_token: str = "clinician",
) -> str:
    safe_token = str(calendar_token or "clinician").replace(" ", "-")[:32]
    events = _placement_calendar_events(placements) + _schedule_calendar_events(schedule_events)
    return build_ics_calendar(
        calendar_name=f"VettedCare.ai — Placements & Schedule ({safe_token})",
        events=events,
    )


def unified_calendar_filename(calendar_token: str) -> str:
    safe = str(calendar_token or "clinician").replace(" ", "-")[:32]
    return f"offercare-full-calendar-{safe}.ics"


def schedule_calendar_filename(calendar_token: str) -> str:
    safe = str(calendar_token or "clinician").replace(" ", "-")[:32]
    return f"offercare-schedule-{safe}.ics"
