"""Explicit shift start/end scheduling helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings
from app.models import OfferCareJobOffer

_GRID_TZ = ZoneInfo("America/New_York")


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def default_shift_window(
    anchor: datetime | None = None,
    *,
    duration_hours: float | None = None,
) -> tuple[datetime, datetime]:
    """Next grid morning block in Eastern time."""
    hours = duration_hours if duration_hours is not None else settings.SHIFT_CALENDAR_DURATION_HOURS
    posted = _as_utc(anchor)
    local = posted.astimezone(_GRID_TZ)
    start_local = local.replace(hour=7, minute=0, second=0, microsecond=0)
    if local.hour >= 7:
        start_local = start_local + timedelta(days=1)
    start = start_local.astimezone(timezone.utc)
    end = start + timedelta(hours=hours)
    return start, end


def resolve_offer_shift_window(
    offer: OfferCareJobOffer,
    *,
    fallback_anchor: datetime | None = None,
) -> tuple[datetime, datetime]:
    if offer.shift_starts_at is not None and offer.shift_ends_at is not None:
        return _as_utc(offer.shift_starts_at), _as_utc(offer.shift_ends_at)
    if offer.shift_starts_at is not None:
        start = _as_utc(offer.shift_starts_at)
        hours = settings.SHIFT_CALENDAR_DURATION_HOURS
        return start, start + timedelta(hours=hours)
    return default_shift_window(fallback_anchor or offer.created_at)


def apply_default_shift_schedule(
    offer: OfferCareJobOffer,
    *,
    anchor: datetime | None = None,
) -> None:
    if offer.shift_starts_at is not None and offer.shift_ends_at is not None:
        return
    start, end = default_shift_window(anchor or offer.created_at)
    offer.shift_starts_at = start
    offer.shift_ends_at = end


def format_shift_window_et(start: datetime, end: datetime) -> str:
    start_local = _as_utc(start).astimezone(_GRID_TZ)
    end_local = _as_utc(end).astimezone(_GRID_TZ)
    if start_local.date() == end_local.date():
        return (
            f"{start_local.strftime('%a %b %d, %H:%M')}–{end_local.strftime('%H:%M')} ET"
        )
    return (
        f"{start_local.strftime('%a %b %d %H:%M')} – "
        f"{end_local.strftime('%a %b %d %H:%M')} ET"
    )


def validate_shift_window(*, shift_starts_at: datetime, shift_ends_at: datetime) -> tuple[datetime, datetime]:
    start = _as_utc(shift_starts_at)
    end = _as_utc(shift_ends_at)
    if end <= start:
        raise ValueError("invalid_schedule_window")
    return start, end


def set_offer_shift_schedule(
    offer: OfferCareJobOffer,
    *,
    shift_starts_at: datetime,
    shift_ends_at: datetime,
) -> tuple[datetime, datetime]:
    start, end = validate_shift_window(shift_starts_at=shift_starts_at, shift_ends_at=shift_ends_at)
    offer.shift_starts_at = start
    offer.shift_ends_at = end
    return start, end
