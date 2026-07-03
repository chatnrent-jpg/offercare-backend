"""Portal step 22 — demo instant pay completion + overview pipeline."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import PORTAL_BUILD_ID
from app.models import MarylandProvider
from app.services.clinician_payments import (
    complete_demo_portal_payouts,
    ensure_demo_portal_payments,
    list_clinician_payments,
)
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, SAMPLE_DEMO_PORTAL_EMAIL
from app.services.demo_portal_lockable import repair_demo_portal_placements
from app.services.vms_submission import submit_demo_clinician_placements_to_vms


def test_portal_step22_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    css = client.get("/portal/styles.css").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert "pipeline-strip" in html
    assert "renderPipelineStrip" in js
    assert ".pipeline-strip" in css
    assert "payment-paid-row" in css


def test_demo_payments_endpoint_paid(client: TestClient) -> None:
    login = client.post(
        "/api/clinicians/login",
        json={"email": SAMPLE_DEMO_PORTAL_EMAIL, "password": DEMO_PORTAL_PASSWORD},
    )
    if login.status_code == 401:
        pytest.skip("demo login unavailable in this database")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/clinicians/me/payments", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    if not rows:
        pytest.skip("no demo payments yet")
    row = rows[0]
    assert row["payout_status"] == "PAID"
    assert row["payout_status_label"] == "Paid"
    assert row.get("stripe_payout_id", "").startswith("DRYRUN-PAY-")
    assert row.get("paid_at") is not None


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_complete_demo_portal_payouts(db: Session) -> None:
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
    completed = complete_demo_portal_payouts(db, provider)
    assert completed >= 0
    rows = list_clinician_payments(db, provider.provider_id)
    if not rows:
        pytest.skip("no demo payouts")
    assert str(rows[0]["payout_status"]).upper() == "PAID"
    assert rows[0].get("stripe_payout_id", "").startswith("DRYRUN-PAY-")
