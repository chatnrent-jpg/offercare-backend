from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import ClinicianPushSubscription, MarylandProvider, ShiftNotificationLog
from app.seed import seed_saint_judes_demo
from app.services.email_alerts import build_shift_alert_email, send_shift_email
from app.services.integrations import integration_snapshot
from app.services.shift_ranking import notify_top_clinicians_for_offer


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_email_dry_run_by_default() -> None:
    result = send_shift_email(
        to_address="nurse.a@offercare.demo",
        subject="Test",
        message_body="Hello",
    )
    assert result.mode == "dry_run"
    assert result.status == "DRY_RUN"
    assert result.message_id


def test_build_shift_alert_email_includes_shift_details() -> None:
    subject, body = build_shift_alert_email(
        facility_name="Saint Jude's ICU",
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
        clinician_name="Nurse A",
    )
    assert "Saint Jude's ICU" in subject
    assert "ICU_RN" in body
    assert "$120.00" in body
    assert "YES" in body


def test_integrations_status_includes_email() -> None:
    snapshot = integration_snapshot()
    assert "email" in snapshot
    assert snapshot["email"]["dry_run"] is True


def test_notify_sends_email_alongside_sms(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = __import__("uuid").UUID(seeded["offer_id"])
    nurse_a = db.query(MarylandProvider).filter(MarylandProvider.email == "nurse.a@offercare.demo").one()
    db.query(ClinicianPushSubscription).filter(
        ClinicianPushSubscription.provider_id == nurse_a.provider_id
    ).delete(synchronize_session=False)
    db.query(ShiftNotificationLog).filter(ShiftNotificationLog.offer_id == offer_id).delete(
        synchronize_session=False
    )
    db.commit()

    notified = notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    assert notified.deliveries
    assert notified.deliveries[0].mode == "dry_run"
    assert notified.email_deliveries
    assert notified.email_deliveries[0].mode == "dry_run"
    assert notified.email_deliveries[0].email_address == "nurse.a@offercare.demo"

    channels = {
        row.channel
        for row in db.query(ShiftNotificationLog)
        .filter(ShiftNotificationLog.offer_id == offer_id)
        .all()
    }
    assert channels == {"SMS", "EMAIL"}


@patch("smtplib.SMTP")
def test_email_live_smtp_send(mock_smtp_cls, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EMAIL_ALERTS_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", False)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "EMAIL_FROM", "alerts@offercare.ai")
    monkeypatch.setattr(settings, "SMTP_USE_TLS", True)

    smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = smtp

    result = send_shift_email(
        to_address="nurse.a@offercare.demo",
        subject="Live test",
        message_body="Shift alert",
    )
    assert result.status == "SENT"
    assert result.mode == "smtp"
    smtp.starttls.assert_called_once()
    smtp.send_message.assert_called_once()


def test_integrations_test_email_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/integrations/test/email",
        json={"email_address": "nurse.a@offercare.demo", "message": "VettedCare test"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "DRY_RUN"


def test_notify_api_returns_email_deliveries(client: TestClient) -> None:
    seed_resp = client.post("/api/seed/saint-judes")
    offer_id = seed_resp.json()["offer_id"]
    notify_resp = client.post(
        f"/shift-sniper/offers/{offer_id}/notify",
        json={"max_recipients": 1, "reply_keyword": "YES"},
    )
    assert notify_resp.status_code == 200
    body = notify_resp.json()
    assert body["deliveries"][0]["status"] == "DRY_RUN"
    assert body["email_deliveries"][0]["status"] == "DRY_RUN"


def test_env_example_documents_email() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "EMAIL_ALERTS_ENABLED" in text
    assert "SMTP_HOST" in text
