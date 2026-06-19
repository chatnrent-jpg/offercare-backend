from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
    build_demo_environment_status,
    build_demo_ready_gate,
    build_demo_walkthrough_script,
    run_full_demo_setup,
)
from app.services.shift_lock import lock_shift_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_demo_ready_gate_not_ready_when_shift_locked(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    offer = status["offers"][0]
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(offer["offer_id"]))
    gate = build_demo_ready_gate(db)
    assert gate["ready"] is False
    assert gate["health_status"] == "yellow"
    assert gate["warning"]
    assert "walkthrough" in gate["warning"].lower()


def test_build_demo_ready_gate_ready_after_full_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    gate = build_demo_ready_gate(db)
    assert gate["ready"] is True
    assert gate["health_status"] == "green"
    assert gate["health_label"] == "READY"
    assert gate["warning"] is None


def test_demo_walkthrough_includes_ready_gate_fields(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    script = build_demo_walkthrough_script(db)
    assert script["demo_ready"] is True
    assert script["health_status"] == "green"
    assert script["health_label"] == "READY"
    assert script["demo_ready_warning"] is None


def test_demo_ready_gate_endpoint(client: TestClient) -> None:
    response = client.get("/api/seed/demo-ready-gate")
    assert response.status_code == 200
    body = response.json()
    assert "ready" in body
    assert "health_status" in body
    assert "health_label" in body
    assert "summary" in body
    assert "issues" in body


def test_demo_walkthrough_endpoint_includes_gate_after_setup(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-walkthrough")
    assert response.status_code == 200
    body = response.json()
    assert body["demo_ready"] is True
    assert body["health_status"] == "green"
    assert body["health_label"] == "READY"


def test_admin_dashboard_includes_demo_ready_gate(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "confirmDemoReadyExport" in text
    assert "/api/seed/demo-ready-gate" in text


def test_deploy_checklist_mentions_demo_ready_gate(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("demo-ready gate" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_demo_ready_gate(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("demo-ready gate" in step.lower() for step in steps)
