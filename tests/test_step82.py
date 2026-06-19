from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
    DEMO_GATE_DEFINITIONS,
    build_demo_environment_status,
    build_demo_gates_summary,
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


def test_build_demo_gates_summary_when_green(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    summary = build_demo_gates_summary(db)
    assert summary["walkthrough_intact"] is True
    assert summary["health_status"] == "green"
    assert "reset_environment" in summary["active_gates"]
    assert "lock_test" in summary["active_gates"]
    assert "export_walkthrough" not in summary["active_gates"]
    assert len(summary["gates"]) == len(DEMO_GATE_DEFINITIONS)
    assert all("active" in row for row in summary["gates"])


def test_build_demo_gates_summary_when_locked_shift_only(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    offer = status["offers"][0]
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(offer["offer_id"]))

    summary = build_demo_gates_summary(db)
    assert summary["walkthrough_intact"] is True
    assert summary["health_status"] == "yellow"
    assert "export_walkthrough" in summary["active_gates"]
    assert "copy_demo_links" in summary["active_gates"]
    assert "run_full_setup" in summary["active_gates"]
    assert "reset_offer" in summary["active_gates"]
    assert "lock_test" in summary["active_gates"]
    assert "reset_environment" not in summary["active_gates"]


def test_demo_health_includes_active_gates_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    health = build_demo_environment_status(db)["health"]
    assert health["active_gates"]
    assert "reset_environment" in health["active_gates"]


def test_demo_gates_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-gates")
    assert response.status_code == 200
    body = response.json()
    assert body["walkthrough_intact"] is True
    assert body["health_status"] == "green"
    assert body["active_gates"]
    assert len(body["gates"]) == 9
    reset_gate = next(row for row in body["gates"] if row["id"] == "reset_environment")
    assert reset_gate["active"] is True


def test_demo_walkthrough_includes_gate_section(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    script = build_demo_walkthrough_script(db)
    markdown = script["markdown"]
    assert "## Admin confirmation gates" in markdown
    assert "Active now:" in markdown
    assert "### Gate matrix" in markdown
    assert "reset_environment" in markdown


def test_demo_status_csv_includes_active_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status.csv")
    assert response.status_code == 200
    assert "health_active_gates" in response.text
    assert "reset_environment" in response.text


def test_admin_dashboard_renders_active_gates(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "active_gates" in js.text
    assert "demo-health-active-gates" in js.text
    css = client.get("/admin/styles.css")
    assert ".demo-health-active-gates" in css.text


def test_deploy_checklist_mentions_demo_gates_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("/api/seed/demo-gates" in step for step in steps)


def test_demo_status_next_steps_mention_demo_gates_endpoint(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("/api/seed/demo-gates" in step for step in steps)
