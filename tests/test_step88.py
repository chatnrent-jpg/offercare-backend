from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_GATE_DEFINITIONS,
    build_demo_active_gates,
    build_demo_environment_status,
    build_demo_gate_hints,
    demo_walkthrough_intact,
    run_full_demo_setup,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_demo_gate_definitions_include_ensure_push() -> None:
    gate = next(row for row in DEMO_GATE_DEFINITIONS if row["id"] == "ensure_push")
    assert gate["action"] == "Ensure demo push subscriptions"
    assert gate["confirm_when"] == "walkthrough_intact"


def test_build_demo_active_gates_includes_ensure_push_when_intact() -> None:
    health = {
        "status": "green",
        "issues": [],
        "present_facility_count": 10,
        "expected_facility_count": 10,
        "broadcasting_facility_count": 10,
    }
    active = build_demo_active_gates(health)
    assert "ensure_push" in active


def test_build_demo_gate_hints_include_ensure_push_when_intact() -> None:
    hints = build_demo_gate_hints(
        {
            "status": "green",
            "issues": [],
            "present_facility_count": 10,
            "expected_facility_count": 10,
            "broadcasting_facility_count": 10,
        }
    )
    assert any("ensure demo push subscriptions" in hint.lower() for hint in hints)


def test_demo_health_includes_ensure_push_gate_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    health = build_demo_environment_status(db)["health"]
    assert demo_walkthrough_intact(health) is True
    assert "ensure_push" in health["active_gates"]


def test_demo_gates_endpoint_lists_ensure_push_gate(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-gates").json()
    ensure_gate = next(row for row in body["gates"] if row["id"] == "ensure_push")
    assert ensure_gate["active"] is True
    assert "ensure_push" in body["active_gates"]


def test_admin_dashboard_gates_ensure_push(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "confirmDemoReadyEnsurePush" in text
    assert "Ensure push subscriptions cancelled" in text
    assert "ensure-demo-push-btn" in text


def test_deploy_checklist_mentions_ensure_push_gate(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "ensure demo push subscriptions" in step.lower() and "intact walkthrough" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_ensure_push_gate(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "ensure demo push subscriptions" in step.lower() and "intact walkthrough" in step.lower()
        for step in steps
    )


def test_demo_push_subscriptions_endpoint_still_works_when_walkthrough_intact(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    health = client.get("/api/seed/demo-status").json()["health"]
    assert demo_walkthrough_intact(health) is True

    response = client.post("/api/seed/demo-push-subscriptions")
    assert response.status_code == 200
    body = response.json()
    assert body["clinician_count"] > 0
