"""Lookahead shift matcher — PostgreSQL path via unified strategy core."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import FacilityContract, MarylandFacility
from app.services.vetted_status import VETTED_CLEAR
from app.shift_sniper import rate_delta
from strategy.db_workforce_adapter import shift_request_from_facility
from strategy.unified_shift_matcher import UnifiedShiftMatcher


def _contract_for_facility(db: Session, facility_id: UUID) -> FacilityContract | None:
    return (
        db.query(FacilityContract)
        .filter(
            FacilityContract.facility_id == facility_id,
            FacilityContract.review_status == "ACTIVE",
            FacilityContract.dispatch_halted == "false",
        )
        .order_by(FacilityContract.parsed_at.desc())
        .first()
    )


def _legacy_row(match: dict[str, Any], *, shift_role: str, hourly_pay_rate: float, facility_id: UUID) -> dict[str, Any]:
    score = (
        float(match.get("response_propensity") or 0) * 100
        - float(match.get("fatigue_score") or 0) * 5
        + rate_delta(
            shift_pay=float(hourly_pay_rate),
            min_rate=float(match.get("min_hourly_rate") or 0),
        )
    )
    return {
        "provider_id": match.get("provider_uuid") or match.get("provider_id"),
        "full_name": match.get("full_name"),
        "credential_type": match.get("role"),
        "vetted_status": VETTED_CLEAR,
        "hourly_pay_rate": float(hourly_pay_rate),
        "match_score": round(score, 2),
        "shift_role": shift_role,
        "facility_id": str(facility_id),
        "shift_starts_at": match.get("_match_meta", {}).get("evaluation_barrier_utc"),
        "matched_at": datetime.now(timezone.utc).isoformat(),
        "matcher_source": match.get("_match_meta", {}).get("matcher_source", "postgresql"),
        "matcher_core": match.get("_match_meta", {}).get("matcher_core"),
        "county_match": match.get("_match_meta", {}).get("county_match"),
    }


def match_top_providers_for_shift(
    db: Session,
    *,
    facility_id: UUID,
    shift_role: str,
    hourly_pay_rate: float,
    shift_starts_at: datetime | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return top N providers using the same core rules as staging desk orchestrator."""
    facility = db.query(MarylandFacility).filter(MarylandFacility.facility_id == facility_id).first()
    if facility is None:
        return []

    contract = _contract_for_facility(db, facility_id)
    if contract is not None and contract.dispatch_halted == "true":
        return []

    shift_request = shift_request_from_facility(
        facility,
        shift_role=shift_role,
        shift_starts_at=shift_starts_at,
        hourly_pay_rate=hourly_pay_rate,
    )
    evaluation_ts = datetime.now(timezone.utc).isoformat()
    matcher = UnifiedShiftMatcher.from_database(db, facility_id=facility_id)
    matches = matcher.find_compliant_matches(shift_request, evaluation_ts)

    scored: list[dict[str, Any]] = []
    for match in matches:
        if float(hourly_pay_rate) < float(match.get("min_hourly_rate") or 0):
            continue
        scored.append(
            _legacy_row(
                match,
                shift_role=shift_role,
                hourly_pay_rate=hourly_pay_rate,
                facility_id=facility_id,
            )
        )

    scored.sort(key=lambda row: float(row["match_score"]), reverse=True)
    return scored[: max(1, int(limit))]
