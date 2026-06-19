from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
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


def test_build_demo_gate_hints_when_green() -> None:
    hints = build_demo_gate_hints({"status": "green", "issues": []})
    assert any("export" in hint.lower() for hint in hints)
    assert any("reset demo environment" in hint.lower() for hint in hints)
    assert any("per-row reset" in hint.lower() for hint in hints)
    assert any("lock test" in hint.lower() for hint in hints)


def test_build_demo_gate_hints_when_not_green() -> None:
    hints = build_demo_gate_hints(
        {
            "status": "red",
            "issues": ["No demo facilities loaded"],
            "present_facility_count": 0,
            "expected_facility_count": 10,
        }
    )
    assert any("export walkthrough" in hint.lower() for hint in hints)
    assert any("run full demo setup" in hint.lower() for hint in hints)
    assert any("reset demo environment proceeds" in hint.lower() for hint in hints)
    assert not any("per-row reset" in hint.lower() for hint in hints)


def test_demo_health_includes_gate_hints_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    health = build_demo_environment_status(db)["health"]
    assert health["gate_hints"]
    assert any("reset demo environment" in hint.lower() for hint in health["gate_hints"])


def test_demo_health_gate_hints_when_shift_locked(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    offer = status["offers"][0]
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(offer["offer_id"]))

    health = build_demo_environment_status(db)["health"]
    assert health["status"] == "yellow"
    assert any("export walkthrough" in hint.lower() for hint in health["gate_hints"])
    assert any("run full demo setup" in hint.lower() for hint in health["gate_hints"])


def test_demo_status_endpoint_includes_gate_hints(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    hints = response.json()["health"]["gate_hints"]
    assert len(hints) >= 2


def test_demo_status_csv_includes_gate_hints(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status.csv")
    assert response.status_code == 200
    assert "health_gate_hints" in response.text
    assert "Reset demo environment" in response.text


def test_admin_dashboard_renders_health_gate_hints(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "demo-health-gates" in js.text
    assert "gate_hints" in js.text
    css = client.get("/admin/styles.css")
    assert ".demo-health-gates" in css.text


def test_deploy_checklist_mentions_health_gate_summary(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("health badge" in step.lower() and "confirmation gates" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_health_gate_summary(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("health badge" in step.lower() and "confirmation gates" in step.lower() for step in steps)
