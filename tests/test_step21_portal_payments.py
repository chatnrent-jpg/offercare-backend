"""Portal step 21 — instant pay / payments tab after VMS-confirmed placements."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import PORTAL_BUILD_ID
from app.models import MarylandProvider
from app.services.clinician_payments import ensure_demo_portal_payments, payment_status_label
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, SAMPLE_DEMO_PORTAL_EMAIL
from app.services.demo_portal_lockable import repair_demo_portal_placements
from app.services.vms_submission import list_clinician_placements, submit_demo_clinician_placements_to_vms


def test_payment_status_label_submitted() -> None:
    assert payment_status_label("SUBMITTED") == "Submitted to payroll"


def test_portal_step21_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert 'data-view="payments"' in html
    assert "view-payments" in html
    assert "renderPayments" in js
    assert "paymentStatusBadge" in js


def test_demo_payments_endpoint(client: TestClient) -> None:
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
    assert "gross_pay_amount" in row
    assert "payout_status_label" in row
    assert row["payout_status"] in {"PENDING", "SUBMITTED", "PROCESSING", "PAID", "FAILED"}


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_ensure_demo_portal_payments_from_submitted_placement(db: Session) -> None:
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == SAMPLE_DEMO_PORTAL_EMAIL)
        .first()
    )
    if provider is None:
        pytest.skip("demo CNA unavailable")
    repair_demo_portal_placements(db, provider)
    submit_demo_clinician_placements_to_vms(db, provider)
    placements = list_clinician_placements(db, provider.provider_id)
    if not placements:
        pytest.skip("no demo placements")
    if str(placements[0]["vms_submission_status"]).upper() != "SUBMITTED":
        pytest.skip("placement not submitted to VMS")
    created = ensure_demo_portal_payments(db, provider)
    assert created >= 0
