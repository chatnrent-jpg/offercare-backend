from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
    build_demo_ready_gate,
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


def test_demo_ready_gate_not_ready_when_shift_locked(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    from app.services.demo_environment import build_demo_environment_status

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


def test_demo_setup_endpoint_still_runs_when_health_not_green(client: TestClient, db: Session) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    offer = status["offers"][0]
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(offer["offer_id"]))
    gate = client.get("/api/seed/demo-ready-gate").json()
    assert gate["ready"] is False

    response = client.post("/api/seed/demo-setup?notify_matched=false")
    assert response.status_code == 200
    body = response.json()
    assert body["status"]["health"]["status"] == "green"


def test_admin_dashboard_gates_run_demo_setup(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "runDemoSetupBtn" in text
    assert "confirmDemoReadyExport(\"Run full demo setup\")" in text
    assert "Demo setup cancelled" in text


def test_deploy_checklist_mentions_setup_gate(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any(
        "demo-ready gate" in step.lower() and "run full demo setup" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_setup_gate(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any(
        "demo-ready gate" in step.lower() and "run full demo setup" in step.lower()
        for step in steps
    )


def test_demo_ready_gate_ready_after_full_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    gate = build_demo_ready_gate(db)
    assert gate["ready"] is True
    assert gate["warning"] is None
