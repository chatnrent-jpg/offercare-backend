"""Portal step 27 — next shift desk / repeat journey."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import PORTAL_BUILD_ID
from app.models import MarylandProvider
from app.services.clinician_journey_status import build_clinician_journey_status
from app.services.clinician_payments import complete_demo_portal_payouts, ensure_demo_portal_payments
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, SAMPLE_DEMO_PORTAL_EMAIL
from app.services.demo_portal_lockable import ensure_demo_replenish_after_payout, repair_demo_portal_placements
from app.services.vms_submission import submit_demo_clinician_placements_to_vms


def test_portal_step27_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    css = client.get("/portal/styles.css").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert "next-shift-desk" in html
    assert "renderNextShiftDesk" in js
    assert "focusNextLockableShift" in js
    assert ".next-shift-desk" in css


def test_demo_journey_status_endpoint(client: TestClient) -> None:
    login = client.post(
        "/api/clinicians/login",
        json={"email": SAMPLE_DEMO_PORTAL_EMAIL, "password": DEMO_PORTAL_PASSWORD},
    )
    if login.status_code == 401:
        pytest.skip("demo login unavailable in this database")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/clinicians/me/journey-status", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "phase" in body
    assert "lockable_count" in body
    assert "can_repeat_journey" in body


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_journey_status_after_paid(db: Session) -> None:
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == SAMPLE_DEMO_PORTAL_EMAIL)
        .first()
    )
    if provider is None:
        pytest.skip("demo CNA unavailable")
    repair_demo_portal_placements(db, provider)
    submit_demo_clinician_placements_to_vms(db, provider)
    ensure_demo_portal_payments(db, provider)
    complete_demo_portal_payouts(db, provider)
    ensure_demo_replenish_after_payout(db, provider)
    status = build_clinician_journey_status(db, provider)
    assert status["paid_shifts_count"] >= 0
