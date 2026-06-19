from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import build_demo_ready_gate, run_full_demo_setup


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_demo_ready_gate_green_after_full_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    gate = build_demo_ready_gate(db)
    assert gate["ready"] is True
    assert gate["health_status"] == "green"


def test_demo_reset_endpoint_still_works_when_health_green(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    gate = client.get("/api/seed/demo-ready-gate").json()
    assert gate["ready"] is True

    response = client.post("/api/seed/demo-reset")
    assert response.status_code == 200
    body = response.json()
    assert body["offer_count"] == 10


def test_admin_dashboard_gates_reset_demo_environment(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "confirmDemoReadyReset" in text
    assert "confirmDemoReadyReset(\"Reset demo environment\")" in text
    assert "Demo reset cancelled" in text
    assert "health.status !== \"green\"" in text


def test_deploy_checklist_mentions_reset_gate(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any(
        "reset gate" in step.lower() and "reset demo environment" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_reset_gate(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any(
        "reset gate" in step.lower() and "reset demo environment" in step.lower()
        for step in steps
    )


def test_demo_ready_gate_not_ready_skips_reset_confirm_logic(client: TestClient) -> None:
    response = client.get("/api/seed/demo-ready-gate")
    assert response.status_code == 200
    gate = response.json()
    if not gate["ready"]:
        assert gate["health_status"] in {"yellow", "red", "pending"}
