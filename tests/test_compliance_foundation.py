from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.database import SessionLocal
from app.models import ClinicianComplianceDocument, MarylandFacility, MarylandProvider, OfferCareJobOffer
from app.services.compliance_monitor import run_compliance_monitor
from app.services.credentialing_pipeline import run_full_credentialing_screen
from app.services.shift_ranking import rank_offer_from_db


def _create_provider(
    db: Session,
    *,
    full_name: str = "Jane CNA",
    license_number: str | None = None,
    credential_type: str = "CNA",
    latitude: float | None = None,
    longitude: float | None = None,
) -> MarylandProvider:
    token = uuid4().hex[:10].upper()
    license_number = license_number or f"CNA{token}"
    digits = "".join(ch for ch in license_number if ch.isdigit())[-10:].rjust(10, "7")
    email = f"compliance.{token.lower()}@example.com"
    provider = MarylandProvider(
        full_name=full_name,
        email=email,
        phone_number=f"+1{digits}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=license_number,
        state="MD",
        credential_type=credential_type,
        service_lines="NURSING_HOME",
        license_status="UNVERIFIED",
        min_hourly_rate=25.0,
        response_propensity=0.8,
        fatigue_score=0.0,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def test_credentialing_screen_passes_active_license(client: TestClient) -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        provider_id = provider.provider_id
    finally:
        db.close()

    response = client.post(f"/api/compliance/providers/{provider_id}/screen")
    assert response.status_code == 200
    body = response.json()
    assert body["mbon_status"] == "ACTIVE"
    assert body["oig_status"] == "CLEAR"
    assert body["judiciary_status"] == "CLEAR"
    assert body["license_status"] == "VERIFIED"
    assert body["dispatch_status"] == "ACTIVE"
    assert body["blocked"] is False


def test_credentialing_screen_blocks_excluded_name(client: TestClient) -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db, full_name="Mary EXCLUDED")
        provider_id = provider.provider_id
    finally:
        db.close()

    response = client.post(f"/api/compliance/providers/{provider_id}/screen")
    body = response.json()
    assert body["oig_status"] == "EXCLUDED"
    assert body["blocked"] is True
    assert body["dispatch_status"] == "SUSPENDED"


def test_compliance_monitor_suspends_expired_documents(client: TestClient) -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        provider_id = provider.provider_id
        run_full_credentialing_screen(db, provider_id)
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        for row in db.query(ClinicianComplianceDocument).filter_by(provider_id=provider_id):
            row.expires_on = expired
        db.commit()
        result = run_compliance_monitor(db)
        refreshed = db.query(MarylandProvider).filter_by(provider_id=provider_id).one()
        assert str(refreshed.dispatch_status) == "SUSPENDED"
        assert str(provider_id) in result["suspended_provider_ids"]
    finally:
        db.close()

    status = client.get(f"/api/compliance/providers/{provider_id}/status")
    assert status.status_code == 200
    assert status.json()["dispatch_eligible"] is False


def test_audit_packet_download(client: TestClient) -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        provider_id = provider.provider_id
        run_full_credentialing_screen(db, provider_id)
    finally:
        db.close()

    response = client.get(f"/api/compliance/providers/{provider_id}/audit-packet")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content[:2] == b"PK"


def test_geo_matches_within_radius(client: TestClient) -> None:
    token = uuid4().hex
    facility_lat = 38.7 + (int(token[:4], 16) % 500) / 10000.0
    facility_lon = -77.6 - (int(token[4:8], 16) % 500) / 10000.0
    db = SessionLocal()
    try:
        facility = MarylandFacility(
            name=f"FutureCare Northpoint {token[:6]}",
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
        near_id = str(near.provider_id)
        far_id = str(far.provider_id)
        run_full_credentialing_screen(db, near.provider_id)
        run_full_credentialing_screen(db, far.provider_id)
        db.commit()
        offer_id = offer.offer_id
    finally:
        db.close()

    response = client.get(f"/api/compliance/offers/{offer_id}/geo-matches?radius_miles=15")
    assert response.status_code == 200
    ids = {row["provider_id"] for row in response.json()}
    assert near_id in ids
    assert far_id not in ids


def test_vms_ingest_dry_run(client: TestClient) -> None:
    response = client.post("/api/vms/shifts/ingest?persist=true")
    assert response.status_code == 200
    body = response.json()
    assert body["shifts_fetched"] >= 3
    assert isinstance(body["shifts"], list)
    assert body["shifts"][0]["source"] in {"SHIFTWISE", "FIELDGLASS"}


def test_shift_ranking_eliminates_unverified_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "GEO_MATCH_RADIUS_MILES", 9999.0)
    db = SessionLocal()
    try:
        facility = MarylandFacility(
            name="Compliance Rank Facility",
            facility_type="NURSING_HOME",
            county="Baltimore",
            state="MD",
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
        db.flush()
        unverified = _create_provider(db)
        verified = _create_provider(db, full_name="Verified CNA")
        run_full_credentialing_screen(db, verified.provider_id)
        db.commit()
        ranking = rank_offer_from_db(db, offer.offer_id)
        assert any(
            row.reason == "license not verified" and row.provider_id == unverified.provider_id
            for row in ranking.eliminated
        )
        assert any(row.provider_id == verified.provider_id for row in ranking.ranked)
    finally:
        db.close()


def test_crisis_scan_creates_signals_when_enough_open_shifts(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.post("/api/compliance/crisis/scan")
    assert response.status_code == 200
    listed = client.get("/api/compliance/crisis/signals?limit=5").json()
    assert isinstance(listed, list)
