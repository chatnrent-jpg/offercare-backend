from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicianPushSubscription, MarylandProvider, ShiftNotificationLog
from app.seed import seed_all_mid_atlantic_demos
from app.services.demo_environment import list_demo_offer_ids, notify_matched_on_demo_environment
from app.services.push_subscriptions import register_push_subscription


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_list_demo_offer_ids_returns_ten_after_mid_atlantic_seed(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    offer_ids = list_demo_offer_ids(db)
    assert len(offer_ids) == 10


def test_notify_matched_on_demo_environment_sends_push(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    provider = db.query(MarylandProvider).filter(MarylandProvider.email == "nj.snf.cna.a@offercare.demo").first()
    db.query(ClinicianPushSubscription).filter(
        ClinicianPushSubscription.provider_id == provider.provider_id
    ).delete(synchronize_session=False)
    db.commit()
    register_push_subscription(
        db,
        provider.provider_id,
        endpoint="https://push.example.test/step52-nj",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
    )

    payload = notify_matched_on_demo_environment(db)
    assert payload["offer_count"] == 10
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


def test_notify_matched_on_demo_environment_with_no_offer_ids(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.demo_environment.list_demo_offer_ids", lambda _db: [])
    payload = notify_matched_on_demo_environment(db)
    assert payload["offer_count"] == 0
    assert payload["matched_push_alerts_sent"] == 0


def test_notify_matched_demos_endpoint(client: TestClient, db: Session) -> None:
    client.post("/api/seed/mid-atlantic-demos")
    provider = db.query(MarylandProvider).filter(MarylandProvider.email == "nj.snf.cna.a@offercare.demo").first()
    register_push_subscription(
        db,
        provider.provider_id,
        endpoint="https://push.example.test/step52-endpoint",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
    )
    response = client.post("/api/seed/notify-matched-demos")
    assert response.status_code == 200
    body = response.json()
    assert body["offer_count"] == 10
    assert body["matched_push_alerts_sent"] >= 1


def test_admin_dashboard_includes_notify_matched_demos_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "notify-matched-demos-btn" in html.text
    assert "Notify matched on all demos" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/notify-matched-demos" in js.text


def test_deploy_checklist_mentions_notify_matched_on_all_demos(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("Notify matched on all demos" in step for step in steps)
