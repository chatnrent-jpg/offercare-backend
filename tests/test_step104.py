from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
    DEMO_GATE_DEFINITIONS,
    reset_demo_offer,
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


def test_reset_demo_offer_service_still_returns_offer_row_without_status(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    from app.services.demo_environment import build_demo_environment_status

    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    payload = reset_demo_offer(db, UUID(nj_offer["offer_id"]))
    assert payload is not None
    assert payload["offer_row"] is not None
    assert "status" not in payload


def test_demo_reset_offer_endpoint_status_includes_demo_gates(client: TestClient, db: Session) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))

    response = client.post(f"/api/seed/demo-reset-offer?offer_id={nj_offer['offer_id']}")
    assert response.status_code == 200
    body = response.json()
    demo_gates = body["status"]["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert "clipboard_text" in demo_gates
    assert body["offer_row"]["loaded"] is True


def test_demo_reset_offer_endpoint_status_demo_gates_reflect_green_after_unlock(client: TestClient, db: Session) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))

    demo_gates = client.post(
        f"/api/seed/demo-reset-offer?offer_id={nj_offer['offer_id']}"
    ).json()["status"]["demo_gates"]
    assert demo_gates["health_status"] == "green"
    assert any(row["id"] == "reset_environment" and row["active"] for row in demo_gates["gates"])


def test_deploy_checklist_demo_steps_mention_reset_offer_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "per-row reset returns status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_reset_offer_status_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "per-row reset returns status with the embedded demo_gates gate matrix" in step.lower()
        for step in steps
    )


def test_admin_app_js_renders_demo_gates_after_reset_offer(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    handler = js.text.split("async function runDemoResetOffer")[1].split("function wireDemoResetOfferButtons")[0]
    assert "renderDemoStatus(data.status)" in handler
