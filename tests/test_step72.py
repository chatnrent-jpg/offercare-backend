from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
    build_demo_environment_status,
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


def test_locked_demo_row_stays_resettable_when_loaded_false(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))

    status = build_demo_environment_status(db)
    locked = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    assert locked["loaded"] is False
    assert locked["compliance_lock_status"] == "LOCKED"
    assert locked["resettable"] is True
    assert locked["offer_id"]
    assert locked["matched_clinician_count"] > 0
    assert locked["demo_clinician_email"]


def test_locked_demo_row_enriched_after_lock_smoke(client: TestClient, db: Session) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))

    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    locked = next(row for row in response.json()["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    assert locked["loaded"] is False
    assert locked["compliance_lock_status"] == "LOCKED"
    assert locked["resettable"] is True
    assert locked["demo_clinician_email"]


def test_broadcasting_demo_row_not_resettable(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    broadcasting = next(row for row in status["offers"] if row["loaded"])
    assert broadcasting["compliance_lock_status"] == "BROADCASTING"
    assert broadcasting["resettable"] is False


def test_admin_dashboard_uses_locked_row_helpers(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "demoOfferStatusLabel" in text
    assert "demoOfferResettable" in text
    assert "demoOfferLockTestable" in text


def test_deploy_checklist_mentions_locked_row_reset_polish(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("loaded is false" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_locked_row_reset_polish(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("loaded is false" in step.lower() for step in steps)
