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


def test_geo_matches_within_radius(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.services.geo_matching import haversine_miles

    monkeypatch.setattr(settings, "UNIFIED_MATCH_MATRIX_BROKER_ENABLED", False)

    token = uuid4().hex
    facility_lat = 38.9 + (int(token[:4], 16) % 500) / 10000.0
    facility_lon = -77.4 - (int(token[4:8], 16) % 500) / 10000.0
    near_lat = facility_lat + 0.004
    near_lon = facility_lon + 0.002
    far_lat = 39.9500
    far_lon = -75.1600
    radius_miles = 15.0
    near_label = f"GeoRadiusNear-{token[:8]}"

    near_distance = haversine_miles(facility_lat, facility_lon, near_lat, near_lon)
    far_distance = haversine_miles(facility_lat, facility_lon, far_lat, far_lon)
    assert near_distance < radius_miles
    assert far_distance > radius_miles

    db = SessionLocal()
    suspended_snapshot: list[tuple[object, str]] = []
    try:
        # Strict isolation: sideline all Maryland providers eligible to compete in geo-match.
        md_providers = db.query(MarylandProvider).filter(MarylandProvider.state == "MD").all()
        for provider in md_providers:
            prior_status = str(provider.dispatch_status or "ACTIVE")
            if prior_status.upper() == "SUSPENDED":
                continue
            suspended_snapshot.append((provider.provider_id, prior_status))
            provider.dispatch_status = "SUSPENDED"
        db.commit()

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
            full_name=near_label,
            latitude=near_lat,
            longitude=near_lon,
        )
        far = _create_provider(
            db,
            full_name=f"GeoRadiusFar-{token[:8]}",
            latitude=far_lat,
            longitude=far_lon,
        )
        near_id = str(near.provider_id)
        far_id = str(far.provider_id)
        run_full_credentialing_screen(db, near.provider_id)
        run_full_credentialing_screen(db, far.provider_id)
        test_provider_ids = {near.provider_id, far.provider_id}
        for provider in db.query(MarylandProvider).filter(MarylandProvider.state == "MD").all():
            if provider.provider_id in test_provider_ids:
                provider.dispatch_status = "ACTIVE"
            else:
                provider.dispatch_status = "SUSPENDED"
        db.commit()
        offer_id = offer.offer_id

        response = client.get(
            f"/api/compliance/offers/{offer_id}/geo-matches"
            f"?radius_miles={radius_miles:.0f}&limit=25"
        )
        assert response.status_code == 200
        geo_match_records = response.json()
        geo_radius_rows = [
            row
            for row in geo_match_records
            if "GeoRadius" in str(row.get("full_name") or "")
        ]
        near_row = next(
            (row for row in geo_radius_rows if row.get("provider_id") == near_id),
            None,
        )
        assert near_row is not None, (
            f"GeoRadiusNear-{token[:8]} missing from test-scoped geo matches; "
            f"filtered={geo_radius_rows!r} total={len(geo_match_records)}"
        )
        assert far_id not in {row.get("provider_id") for row in geo_radius_rows}
        assert near_row["distance_miles"] is not None
        assert near_row["distance_miles"] < radius_miles
    finally:
        if suspended_snapshot:
            for provider_id, prior_status in suspended_snapshot:
                row = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
                if row is not None:
                    row.dispatch_status = prior_status
            db.commit()
        db.close()


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


def _parse_sentinel_block_message(message: str) -> dict:
    import json

    assert "SENTINEL_BLOCK" in message
    payload_raw = message.split("SENTINEL_BLOCK:", 1)[1]
    payload = json.loads(payload_raw)
    assert payload["ok"] is False
    assert payload["sentinel"] == "VALIDATION_BLOCK"
    assert payload["error_count"] >= 1
    assert isinstance(payload["errors"], list)
    assert payload["errors"]
    return payload


def test_semantic_engine_sentinel_blocks_excessive_search_radius() -> None:
    from strategy.semantic_payout_engine import SemanticPayoutEngine

    engine = SemanticPayoutEngine(prefer_live_db=False)
    query = "Dementia care Baltimore night shift SNF memory unit coverage"
    with pytest.raises(ValueError) as excinfo:
        engine.find_top_vector_matches(
            query,
            shift_context={
                "latitude": 39.29,
                "longitude": -76.61,
                "search_radius_miles": 150.0,
            },
        )

    payload = _parse_sentinel_block_message(str(excinfo.value))
    fields = {err["field"] for err in payload["errors"]}
    assert "search_radius_miles" in fields


def test_semantic_engine_sentinel_blocks_illegal_latitude() -> None:
    from strategy.semantic_payout_engine import SemanticPayoutEngine

    engine = SemanticPayoutEngine(prefer_live_db=False)
    query = "Night shift CNA dementia care Baltimore SNF memory unit"
    with pytest.raises(ValueError) as excinfo:
        engine.find_top_vector_matches(
            query,
            shift_context={
                "latitude": 91.5,
                "longitude": -76.61,
                "search_radius_miles": 25.0,
            },
        )

    payload = _parse_sentinel_block_message(str(excinfo.value))
    fields = {err["field"] for err in payload["errors"]}
    assert "latitude" in fields


def test_semantic_engine_sentinel_blocks_illegal_longitude() -> None:
    from strategy.semantic_payout_engine import SemanticPayoutEngine

    engine = SemanticPayoutEngine(prefer_live_db=False)
    query = "Night shift CNA dementia care Baltimore SNF memory unit"
    with pytest.raises(ValueError) as excinfo:
        engine.find_top_vector_matches(
            query,
            shift_context={
                "latitude": 39.29,
                "longitude": -181.0,
                "search_radius_miles": 25.0,
            },
        )

    payload = _parse_sentinel_block_message(str(excinfo.value))
    fields = {err["field"] for err in payload["errors"]}
    assert "longitude" in fields
