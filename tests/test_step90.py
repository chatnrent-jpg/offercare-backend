from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_GATE_DEFINITIONS,
    build_demo_environment_status,
    build_demo_gates_summary,
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


def test_demo_health_includes_gate_count_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    health = build_demo_environment_status(db)["health"]
    assert health["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert health["gate_count"] == 9


def test_demo_gates_summary_includes_gate_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    summary = build_demo_gates_summary(db)
    assert summary["gate_count"] == 9
    assert len(summary["gates"]) == summary["gate_count"]


def test_demo_walkthrough_includes_full_gate_matrix(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    script = build_demo_walkthrough_script(db)
    markdown = script["markdown"]
    assert "### Gate matrix" in markdown
    assert "Total confirmation gates: 9" in markdown
    assert "Copy demo portal links (`copy_demo_links`)" in markdown
    assert "Ensure demo push subscriptions (`ensure_push`)" in markdown
    assert "active now" in markdown
    assert "inactive" in markdown


def test_demo_gates_endpoint_includes_gate_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-gates").json()
    assert body["gate_count"] == 9


def test_demo_status_includes_gate_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    health = client.get("/api/seed/demo-status").json()["health"]
    assert health["gate_count"] == 9


def test_demo_status_csv_includes_gate_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status.csv")
    assert response.status_code == 200
    assert "health_gate_count" in response.text
    assert ",9" in response.text or ", 9" in response.text or "9\n" in response.text


def test_admin_dashboard_renders_gate_count(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "gate_count" in js.text
    assert "demo-health-gate-count" in js.text
    assert "Confirmation gates:" in js.text


def test_deploy_checklist_mentions_walkthrough_gate_matrix(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any("gate matrix" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_walkthrough_gate_matrix(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any("gate matrix" in step.lower() for step in steps)
