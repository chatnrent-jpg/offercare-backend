"""Filter open shifts to those a clinician can staff."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import MarylandProvider
from app.services.care_taxonomy import (
    clinician_qualifies_for_shift_role,
    credential_valid_in_state,
    provider_supports_facility_type,
)
from app.services.shift_offer_generator import list_open_shifts
from app.services.states import normalize_state
from app.shift_sniper import rate_delta


def shift_matches_provider(
    *,
    provider: MarylandProvider,
    facility_state: str,
    facility_type: str,
    shift_role: str,
    hourly_pay_rate: float,
) -> bool:
    if normalize_state(provider.state) != normalize_state(facility_state):
        return False
    if not credential_valid_in_state(provider.credential_type, provider.state):
        return False
    if not clinician_qualifies_for_shift_role(
        provider.credential_type,
        shift_role,
        facility_state=facility_state,
    ):
        return False
    if not provider_supports_facility_type(provider.service_lines, facility_type):
        return False
    return float(hourly_pay_rate) >= float(provider.min_hourly_rate or 0)


def list_matched_shifts_for_provider(
    db: Session,
    provider: MarylandProvider,
    *,
    limit: int = 50,
    state: str | None = None,
    county: str | None = None,
    facility_type: str | None = None,
    shift_role: str | None = None,
    min_pay: float | None = None,
    starts_after: datetime | None = None,
) -> list[dict]:
    rows = list_open_shifts(
        db,
        limit=max(limit * 4, 100),
        state=state or provider.state,
        county=county,
        facility_type=facility_type,
        shift_role=shift_role,
        min_pay=min_pay,
        starts_after=starts_after,
    )
    matched: list[dict] = []
    for row in rows:
        if not shift_matches_provider(
            provider=provider,
            facility_state=str(row["state"]),
            facility_type=str(row["facility_type"]),
            shift_role=str(row["shift_role"]),
            hourly_pay_rate=float(row["hourly_pay_rate"]),
        ):
            continue
        pay_delta = rate_delta(
            shift_pay=float(row["hourly_pay_rate"]),
            min_rate=float(provider.min_hourly_rate or 0),
        )
        matched.append({**row, "rate_delta": round(pay_delta, 2)})
        if len(matched) >= limit:
            break
    return matched


def get_matched_shift_for_provider(
    db: Session,
    provider: MarylandProvider,
    offer_id: UUID,
) -> dict | None:
    from app.services.shift_offer_generator import get_open_shift_by_id

    row = get_open_shift_by_id(db, offer_id)
    if row is None:
        return None
    if not shift_matches_provider(
        provider=provider,
        facility_state=str(row["state"]),
        facility_type=str(row["facility_type"]),
        shift_role=str(row["shift_role"]),
        hourly_pay_rate=float(row["hourly_pay_rate"]),
    ):
        return None
    pay_delta = rate_delta(
        shift_pay=float(row["hourly_pay_rate"]),
        min_rate=float(provider.min_hourly_rate or 0),
    )
    return {**row, "rate_delta": round(pay_delta, 2)}
