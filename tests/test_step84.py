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


def test_demo_gate_definitions_include_notify_matched() -> None:
    gate = next(row for row in DEMO_GATE_DEFINITIONS if row["id"] == "notify_matched")
    assert gate["action"] == "Notify matched"
    assert gate["confirm_when"] == "walkthrough_intact"


def test_build_demo_active_gates_includes_notify_matched_when_intact() -> None:
    health = {
        "status": "green",
        "issues": [],
        "present_facility_count": 10,
        "expected_facility_count": 10,
        "broadcasting_facility_count": 10,
    }
    active = build_demo_active_gates(health)
    assert "notify_matched" in active
    assert "lock_test" in active
    assert "reset_offer" in active


def test_build_demo_gate_hints_include_notify_matched_when_intact() -> None:
    hints = build_demo_gate_hints(
        {
            "status": "green",
            "issues": [],
            "present_facility_count": 10,
            "expected_facility_count": 10,
            "broadcasting_facility_count": 10,
        }
    )
    assert any("notify matched" in hint.lower() for hint in hints)


def test_demo_health_includes_notify_matched_gate_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    health = build_demo_environment_status(db)["health"]
    assert demo_walkthrough_intact(health) is True
    assert "notify_matched" in health["active_gates"]
    assert any("notify matched" in hint.lower() for hint in health["gate_hints"])


def test_demo_gates_endpoint_lists_notify_matched_gate(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-gates")
    assert response.status_code == 200
    body = response.json()
    notify_gate = next(row for row in body["gates"] if row["id"] == "notify_matched")
    assert notify_gate["active"] is True
    assert "notify_matched" in body["active_gates"]


def test_admin_dashboard_gates_notify_matched(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "confirmDemoReadyNotifyMatched" in text
    assert "Notify matched cancelled" in text
    assert "demo-notify-matched-offer-btn" in text
    assert 'data-facility-name="${row.facility_name}"' in text or "data-facility-name" in text


def test_deploy_checklist_mentions_notify_matched_gate(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any(
        "notify matched" in step.lower() and "intact walkthrough" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_notify_matched_gate(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any(
        "notify matched" in step.lower() and "intact walkthrough" in step.lower()
        for step in steps
    )


def test_demo_notify_matched_endpoints_still_work_when_walkthrough_intact(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    health = client.get("/api/seed/demo-status").json()["health"]
    assert demo_walkthrough_intact(health) is True

    status = client.get("/api/seed/demo-status").json()
    offer_id = next(row["offer_id"] for row in status["offers"] if row.get("loaded"))

    per_row = client.post(f"/api/seed/demo-notify-matched?offer_id={offer_id}")
    assert per_row.status_code == 200

    bulk = client.post("/api/seed/notify-matched-demos")
    assert bulk.status_code == 200
