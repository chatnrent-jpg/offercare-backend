from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    build_demo_walkthrough_script,
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


def test_admin_app_js_gate_panel_header_shows_admin_action_count(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "demo_admin_action_count" in text
    assert "${demoGates.gate_count} gates · ${adminActionCount} admin actions" in text
    assert "cataloged actions return embedded demo_gates" in text


def test_demo_gates_payload_includes_admin_action_count_for_panel_header(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    demo_gates = client.get("/api/seed/demo-gates").json()
    assert demo_gates["gate_count"] == 9
    assert demo_gates["demo_admin_action_count"] == 8


def test_demo_status_demo_gates_include_admin_action_count_for_panel_header(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    demo_gates = client.get("/api/seed/demo-status").json()["demo_gates"]
    assert demo_gates["demo_admin_action_count"] == 8


def test_deploy_checklist_demo_gates_include_admin_action_count_for_panel_header(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    demo_gates = client.get("/api/deploy/checklist").json()["demo_gates"]
    assert demo_gates["demo_admin_action_count"] == 8


def test_demo_walkthrough_gate_matrix_section_includes_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    markdown = build_demo_walkthrough_script(db)["markdown"]
    assert "### Gate matrix" in markdown
    assert "Demo admin actions catalog: 8" in markdown


def test_demo_status_next_steps_mention_panel_gate_header_admin_action_count(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "demo environment panel gate matrix header shows demo admin action count" in step.lower()
        for step in steps
    )


def test_deploy_checklist_demo_steps_mention_panel_gate_header_admin_action_count(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "deploy walkthrough panel gate matrix header shows demo admin action count" in step.lower()
        for step in steps
    )
    assert any(
        "demo environment panel gate matrix header shows demo admin action count" in step.lower()
        for step in steps
    )
