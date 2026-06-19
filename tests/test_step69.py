from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicalPlacementLedger, MarylandProvider, OfferCareJobOffer
from app.services.demo_environment import (
    build_demo_environment_status,
    reset_demo_environment,
    reset_demo_offer,
    run_full_demo_setup,
)
from app.services.shift_lock import lock_shift_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_reset_demo_offer_unlocks_single_locked_shift(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    saint_jude = next(row for row in status["offers"] if row["facility_name"] == "Saint Jude's ICU")
    nj_provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    saint_provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == saint_jude["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=nj_provider, offer_id=UUID(nj_offer["offer_id"]))
    lock_shift_for_provider(db, provider=saint_provider, offer_id=UUID(saint_jude["offer_id"]))

    payload = reset_demo_offer(db, UUID(nj_offer["offer_id"]))
    assert payload is not None
    assert payload["facility_name"] == "Paramus SNF at Bergen"
    assert payload["offers_reset"] == 1
    assert payload["placements_cleared"] == 1

    nj = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == nj_offer["offer_id"]).first()
    saint = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == saint_jude["offer_id"]).first()
    db.refresh(nj)
    db.refresh(saint)
    assert nj.compliance_lock_status == "BROADCASTING"
    assert saint.compliance_lock_status == "LOCKED"


def test_reset_demo_offer_is_idempotent_when_already_broadcasting(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    first = reset_demo_offer(db, UUID(nj_offer["offer_id"]))
    second = reset_demo_offer(db, UUID(nj_offer["offer_id"]))
    assert first is not None
    assert second is not None
    assert second["offers_reset"] == 0
    assert second["placements_cleared"] == 0


def test_reset_demo_offer_rejects_non_demo_facility(db: Session) -> None:
    from app.models import MarylandFacility, OfferCareJobOffer

    facility = MarylandFacility(
        name="Non Demo Hospital",
        facility_type="HOSPITAL",
        county="Test",
        state="MD",
        vms_integration_type="SCRAPE",
    )
    db.add(facility)
    db.flush()
    offer = OfferCareJobOffer(
        facility_id=facility.facility_id,
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
        compliance_lock_status="LOCKED",
    )
    db.add(offer)
    db.commit()
    assert reset_demo_offer(db, offer.offer_id) is None


def test_reset_demo_offer_leaves_other_locked_shifts(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    reset_demo_environment(db)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))
    payload = reset_demo_offer(db, UUID(nj_offer["offer_id"]))
    assert payload is not None
    assert payload["offers_reset"] == 1
    placement_count = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.offer_id == UUID(nj_offer["offer_id"]))
        .count()
    )
    assert placement_count == 0


def test_demo_reset_offer_endpoint(client: TestClient, db: Session) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))
    response = client.post(f"/api/seed/demo-reset-offer?offer_id={nj_offer['offer_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["facility_name"] == "Paramus SNF at Bergen"
    assert body["offers_reset"] == 1
    assert body["placements_cleared"] == 1


def test_admin_dashboard_includes_per_row_reset_button(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "demo-reset-offer-btn" in text
    assert "wireDemoResetOfferButtons" in text
    assert "/api/seed/demo-reset-offer" in text


def test_deploy_checklist_mentions_per_row_reset(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("reset" in step.lower() and "row" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_per_row_reset(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("reset on a locked demo shift row" in step.lower() for step in steps)
