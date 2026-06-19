from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.seed import seed_saint_judes_demo
from app.services.shift_ranking import notify_top_clinicians_for_offer
from app.services.twilio_security import compute_twilio_signature


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_admin_route_blocks_missing_key(client: TestClient) -> None:
    response = client.post("/api/seed/saint-judes", headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 401
    assert response.json()["detail"] == "admin_unauthorized"


def test_admin_route_allows_valid_key(client: TestClient) -> None:
    response = client.post("/api/seed/saint-judes")
    assert response.status_code == 200


def test_admin_auth_disabled_when_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")
    from app.main import app

    open_client = TestClient(app)
    response = open_client.post("/api/seed/saint-judes")
    assert response.status_code == 200


def test_twilio_signature_rejected_when_enabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TWILIO_VALIDATE_SIGNATURES", True)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "twilio-test-token")

    response = client.post(
        "/shift-sniper/twilio/sms",
        data={"From": "+14105550001", "Body": "YES"},
        headers={"X-Twilio-Signature": "invalid"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "invalid_twilio_signature"


def test_twilio_signature_accepted_when_valid(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TWILIO_VALIDATE_SIGNATURES", True)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "twilio-test-token")

    seeded = seed_saint_judes_demo(db)
    offer_id = uuid.UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)

    params = {"From": "+14105550001", "Body": "YES"}
    url = "http://testserver/shift-sniper/twilio/sms"
    signature = compute_twilio_signature(url, params, "twilio-test-token")

    response = client.post(
        "/shift-sniper/twilio/sms",
        data=params,
        headers={"X-Twilio-Signature": signature},
    )
    assert response.status_code == 200
    assert "Shift locked" in response.text
