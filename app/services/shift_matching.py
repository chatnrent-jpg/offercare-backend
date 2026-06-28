"""Filter open shifts to those a clinician can staff."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandProvider
from app.services.care_taxonomy import (
    clinician_qualifies_for_shift_role,
    credential_valid_in_state,
    provider_supports_facility_type,
)
from app.services.shift_offer_generator import list_open_shifts
from app.services.states import normalize_state
from app.shift_sniper import rate_delta

logger = logging.getLogger(__name__)


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


def _shift_context_from_open_shift(row: dict) -> dict:
    starts_at = row.get("shift_starts_at")
    ends_at = row.get("shift_ends_at")
    return {
        "offer_id": str(row.get("offer_id") or ""),
        "shift_id": str(row.get("offer_id") or ""),
        "facility_id": str(row.get("facility_id") or ""),
        "facility_name": str(row.get("facility_name") or ""),
        "facility_county": str(row.get("county") or ""),
        "county": str(row.get("county") or ""),
        "state": str(row.get("state") or ""),
        "shift_role": str(row.get("shift_role") or ""),
        "facility_type": str(row.get("facility_type") or ""),
        "hourly_pay_rate": float(row.get("hourly_pay_rate") or 0),
        "shift_starts_at": starts_at.isoformat() if isinstance(starts_at, datetime) else starts_at,
        "shift_ends_at": ends_at.isoformat() if isinstance(ends_at, datetime) else ends_at,
    }


def _provider_in_broker_matches(provider: MarylandProvider, matches: list[dict]) -> bool:
    provider_uuid = str(provider.provider_id)
    license_token = str(provider.md_license_number or "").strip().upper()
    for match in matches:
        candidate_id = str(match.get("provider_id") or "").strip()
        license_number = str(match.get("license_number") or "").strip().upper()
        if candidate_id == provider_uuid:
            return True
        if license_token and license_number == license_token:
            return True
        if license_token and candidate_id.upper() == license_token:
            return True
    return False


def _broker_confirms_provider_match(
    db: Session,
    provider: MarylandProvider,
    row: dict,
) -> bool:
    if not settings.UNIFIED_MATCH_MATRIX_BROKER_ENABLED:
        return True
    try:
        from strategy.unified_match_matrix_broker import UnifiedMatchMatrixBroker

        shift_id = str(row.get("offer_id") or "")
        if not shift_id:
            return False
        broker = UnifiedMatchMatrixBroker(db=db)
        try:
            result = broker.resolve_canonical_shift_matches(
                shift_id,
                _shift_context_from_open_shift(row),
            )
        finally:
            broker.close()
        if not result.get("ok"):
            return False
        return _provider_in_broker_matches(provider, list(result.get("matches") or []))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "shift_matching: broker gate fail-open provider=%s offer=%s error=%s",
            provider.provider_id,
            row.get("offer_id"),
            exc,
        )
        return True


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
        if not _broker_confirms_provider_match(db, provider, row):
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
    if not _broker_confirms_provider_match(db, provider, row):
        return None
    pay_delta = rate_delta(
        shift_pay=float(row["hourly_pay_rate"]),
        min_rate=float(provider.min_hourly_rate or 0),
    )
    return {**row, "rate_delta": round(pay_delta, 2)}
