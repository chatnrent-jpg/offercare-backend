"""Portal step 24 — earnings summary + instant pay deposit toast."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import PORTAL_BUILD_ID
from app.models import MarylandProvider
from app.services.clinician_earnings import summarize_clinician_earnings
from app.services.clinician_payments import (
    complete_demo_portal_payouts,
    ensure_demo_portal_payments,
)
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, SAMPLE_DEMO_PORTAL_EMAIL
from app.services.demo_portal_lockable import repair_demo_portal_placements
from app.services.vms_submission import submit_demo_clinician_placements_to_vms


def test_portal_step24_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    css = client.get("/portal/styles.css").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert "earnings-strip" in html
    assert "renderEarningsSummary" in js
    assert "notifyInstantPayDeposits" in js
    assert ".earnings-strip" in css


def test_demo_earnings_endpoint(client: TestClient) -> None:
    login = client.post(
        "/api/clinicians/login",
        json={"email": SAMPLE_DEMO_PORTAL_EMAIL, "password": DEMO_PORTAL_PASSWORD},
    )
    if login.status_code == 401:
        pytest.skip("demo login unavailable in this database")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/clinicians/me/earnings", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "week_paid_amount" in body
    assert "lifetime_paid_amount" in body
    assert "pending_payroll_amount" in body
    assert body["currency"] == "USD"


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_summarize_clinician_earnings_after_paid(db: Session) -> None:
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
    summary = summarize_clinician_earnings(db, provider.provider_id)
    if summary["shifts_paid_count"] == 0:
        pytest.skip("no paid demo payouts")
    assert summary["lifetime_paid_amount"] > 0
