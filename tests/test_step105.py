from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_GATE_DEFINITIONS,
    run_demo_lock_smoke_test,
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


def test_run_demo_lock_smoke_service_still_returns_lock_status_without_demo_status(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = run_demo_lock_smoke_test(db)
    assert payload["ok"] is True
    assert payload["status"] == "locked"
    assert "demo_status" not in payload


def test_demo_lock_smoke_endpoint_demo_status_includes_demo_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.post("/api/seed/demo-lock-smoke")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    demo_gates = body["demo_status"]["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert "clipboard_text" in demo_gates
    assert body["offer_row"]["resettable"] is True


def test_demo_lock_smoke_endpoint_demo_gates_reflect_intact_walkthrough_after_lock(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    body = client.post(f"/api/seed/demo-lock-smoke?offer_id={nj_offer['offer_id']}").json()
    demo_gates = body["demo_status"]["demo_gates"]
    assert demo_gates["walkthrough_intact"] is True
    assert "reset_offer" in demo_gates["active_gates"]
    assert "lock_test" in demo_gates["active_gates"]
    assert "export_walkthrough" in demo_gates["active_gates"]


def test_deploy_checklist_demo_steps_mention_lock_smoke_demo_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "lock test returns demo_status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_lock_smoke_demo_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "lock test returns demo_status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_admin_app_js_renders_demo_gates_after_lock_smoke(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    handler = js.text.split("async function runDemoLockSmoke")[1].split("function wireDemoLockSmokeButtons")[0]
    assert "renderDemoStatus(data.demo_status)" in handler
