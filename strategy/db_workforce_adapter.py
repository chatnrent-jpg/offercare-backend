"""Map PostgreSQL and staging registry rows to unified strategy candidate dicts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import MdProviderCompliance, MarylandFacility, MarylandProvider
from app.services.compliance_monitor import provider_dispatch_eligible
from app.services.vetted_status import VETTED_CLEAR, compute_vetted_status


def _normalize_county(value: str) -> str:
    return re.sub(r"\s+county\s*$", "", str(value or "").strip(), flags=re.IGNORECASE).lower()


def _normalize_facility_type_for_shift(facility_type: str) -> str:
    token = str(facility_type or "").strip().upper()
    if token in {"NURSING_HOME", "SKILLED_NURSING", "LTC", "LONG_TERM_CARE"}:
        return "SNF"
    if token in {"ASSISTED_LIVING", "ALF"}:
        return "ALF"
    return token


def candidates_from_registry(workforce_registry: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for applicant in workforce_registry.get("applicants") or []:
        verification_ts = str(applicant.get("verification_timestamp") or "").strip()
        if not verification_ts:
            continue
        candidates.append(
            {
                "provider_id": applicant.get("license_number") or applicant.get("name"),
                "full_name": applicant.get("name"),
                "role": str(applicant.get("license_type") or "").upper(),
                "county": applicant.get("county"),
                "has_gna_endorsement": bool(applicant.get("has_gna_endorsement")),
                "license_verified_at": verification_ts,
                "background_check_verified_at": verification_ts,
                "placement_eligible": bool(applicant.get("placement_eligible")),
            }
        )
    return candidates


def provider_to_candidate(
    provider: MarylandProvider,
    compliance: MdProviderCompliance | None,
    *,
    county: str | None = None,
    placement_eligible: bool | None = None,
) -> dict[str, Any]:
    credential = str(provider.credential_type or "").upper()
    role = "CNA" if credential in {"CNA", "GNA"} else credential
    verified = provider.last_verified_timestamp or provider.applied_at or datetime.now(timezone.utc)
    verified_iso = verified.isoformat() if hasattr(verified, "isoformat") else str(verified)
    has_gna = bool(compliance.has_gna_endorsement) if compliance else credential == "GNA"
    home_county = county or (compliance.home_county if compliance and compliance.home_county else "")

    return {
        "provider_id": provider.md_license_number,
        "provider_uuid": str(provider.provider_id),
        "full_name": provider.full_name,
        "role": role,
        "county": home_county,
        "has_gna_endorsement": has_gna,
        "license_verified_at": verified_iso,
        "background_check_verified_at": verified_iso,
        "placement_eligible": placement_eligible if placement_eligible is not None else True,
        "response_propensity": float(provider.response_propensity or 0),
        "fatigue_score": float(provider.fatigue_score or 0),
        "min_hourly_rate": float(provider.min_hourly_rate or 0),
    }


def load_db_candidates(
    db: Session,
    *,
    facility_id: UUID | None = None,
    state: str = "MD",
    limit: int = 500,
) -> list[dict[str, Any]]:
    rows = (
        db.query(MarylandProvider, MdProviderCompliance)
        .outerjoin(MdProviderCompliance, MdProviderCompliance.provider_id == MarylandProvider.provider_id)
        .filter(MarylandProvider.state == state)
        .order_by(MarylandProvider.response_propensity.desc())
        .limit(limit)
        .all()
    )

    candidates: list[dict[str, Any]] = []
    for provider, compliance in rows:
        if compute_vetted_status(db, provider) != VETTED_CLEAR:
            continue
        if not provider_dispatch_eligible(db, provider):
            continue
        county_override = compliance.home_county if compliance and compliance.home_county else None
        candidates.append(
            provider_to_candidate(
                provider,
                compliance,
                county=county_override,
                placement_eligible=True,
            )
        )
    return candidates


def shift_request_from_facility(
    facility: MarylandFacility,
    *,
    shift_role: str,
    shift_starts_at: datetime | None = None,
    hourly_pay_rate: float | None = None,
) -> dict[str, Any]:
    county_raw = facility.county or ""
    county = re.sub(r"\s+county\s*$", "", county_raw.strip(), flags=re.IGNORECASE)
    barrier = shift_starts_at or datetime.now(timezone.utc)
    if barrier.tzinfo is None:
        barrier = barrier.replace(tzinfo=timezone.utc)
    return {
        "facility_id": str(facility.facility_id),
        "facility_name": facility.name,
        "facility_type": _normalize_facility_type_for_shift(facility.facility_type),
        "required_role": str(shift_role or "").upper(),
        "county": county,
        "facility_county": county,
        "shift_timestamp": barrier.isoformat(),
        "evaluation_window_barrier": barrier.isoformat(),
        "hourly_pay_rate": hourly_pay_rate,
    }
