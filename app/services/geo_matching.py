"""Geographic proximity matching for Maryland shift dispatch."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandFacility, MarylandProvider, OfferCareJobOffer
from app.services.compliance_monitor import provider_dispatch_eligible
from app.services.postgis_geo import postgis_geo_ready, query_provider_geo_candidates
from app.services.shift_matching import shift_matches_provider


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius_miles * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _coords(row: Any) -> tuple[float, float] | None:
    if row.latitude is None or row.longitude is None:
        return None
    return float(row.latitude), float(row.longitude)


def _append_candidate(
    candidates: list[dict],
    provider: MarylandProvider,
    distance: float | None,
) -> None:
    candidates.append(
        {
            "provider_id": str(provider.provider_id),
            "full_name": provider.full_name,
            "credential_type": provider.credential_type,
            "dispatch_status": provider.dispatch_status,
            "distance_miles": round(distance, 2) if distance is not None else None,
        }
    )


def _list_geo_matches_python(
    db: Session,
    *,
    facility: MarylandFacility,
    offer: OfferCareJobOffer,
    max_radius: float,
) -> list[dict]:
    facility_coords = _coords(facility)
    candidates: list[dict] = []

    for provider in db.query(MarylandProvider).filter(MarylandProvider.state == facility.state).all():
        if not provider_dispatch_eligible(db, provider):
            continue
        if not shift_matches_provider(
            provider=provider,
            facility_state=facility.state,
            facility_type=facility.facility_type,
            shift_role=offer.shift_role,
            hourly_pay_rate=float(offer.hourly_pay_rate),
        ):
            continue
        provider_coords = _coords(provider)
        if facility_coords and provider_coords:
            distance = haversine_miles(
                facility_coords[0],
                facility_coords[1],
                provider_coords[0],
                provider_coords[1],
            )
            if distance > max_radius:
                continue
        else:
            distance = None
        _append_candidate(candidates, provider, distance)

    candidates.sort(key=lambda row: row["distance_miles"] if row["distance_miles"] is not None else 9999)
    return candidates


def _list_geo_matches_postgis(
    db: Session,
    *,
    facility: MarylandFacility,
    offer: OfferCareJobOffer,
    max_radius: float,
) -> list[dict]:
    facility_coords = _coords(facility)
    if not facility_coords:
        return _list_geo_matches_python(db, facility=facility, offer=offer, max_radius=max_radius)

    candidates: list[dict] = []
    for row in query_provider_geo_candidates(
        db,
        facility_longitude=facility_coords[1],
        facility_latitude=facility_coords[0],
        state=facility.state,
        radius_miles=max_radius,
    ):
        provider = (
            db.query(MarylandProvider)
            .filter(MarylandProvider.provider_id == row["provider_id"])
            .first()
        )
        if provider is None:
            continue
        if not provider_dispatch_eligible(db, provider):
            continue
        if not shift_matches_provider(
            provider=provider,
            facility_state=facility.state,
            facility_type=facility.facility_type,
            shift_role=offer.shift_role,
            hourly_pay_rate=float(offer.hourly_pay_rate),
        ):
            continue
        distance = float(row["distance_miles"]) if row["distance_miles"] is not None else None
        _append_candidate(candidates, provider, distance)

    candidates.sort(key=lambda item: item["distance_miles"] if item["distance_miles"] is not None else 9999)
    return candidates


def list_geo_matched_providers_for_offer(
    db: Session,
    offer_id,
    *,
    radius_miles: float | None = None,
    limit: int = 5,
) -> list[dict]:
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    if offer is None:
        raise ValueError("offer_not_found")
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id == offer.facility_id)
        .first()
    )
    if facility is None:
        raise ValueError("facility_not_found")

    max_radius = float(radius_miles or settings.GEO_MATCH_RADIUS_MILES)
    if postgis_geo_ready(db):
        candidates = _list_geo_matches_postgis(
            db,
            facility=facility,
            offer=offer,
            max_radius=max_radius,
        )
    else:
        candidates = _list_geo_matches_python(
            db,
            facility=facility,
            offer=offer,
            max_radius=max_radius,
        )
    return candidates[:limit]
