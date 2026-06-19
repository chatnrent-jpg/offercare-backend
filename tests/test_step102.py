from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import DEMO_GATE_DEFINITIONS, run_full_demo_setup


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_run_full_demo_setup_status_includes_demo_gates(db: Session) -> None:
    payload = run_full_demo_setup(db, notify_matched=False)
    demo_gates = payload["status"]["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert demo_gates["health_status"] == "green"
    assert demo_gates["clipboard_text"]
    assert len(demo_gates["gates"]) == 9


def test_demo_setup_endpoint_status_includes_demo_gates(client: TestClient) -> None:
    response = client.post("/api/seed/demo-setup?notify_matched=false")
    assert response.status_code == 200
    demo_gates = response.json()["status"]["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == 9
    assert "clipboard_text" in demo_gates


def test_demo_setup_endpoint_status_demo_gates_reflect_green_health(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    demo_gates = client.post("/api/seed/demo-setup?notify_matched=false").json()["status"]["demo_gates"]
    assert any(row["id"] == "reset_environment" and row["active"] for row in demo_gates["gates"])
    assert any(row["id"] == "export_walkthrough" and not row["active"] for row in demo_gates["gates"])


def test_deploy_checklist_demo_steps_mention_setup_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "run full demo setup returns status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_setup_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "run full demo setup returns status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_admin_app_js_renders_demo_gates_after_setup(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    handler = js.text.split("runDemoSetupBtn?.addEventListener")[1].split("resetDemoBtn?.addEventListener")[0]
    assert "renderDemoStatus(data.status)" in handler
