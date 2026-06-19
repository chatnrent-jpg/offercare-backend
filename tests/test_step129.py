"""PostGIS native geo matching (step 129)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import MarylandFacility, MarylandProvider, OfferCareJobOffer
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.credentialing_pipeline import run_full_credentialing_screen
from app.services.geo_matching import haversine_miles, list_geo_matched_providers_for_offer
from app.services.postgis_geo import describe_postgis_status, postgis_geo_ready


def _create_provider(
    db: Session,
    *,
    full_name: str = "Near Nurse",
    latitude: float | None = None,
    longitude: float | None = None,
) -> MarylandProvider:
    token = uuid4().hex[:10].upper()
    license_number = f"CNA{token}"
    digits = "".join(ch for ch in license_number if ch.isdigit())[-10:].rjust(10, "7")
    email = f"geo.{token.lower()}@example.com"
    provider = MarylandProvider(
        full_name=full_name,
        email=email,
        phone_number=f"+1{digits}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=license_number,
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="UNVERIFIED",
        min_hourly_rate=25.0,
        response_propensity=0.8,
        fatigue_score=0.0,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(provider)
    db.flush()
    return provider


def test_postgis_status_shape(client: TestClient) -> None:
    overview = client.get("/api/compliance/overview?limit=5").json()
    assert "postgis_enabled" in overview
    assert "postgis_version" in overview
    assert isinstance(overview["postgis_enabled"], bool)


def test_geo_matches_within_radius(client: TestClient) -> None:
    token = uuid4().hex
    facility_lat = 38.9 + (int(token[:4], 16) % 500) / 10000.0
    facility_lon = -77.4 - (int(token[4:8], 16) % 500) / 10000.0
    db = SessionLocal()
    try:
        facility = MarylandFacility(
            name=f"Geo Facility {token[:6]}",
            facility_type="NURSING_HOME",
            county="Baltimore",
            state="MD",
            latitude=facility_lat,
            longitude=facility_lon,
        )
        db.add(facility)
        db.flush()
        offer = OfferCareJobOffer(
            facility_id=facility.facility_id,
            shift_role="CNA",
            hourly_pay_rate=32.0,
            compliance_lock_status="BROADCASTING",
        )
        db.add(offer)
        near = _create_provider(
            db,
            latitude=facility_lat + 0.004,
            longitude=facility_lon + 0.002,
        )
        far = _create_provider(
            db,
            full_name="Far Nurse",
            latitude=39.9500,
            longitude=-75.1600,
        )
        run_full_credentialing_screen(db, near.provider_id)
        run_full_credentialing_screen(db, far.provider_id)
        db.commit()
        offer_id = offer.offer_id
        near_id = str(near.provider_id)
        far_id = str(far.provider_id)
    finally:
        db.close()

    response = client.get(f"/api/compliance/offers/{offer_id}/geo-matches?radius_miles=15")
    assert response.status_code == 200
    body = response.json()
    ids = {row["provider_id"] for row in body}
    assert near_id in ids
    assert far_id not in ids
    if postgis_geo_ready(SessionLocal()):
        near_row = next(row for row in body if row["provider_id"] == near_id)
        assert near_row["distance_miles"] is not None
        assert near_row["distance_miles"] < 15


def test_geo_matches_haversine_fallback_when_postgis_disabled(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "GEO_MATCH_USE_POSTGIS", False)
    token = uuid4().hex
    facility_lat = 38.8 + (int(token[:4], 16) % 500) / 10000.0
    facility_lon = -77.5 - (int(token[4:8], 16) % 500) / 10000.0

    db = SessionLocal()
    try:
        facility = MarylandFacility(
            name=f"Fallback Facility {token[:6]}",
            facility_type="NURSING_HOME",
            county="Baltimore",
            state="MD",
            latitude=facility_lat,
            longitude=facility_lon,
        )
        db.add(facility)
        db.flush()
        offer = OfferCareJobOffer(
            facility_id=facility.facility_id,
            shift_role="CNA",
            hourly_pay_rate=30.0,
            compliance_lock_status="BROADCASTING",
        )
        db.add(offer)
        near = _create_provider(
            db,
            latitude=facility_lat + 0.004,
            longitude=facility_lon + 0.002,
        )
        run_full_credentialing_screen(db, near.provider_id)
        db.commit()
        rows = list_geo_matched_providers_for_offer(db, offer.offer_id, radius_miles=15, limit=50)
        assert any(row["provider_id"] == str(near.provider_id) for row in rows)
    finally:
        db.close()


def test_haversine_distance_reasonable() -> None:
    distance = haversine_miles(39.2904, -76.6122, 39.2950, -76.6100)
    assert 0 < distance < 5


def test_deploy_checklist_includes_postgis_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "postgis_geo")
    assert item["status"] in {"ready", "warning"}
    assert "PostGIS" in item["detail"] or "Haversine" in item["detail"]


def test_describe_postgis_status() -> None:
    db = SessionLocal()
    try:
        status = describe_postgis_status(db)
        assert "postgis_enabled" in status
        assert "postgis_columns_ready" in status
        assert status["postgis_enabled"] == postgis_geo_ready(db)
    finally:
        db.close()
