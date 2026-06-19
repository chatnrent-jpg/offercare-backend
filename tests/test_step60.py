from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicalPlacementLedger, MarylandProvider, OfferCareJobOffer
from app.services.demo_environment import (
    build_demo_environment_status,
    run_demo_lock_smoke_test,
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


def test_run_demo_lock_smoke_test_locks_first_broadcasting_shift(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = run_demo_lock_smoke_test(db)
    assert payload["ok"] is True
    assert payload["status"] == "locked"
    assert payload["placement_verified"] is True
    assert payload["compliance_lock_status"] == "LOCKED"
    assert payload["vms_submission_status"] == "PENDING"
    assert payload["clinician_email"]
    assert payload["placement_id"]

    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == UUID(payload["offer_id"])).first()
    placement = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.placement_id == UUID(payload["placement_id"]))
        .first()
    )
    assert offer.compliance_lock_status == "LOCKED"
    assert placement is not None
    assert str(placement.offer_id) == payload["offer_id"]


def test_run_demo_lock_smoke_test_targets_specific_offer(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    nj_offer = next(
        row for row in build_demo_environment_status(db)["offers"] if row["facility_name"] == "Paramus SNF at Bergen"
    )
    payload = run_demo_lock_smoke_test(db, offer_id=UUID(nj_offer["offer_id"]))
    assert payload["ok"] is True
    assert payload["facility_name"] == "Paramus SNF at Bergen"
    assert payload["clinician_email"] == nj_offer["demo_clinician_email"]


def test_run_demo_lock_smoke_test_fails_when_shift_already_locked(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    nj_offer = next(
        row for row in build_demo_environment_status(db)["offers"] if row["facility_name"] == "Paramus SNF at Bergen"
    )
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))

    payload = run_demo_lock_smoke_test(db, offer_id=UUID(nj_offer["offer_id"]))
    assert payload["ok"] is False
    assert payload["status"] == "already_locked"


def test_demo_lock_smoke_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.post("/api/seed/demo-lock-smoke")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "locked"
    assert body["placement_verified"] is True


def test_demo_lock_smoke_endpoint_accepts_offer_id(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    response = client.post(f"/api/seed/demo-lock-smoke?offer_id={nj_offer['offer_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["facility_name"] == "Paramus SNF at Bergen"
    assert body["clinician_email"] == nj_offer["demo_clinician_email"]


def test_admin_dashboard_includes_demo_lock_smoke_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "demo-lock-smoke-btn" in html.text
    assert "Smoke test demo lock" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-lock-smoke" in js.text


def test_deploy_checklist_mentions_demo_lock_smoke(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("smoke test demo lock" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_lock_smoke(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("smoke test demo lock" in step.lower() for step in steps)
