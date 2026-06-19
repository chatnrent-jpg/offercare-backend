from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
    build_demo_environment_status,
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


def test_reset_demo_offer_returns_broadcasting_offer_row(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))

    payload = reset_demo_offer(db, UUID(nj_offer["offer_id"]))
    assert payload is not None
    assert payload["offers_reset"] == 1
    assert payload["offer_row"] is not None
    assert payload["offer_row"]["facility_name"] == "Paramus SNF at Bergen"
    assert payload["offer_row"]["loaded"] is True
    assert payload["offer_row"]["resettable"] is False
    assert payload["offer_row"]["compliance_lock_status"] == "BROADCASTING"
    assert payload["offer_row"]["matched_clinician_count"] > 0
    assert payload["offer_row"]["demo_clinician_email"]


def test_reset_demo_offer_offer_row_idempotent_when_already_broadcasting(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    payload = reset_demo_offer(db, UUID(nj_offer["offer_id"]))
    assert payload is not None
    assert payload["offers_reset"] == 0
    assert payload["offer_row"] is not None
    assert payload["offer_row"]["loaded"] is True
    assert payload["offer_row"]["compliance_lock_status"] == "BROADCASTING"


def test_demo_reset_offer_endpoint_returns_offer_row(client: TestClient, db: Session) -> None:
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
    assert body["offer_row"]["facility_name"] == "Paramus SNF at Bergen"
    assert body["offer_row"]["loaded"] is True
    assert body["offer_row"]["resettable"] is False


def test_admin_dashboard_logs_reset_offer_row(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "Reset row broadcasting" in js.text
    assert "offer_row" in js.text


def test_deploy_checklist_mentions_reset_offer_row(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("offer_row" in step.lower() and "reset" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_reset_offer_row(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("offer_row" in step.lower() and "reset" in step.lower() for step in steps)
