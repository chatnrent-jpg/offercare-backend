from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.seed import seed_all_mid_atlantic_demos
from app.services.demo_environment import build_demo_environment_status, run_full_demo_setup
from app.services.states import supported_states


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_run_full_demo_setup_loads_seed_portal_and_push(db: Session) -> None:
    payload = run_full_demo_setup(db)
    assert payload["seed"]["count"] == 10
    assert set(payload["seed"]["states"]) == set(supported_states())
    assert payload["seed"]["portal_accounts"]["clinician_count"] >= 10
    assert payload["push_subscriptions"]["clinician_count"] >= 10
    assert payload["status"]["loaded"] is True
    assert payload["status"]["portal_ready"] is True
    assert payload["status"]["push_subscriptions_ready"] is True


def test_run_full_demo_setup_sends_matched_push(db: Session) -> None:
    payload = run_full_demo_setup(db)
    assert payload["matched_push"]["offer_count"] == 10
    assert payload["matched_push"]["matched_push_alerts_sent"] >= 10


def test_run_full_demo_setup_can_skip_matched_push(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    payload = run_full_demo_setup(db, notify_matched=False)
    assert payload["matched_push"]["offer_count"] == 10
    assert payload["matched_push"]["matched_push_alerts_sent"] == 0


def test_demo_setup_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/demo-setup")
    assert response.status_code == 200
    body = response.json()
    assert body["seed"]["count"] == 10
    assert body["push_subscriptions"]["clinician_count"] >= 10
    assert body["matched_push"]["offer_count"] == 10
    assert body["status"]["loaded"] is True


def test_demo_setup_endpoint_can_skip_notify(client: TestClient) -> None:
    response = client.post("/api/seed/demo-setup?notify_matched=false")
    assert response.status_code == 200
    body = response.json()
    assert body["matched_push"]["matched_push_alerts_sent"] == 0


def test_admin_dashboard_includes_run_demo_setup_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "run-demo-setup-btn" in html.text
    assert "Run full demo setup" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-setup" in js.text


def test_deploy_checklist_mentions_full_demo_setup(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("Run full demo setup" in step for step in steps)


def test_demo_status_next_steps_mention_full_demo_setup(client: TestClient) -> None:
    client.post("/api/seed/demo-setup")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("Run full demo setup" in step for step in steps)
