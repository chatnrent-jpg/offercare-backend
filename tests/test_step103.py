from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import DEMO_GATE_DEFINITIONS, reset_demo_environment, run_full_demo_setup


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_reset_demo_environment_service_still_returns_reset_counts(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = reset_demo_environment(db)
    assert payload["offer_count"] == 10
    assert "offers_reset" in payload
    assert "placements_cleared" in payload
    assert "status" not in payload


def test_demo_reset_endpoint_status_includes_demo_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.post("/api/seed/demo-reset")
    assert response.status_code == 200
    body = response.json()
    demo_gates = body["status"]["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert "clipboard_text" in demo_gates


def test_demo_reset_endpoint_status_demo_gates_reflect_green_health(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    demo_gates = client.post("/api/seed/demo-reset").json()["status"]["demo_gates"]
    assert demo_gates["health_status"] == "green"
    assert any(row["id"] == "reset_environment" and row["active"] for row in demo_gates["gates"])


def test_deploy_checklist_demo_steps_mention_reset_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "reset demo environment returns status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_reset_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "reset demo environment returns status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_admin_app_js_renders_demo_gates_after_reset(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    handler = js.text.split("resetDemoBtn?.addEventListener")[1].split("copyDemoLinksBtn?.addEventListener")[0]
    assert "renderDemoStatus(data.status)" in handler
