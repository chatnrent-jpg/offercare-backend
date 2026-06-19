from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
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


def test_build_demo_gate_hints_includes_lock_test_when_intact() -> None:
    hints = build_demo_gate_hints(
        {
            "status": "green",
            "issues": [],
            "present_facility_count": 10,
            "expected_facility_count": 10,
            "broadcasting_facility_count": 10,
        }
    )
    assert any("lock test" in hint.lower() for hint in hints)
    assert any("per-row reset" in hint.lower() for hint in hints)


def test_demo_health_gate_hints_include_lock_test_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    health = build_demo_environment_status(db)["health"]
    assert demo_walkthrough_intact(health) is True
    assert any("lock test" in hint.lower() for hint in health["gate_hints"])


def test_admin_dashboard_gates_lock_test(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "confirmDemoReadyLockTest" in text
    assert "Lock test cancelled" in text
    assert "demo-lock-smoke-offer-btn" in text
    assert "data-facility-name" in text


def test_deploy_checklist_mentions_lock_test_gate(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any(
        "lock test" in step.lower() and "intact walkthrough" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_lock_test_gate(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any(
        "lock test" in step.lower() and "intact walkthrough" in step.lower()
        for step in steps
    )


def test_demo_lock_smoke_endpoint_still_works_when_walkthrough_intact(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    health = client.get("/api/seed/demo-status").json()["health"]
    assert demo_walkthrough_intact(health) is True

    response = client.post("/api/seed/demo-lock-smoke")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["offer_row"]["resettable"] is True
