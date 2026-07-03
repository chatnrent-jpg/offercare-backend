"""Portal step 26 — instant pay receipt download."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import PORTAL_BUILD_ID
from app.models import MarylandProvider
from app.services.clinician_payment_receipt import get_clinician_payment_receipt
from app.services.clinician_payments import (
    complete_demo_portal_payouts,
    ensure_demo_portal_payments,
    list_clinician_payments,
)
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, SAMPLE_DEMO_PORTAL_EMAIL
from app.services.demo_portal_lockable import repair_demo_portal_placements
from app.services.vms_submission import submit_demo_clinician_placements_to_vms


def test_portal_step26_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert "downloadPaymentReceipt" in js
    assert "payment-receipt-btn" in js


def test_demo_payment_receipt_endpoint(client: TestClient) -> None:
    login = client.post(
        "/api/clinicians/login",
        json={"email": SAMPLE_DEMO_PORTAL_EMAIL, "password": DEMO_PORTAL_PASSWORD},
    )
    if login.status_code == 401:
        pytest.skip("demo login unavailable in this database")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    payments = client.get("/api/clinicians/me/payments", headers=headers)
    assert payments.status_code == 200
    rows = payments.json()
    paid = next((row for row in rows if row.get("payout_status") == "PAID"), None)
    if paid is None:
        pytest.skip("no paid demo payout")

    response = client.get(
        f"/api/clinicians/me/payments/{paid['payout_id']}/receipt",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["receipt_id"].startswith("VC-PAY-")
    assert "VettedCare.ai" in body["receipt_text"]
    assert body["gross_pay_amount"] > 0


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_get_clinician_payment_receipt(db: Session) -> None:
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
    payments = list_clinician_payments(db, provider.provider_id)
    paid = next((row for row in payments if str(row["payout_status"]).upper() == "PAID"), None)
    if paid is None:
        pytest.skip("no paid payout")
    receipt = get_clinician_payment_receipt(db, provider.provider_id, paid["payout_id"])
    assert receipt is not None
    assert receipt["receipt_filename"].endswith(".txt")
