from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import DEMO_GATE_DEFINITIONS, run_full_demo_setup
from app.services.demo_push_subscriptions import ensure_demo_push_subscriptions


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_ensure_demo_push_subscriptions_service_still_returns_counts_without_demo_status(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = ensure_demo_push_subscriptions(db)
    assert payload["clinician_count"] > 0
    assert "demo_status" not in payload


def test_demo_push_subscriptions_endpoint_demo_status_includes_demo_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.post("/api/seed/demo-push-subscriptions")
    assert response.status_code == 200
    body = response.json()
    demo_gates = body["demo_status"]["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert "clipboard_text" in demo_gates


def test_demo_push_subscriptions_endpoint_demo_gates_list_ensure_push_gate(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    demo_gates = client.post("/api/seed/demo-push-subscriptions").json()["demo_status"]["demo_gates"]
    ensure_gate = next(row for row in demo_gates["gates"] if row["id"] == "ensure_push")
    assert ensure_gate["action"] == "Ensure demo push subscriptions"
    assert "ensure_push" in demo_gates["active_gates"]


def test_deploy_checklist_demo_steps_mention_ensure_push_demo_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "ensure demo push subscriptions returns demo_status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_ensure_push_demo_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "ensure demo push subscriptions returns demo_status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_admin_app_js_renders_demo_gates_after_ensure_push(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    handler = js.text.split("ensureDemoPushBtn?.addEventListener")[1].split("notifyMatchedDemosBtn?.addEventListener")[0]
    assert "renderDemoStatus(data.demo_status)" in handler
