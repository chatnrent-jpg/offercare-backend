"""Portal step 25 — alerts inbox (SMS, push, portal)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import PORTAL_BUILD_ID
from app.models import MarylandProvider
from app.services.clinician_alerts import list_clinician_alerts
from app.services.clinician_payments import complete_demo_portal_payouts, ensure_demo_portal_payments
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, SAMPLE_DEMO_PORTAL_EMAIL
from app.services.demo_portal_lockable import repair_demo_portal_placements
from app.services.shift_matching import count_portal_lockable_shifts
from app.services.vms_submission import submit_demo_clinician_placements_to_vms


def test_portal_step25_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    css = client.get("/portal/styles.css").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert 'data-view="alerts"' in html
    assert "view-alerts" in html
    assert "renderAlerts" in js
    assert ".alert-card" in css


def test_demo_alerts_endpoint(client: TestClient) -> None:
    login = client.post(
        "/api/clinicians/login",
        json={"email": SAMPLE_DEMO_PORTAL_EMAIL, "password": DEMO_PORTAL_PASSWORD},
    )
    if login.status_code == 401:
        pytest.skip("demo login unavailable in this database")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/clinicians/me/alerts", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    if not rows:
        pytest.skip("no demo alerts yet")
    channels = {row["channel"] for row in rows}
    assert channels & {"SMS", "PUSH", "PORTAL"}


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_list_clinician_alerts_after_journey(db: Session) -> None:
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
    lockable = count_portal_lockable_shifts(db, provider, limit=50)
    rows = list_clinician_alerts(db, provider.provider_id, lockable_count=lockable)
    if not rows:
        pytest.skip("no demo alerts")
    types = {row["alert_type"] for row in rows}
    assert "SHIFT_MATCH" in types or "SHIFT_LOCKED" in types
