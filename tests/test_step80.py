from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
    build_demo_environment_status,
    demo_walkthrough_intact,
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


def test_demo_walkthrough_intact_when_green(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    health = build_demo_environment_status(db)["health"]
    assert health["status"] == "green"
    assert demo_walkthrough_intact(health) is True


def test_demo_walkthrough_intact_when_only_locked_shift_issue(db: Session) -> None:
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
    assert health["present_facility_count"] == 10
    assert demo_walkthrough_intact(health) is True
    assert any("per-row reset" in hint.lower() for hint in health["gate_hints"])


def test_demo_walkthrough_not_intact_when_facility_missing(db: Session) -> None:
    health = {
        "status": "yellow",
        "issues": ["3/10 demo facilities present"],
        "present_facility_count": 3,
        "expected_facility_count": 10,
    }
    assert demo_walkthrough_intact(health) is False


def test_admin_dashboard_gates_per_row_reset(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "confirmDemoReadyResetOffer" in text
    assert "demoWalkthroughIntact" in text
    assert "data-facility-name" in text
    assert "Per-row reset cancelled" in text


def test_deploy_checklist_mentions_per_row_reset_gate(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any(
        "per-row reset" in step.lower() and "intact walkthrough" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_per_row_reset_gate(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any(
        "per-row reset" in step.lower() and "intact walkthrough" in step.lower()
        for step in steps
    )


def test_demo_reset_offer_endpoint_still_works_when_walkthrough_intact(
    client: TestClient, db: Session
) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    offer = status["offers"][0]
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(offer["offer_id"]))

    health = client.get("/api/seed/demo-status").json()["health"]
    assert demo_walkthrough_intact(health) is True

    locked = next(row for row in status["offers"] if row["offer_id"] == offer["offer_id"])
    response = client.post(f"/api/seed/demo-reset-offer?offer_id={locked['offer_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["offers_reset"] == 1
    assert body["offer_row"]["loaded"] is True
