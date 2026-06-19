from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
    DEMO_GATE_DEFINITIONS,
    build_demo_active_gates,
    build_demo_environment_status,
    build_demo_gate_hints,
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


def test_demo_gate_definitions_include_copy_demo_links() -> None:
    gate = next(row for row in DEMO_GATE_DEFINITIONS if row["id"] == "copy_demo_links")
    assert gate["action"] == "Copy demo portal links"
    assert gate["confirm_when"] == "health_not_green"


def test_build_demo_active_gates_includes_copy_demo_links_when_not_green() -> None:
    active = build_demo_active_gates(
        {
            "status": "yellow",
            "issues": ["Paramus SNF at Bergen locked"],
            "present_facility_count": 10,
            "expected_facility_count": 10,
            "broadcasting_facility_count": 9,
        }
    )
    assert "copy_demo_links" in active
    assert "export_walkthrough" in active


def test_build_demo_active_gates_excludes_copy_demo_links_when_green() -> None:
    active = build_demo_active_gates(
        {
            "status": "green",
            "issues": [],
            "present_facility_count": 10,
            "expected_facility_count": 10,
            "broadcasting_facility_count": 10,
        }
    )
    assert "copy_demo_links" not in active


def test_build_demo_gate_hints_include_copy_demo_links_when_not_green() -> None:
    hints = build_demo_gate_hints(
        {
            "status": "yellow",
            "issues": ["Paramus SNF at Bergen locked"],
            "present_facility_count": 10,
            "expected_facility_count": 10,
            "broadcasting_facility_count": 9,
        }
    )
    assert any("copy demo portal links" in hint.lower() for hint in hints)


def test_demo_gates_endpoint_lists_copy_demo_links_when_locked(db: Session, client: TestClient) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    offer = status["offers"][0]
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(offer["offer_id"]))

    body = client.get("/api/seed/demo-gates").json()
    copy_gate = next(row for row in body["gates"] if row["id"] == "copy_demo_links")
    assert copy_gate["active"] is True
    assert "copy_demo_links" in body["active_gates"]


def test_admin_dashboard_gates_copy_demo_links(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "copyDemoLinksBtn" in text
    assert 'confirmDemoReadyExport("Copy demo portal links")' in text
    assert "Copy cancelled — run full demo setup until health is green" in text


def test_deploy_checklist_mentions_copy_demo_links_gate(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any("copy demo portal links" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_copy_demo_links_gate(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any("copy demo portal links" in step.lower() for step in steps)


def test_demo_links_endpoint_still_works(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-links")
    assert response.status_code == 200
    body = response.json()
    assert body["offers"]
    assert body["portal_login_url"]
