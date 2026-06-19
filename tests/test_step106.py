from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_GATE_DEFINITIONS,
    notify_matched_on_demo_environment,
    notify_matched_on_demo_offer,
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


def test_notify_matched_services_still_return_counts_without_demo_status(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    from app.services.demo_environment import build_demo_environment_status

    status = build_demo_environment_status(db)
    offer_id = next(row["offer_id"] for row in status["offers"] if row.get("loaded"))
    bulk = notify_matched_on_demo_environment(db)
    per_row = notify_matched_on_demo_offer(db, UUID(offer_id))
    assert bulk["offer_count"] == 10
    assert "demo_status" not in bulk
    assert per_row is not None
    assert "demo_status" not in per_row


def test_notify_matched_demos_endpoint_demo_status_includes_demo_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.post("/api/seed/notify-matched-demos")
    assert response.status_code == 200
    body = response.json()
    demo_gates = body["demo_status"]["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert "clipboard_text" in demo_gates


def test_demo_notify_matched_offer_endpoint_demo_status_includes_demo_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    offer_id = next(row["offer_id"] for row in status["offers"] if row.get("loaded"))
    response = client.post(f"/api/seed/demo-notify-matched?offer_id={offer_id}")
    assert response.status_code == 200
    demo_gates = response.json()["demo_status"]["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == 9
    assert "notify_matched" in demo_gates["active_gates"]


def test_deploy_checklist_demo_steps_mention_notify_matched_demo_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "notify matched returns demo_status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_notify_matched_demo_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "notify matched returns demo_status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_admin_app_js_renders_demo_gates_after_notify_matched(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    per_row = js.text.split("async function runDemoNotifyMatched")[1].split("function wireDemoNotifyMatchedButtons")[0]
    bulk = js.text.split("notifyMatchedDemosBtn?.addEventListener")[1].split("demoLockSmokeBtn?.addEventListener")[0]
    assert "renderDemoStatus(data.demo_status)" in per_row
    assert "renderDemoStatus(data.demo_status)" in bulk
