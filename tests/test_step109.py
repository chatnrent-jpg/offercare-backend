from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_ADMIN_ACTION_DEMO_GATES,
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


def test_demo_walkthrough_includes_demo_actions_with_embedded_demo_gates(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    script = build_demo_walkthrough_script(db)
    markdown = script["markdown"]
    assert "### Demo actions with embedded demo_gates" in markdown
    assert "POST /api/seed/demo-setup" in markdown
    assert "`status.demo_gates`" in markdown
    assert "POST /api/seed/demo-lock-smoke" in markdown
    assert "`demo_status.demo_gates`" in markdown
    assert "POST /api/seed/demo-push-subscriptions" in markdown
    assert len(DEMO_ADMIN_ACTION_DEMO_GATES) == 8


def test_demo_admin_action_demo_gates_catalog_covers_all_mutating_actions() -> None:
    endpoints = {row["endpoint"] for row in DEMO_ADMIN_ACTION_DEMO_GATES}
    assert "POST /api/seed/demo-setup" in endpoints
    assert "POST /api/seed/demo-reset" in endpoints
    assert "POST /api/seed/demo-reset-offer" in endpoints
    assert "POST /api/seed/demo-lock-smoke" in endpoints
    assert "POST /api/seed/notify-matched-demos" in endpoints
    assert "POST /api/seed/demo-notify-matched" in endpoints
    assert "POST /api/seed/demo-portal-accounts" in endpoints
    assert "POST /api/seed/demo-push-subscriptions" in endpoints


def test_deploy_checklist_demo_steps_mention_all_demo_admin_actions_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "all demo admin actions return embedded demo_gates" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_all_demo_admin_actions_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "all demo admin actions return embedded demo_gates" in step.lower()
        for step in steps
    )


def test_demo_walkthrough_download_includes_demo_actions_section(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-walkthrough.md")
    assert response.status_code == 200
    assert "### Demo actions with embedded demo_gates" in response.text
