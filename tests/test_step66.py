from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider, ShiftNotificationLog
from app.services.demo_environment import (
    build_demo_environment_status,
    notify_matched_on_demo_offer,
    run_full_demo_setup,
)
from app.services.push_subscriptions import register_push_subscription
from app.services.shift_lock import lock_shift_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_notify_matched_on_demo_offer_sends_push_for_one_shift(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    register_push_subscription(
        db,
        provider.provider_id,
        endpoint="https://push.example.test/step66-nj",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
    )
    payload = notify_matched_on_demo_offer(db, UUID(nj_offer["offer_id"]))
    assert payload is not None
    assert payload["facility_name"] == "Paramus SNF at Bergen"
    assert payload["matched_push_alerts_sent"] >= 1
    logs = (
        db.query(ShiftNotificationLog)
        .filter(
            ShiftNotificationLog.provider_id == provider.provider_id,
            ShiftNotificationLog.channel == "MATCHED_PUSH",
        )
        .all()
    )
    assert logs


def test_notify_matched_on_demo_offer_rejects_non_demo_offer(db: Session) -> None:
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
        compliance_lock_status="BROADCASTING",
    )
    db.add(offer)
    db.commit()
    assert notify_matched_on_demo_offer(db, offer.offer_id) is None


def test_notify_matched_on_demo_offer_skips_locked_shift(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))
    payload = notify_matched_on_demo_offer(db, UUID(nj_offer["offer_id"]))
    assert payload is not None
    assert payload["matched_push_alerts_sent"] == 0
    assert "not broadcasting" in payload["message"].lower()


def test_demo_notify_matched_offer_endpoint(client: TestClient, db: Session) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    register_push_subscription(
        db,
        provider.provider_id,
        endpoint="https://push.example.test/step66-endpoint",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
    )
    response = client.post(f"/api/seed/demo-notify-matched?offer_id={nj_offer['offer_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["facility_name"] == "Paramus SNF at Bergen"
    assert body["matched_push_alerts_sent"] >= 1


def test_admin_dashboard_includes_per_row_notify_button(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "demo-notify-matched-offer-btn" in text
    assert "wireDemoNotifyMatchedButtons" in text
    assert "runDemoNotifyMatched" in text
    assert "/api/seed/demo-notify-matched" in text


def test_deploy_checklist_mentions_per_row_notify(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("notify" in step.lower() and "row" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_per_row_notify(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("notify" in step.lower() for step in steps)
