from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicianPushSubscription, MarylandProvider
from app.seed import seed_all_mid_atlantic_demos
from app.services.demo_environment import build_demo_environment_status, notify_matched_on_demo_environment
from app.services.demo_push_subscriptions import demo_push_endpoint, ensure_demo_push_subscriptions
from app.services.push_subscriptions import list_push_subscriptions_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_ensure_demo_push_subscriptions_registers_all_demo_clinicians(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    payload = ensure_demo_push_subscriptions(db)
    assert payload["clinician_count"] >= 10
    assert payload["created"] + payload["existing"] == payload["clinician_count"]

    provider = db.query(MarylandProvider).filter(MarylandProvider.email == "nj.snf.cna.a@offercare.demo").first()
    subscriptions = list_push_subscriptions_for_provider(db, provider.provider_id)
    assert subscriptions
    endpoints = {subscription.endpoint for subscription in subscriptions}
    assert demo_push_endpoint(provider.provider_id) in endpoints


def test_ensure_demo_push_subscriptions_is_idempotent(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    first = ensure_demo_push_subscriptions(db)
    second = ensure_demo_push_subscriptions(db)
    assert second["created"] == 0
    assert second["existing"] == first["clinician_count"]


def test_demo_status_shows_push_subscription_counts(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    ensure_demo_push_subscriptions(db)
    status = build_demo_environment_status(db)
    assert status["push_subscription_count"] >= 10
    assert status["push_subscriptions_ready"] is True
    assert all(row["push_enabled"] for row in status["clinicians"])


def test_notify_matched_on_demos_sends_after_demo_push_subscriptions(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    ensure_demo_push_subscriptions(db)
    payload = notify_matched_on_demo_environment(db)
    assert payload["offer_count"] == 10
    assert payload["matched_push_alerts_sent"] >= 10


def test_demo_push_subscriptions_endpoint(client: TestClient) -> None:
    client.post("/api/seed/mid-atlantic-demos")
    response = client.post("/api/seed/demo-push-subscriptions")
    assert response.status_code == 200
    body = response.json()
    assert body["clinician_count"] >= 10
    assert body["created"] + body["existing"] >= 10


def test_admin_dashboard_includes_ensure_demo_push_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "ensure-demo-push-btn" in html.text
    assert "Ensure demo push subscriptions" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-push-subscriptions" in js.text


def test_deploy_checklist_mentions_demo_push_subscriptions(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("Ensure demo push subscriptions" in step for step in steps)
