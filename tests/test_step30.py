from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.auth import hash_password
from app.models import ClinicianPortalAccount, ClinicianPushSubscription, MarylandProvider, ShiftNotificationLog
from app.seed import seed_saint_judes_demo
from app.services.clinician_auth import create_portal_account
from app.services.integrations import integration_snapshot
from app.services.push_alerts import build_shift_alert_push, send_shift_push
from app.services.push_subscriptions import register_push_subscription
from app.services.shift_ranking import notify_top_clinicians_for_offer


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _ensure_portal_password(db: Session, provider_id: UUID, password: str) -> None:
    account = (
        db.query(ClinicianPortalAccount)
        .filter(ClinicianPortalAccount.provider_id == provider_id)
        .first()
    )
    if account is None:
        create_portal_account(db, provider_id, password)
        return
    account.password_hash = hash_password(password)
    db.commit()


def test_push_dry_run_by_default() -> None:
    result = send_shift_push(
        endpoint="https://push.example.test/endpoint",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
        title="Test",
        message_body="Hello",
    )
    assert result.mode == "dry_run"
    assert result.status == "DRY_RUN"
    assert result.receipt_id


def test_build_shift_alert_push_includes_shift_details() -> None:
    title, body = build_shift_alert_push(
        facility_name="Saint Jude's ICU",
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
        schedule_line=" · Mon 7am ET",
    )
    assert "Saint Jude's ICU" in title
    assert "ICU_RN" in body
    assert "$120.00" in body
    assert "YES" in body


def test_integrations_status_includes_push() -> None:
    snapshot = integration_snapshot()
    assert "push" in snapshot
    assert snapshot["push"]["dry_run"] is True
    assert snapshot["push"]["vapid_public_key"]


def test_register_and_notify_push(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    nurse_a = db.query(MarylandProvider).filter(MarylandProvider.full_name == "Nurse A").one()
    db.query(ClinicianPushSubscription).filter(
        ClinicianPushSubscription.provider_id == nurse_a.provider_id
    ).delete(synchronize_session=False)
    db.commit()
    register_push_subscription(
        db,
        nurse_a.provider_id,
        endpoint="https://push.example.test/device-1",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
    )

    notified = notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    assert notified.deliveries
    assert notified.email_deliveries
    assert notified.push_deliveries
    assert notified.push_deliveries[0].mode == "dry_run"
    assert any(
        delivery.endpoint == "https://push.example.test/device-1"
        for delivery in notified.push_deliveries
    )

    channels = {
        row.channel
        for row in db.query(ShiftNotificationLog)
        .filter(ShiftNotificationLog.offer_id == offer_id)
        .all()
    }
    assert channels == {"SMS", "EMAIL", "PUSH"}


@patch("pywebpush.webpush")
def test_push_live_webpush_send(mock_webpush, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PUSH_ALERTS_ENABLED", True)
    monkeypatch.setattr(settings, "PUSH_DRY_RUN", False)
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrnZgGgSnrjUThz_jBVehPu5y0rFL17qkhX-R-Zg")
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIAGb7x...\n-----END EC PRIVATE KEY-----")
    mock_webpush.return_value = MagicMock(headers={"location": "receipt-123"})

    result = send_shift_push(
        endpoint="https://push.example.test/device-1",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
        title="Live test",
        message_body="Shift alert",
    )
    assert result.status == "SENT"
    assert result.mode == "webpush"
    mock_webpush.assert_called_once()


def test_clinician_push_subscribe_api(client: TestClient, db: Session) -> None:
    seed_saint_judes_demo(db)
    nurse_a = db.query(MarylandProvider).filter(MarylandProvider.email == "nurse.a@offercare.demo").one()
    db.query(ClinicianPushSubscription).filter(
        ClinicianPushSubscription.provider_id == nurse_a.provider_id
    ).delete(synchronize_session=False)
    db.commit()
    _ensure_portal_password(db, nurse_a.provider_id, "SecretPass1")
    login = client.post(
        "/api/clinicians/login",
        json={"email": "nurse.a@offercare.demo", "password": "SecretPass1"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    config = client.get("/api/clinicians/me/push/config", headers=headers)
    assert config.status_code == 200
    assert config.json()["enabled"] is True
    assert config.json()["public_key"]

    subscribe = client.post(
        "/api/clinicians/me/push/subscribe",
        headers=headers,
        json={
            "endpoint": "https://push.example.test/device-portal",
            "keys": {"p256dh": "portal-p256dh", "auth": "portal-auth"},
            "user_agent": "pytest",
        },
    )
    assert subscribe.status_code == 200

    listed = client.get("/api/clinicians/me/push/subscriptions", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_integrations_test_push_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/integrations/test/push",
        json={
            "endpoint": "https://push.example.test/device-admin",
            "p256dh_key": "admin-p256dh",
            "auth_key": "admin-auth",
            "message": "OfferCare test",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "DRY_RUN"


def test_notify_api_returns_push_deliveries(client: TestClient, db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = seeded["offer_id"]
    nurse_a = db.query(MarylandProvider).filter(MarylandProvider.email == "nurse.a@offercare.demo").one()
    _ensure_portal_password(db, nurse_a.provider_id, "SecretPass1")
    login = client.post(
        "/api/clinicians/login",
        json={"email": "nurse.a@offercare.demo", "password": "SecretPass1"},
    )
    token = login.json()["access_token"]
    client.post(
        "/api/clinicians/me/push/subscribe",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "endpoint": "https://push.example.test/device-notify",
            "keys": {"p256dh": "notify-p256dh", "auth": "notify-auth"},
        },
    )

    notify_resp = client.post(
        f"/shift-sniper/offers/{offer_id}/notify",
        json={"max_recipients": 1, "reply_keyword": "YES"},
    )
    assert notify_resp.status_code == 200
    body = notify_resp.json()
    assert body["push_deliveries"][0]["status"] == "DRY_RUN"


def test_portal_includes_push_ui(client: TestClient) -> None:
    html = client.get("/portal")
    assert html.status_code == 200
    assert "enable-push-btn" in html.text
    assert "manifest.webmanifest" in html.text
    js = client.get("/portal/app.js")
    assert js.status_code == 200
    assert "enablePushAlerts" in js.text
    sw = client.get("/portal/sw.js")
    assert sw.status_code == 200
    assert "showNotification" in sw.text


def test_env_example_documents_push() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "PUSH_ALERTS_ENABLED" in text
    assert "VAPID_PUBLIC_KEY" in text
