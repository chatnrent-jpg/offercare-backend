from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicalPlacementLedger, OfferCareJobOffer
from app.services.demo_environment import reset_demo_environment, run_full_demo_setup
from app.services.shift_lock import lock_shift_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_reset_demo_environment_unlocks_locked_shift(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status_offer = None
    from app.services.demo_environment import build_demo_environment_status

    for row in build_demo_environment_status(db)["offers"]:
        if row["facility_name"] == "Paramus SNF at Bergen":
            status_offer = row
            break
    assert status_offer is not None
    from app.models import MarylandProvider

    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == status_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(status_offer["offer_id"]))
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == status_offer["offer_id"]).first()
    assert offer.compliance_lock_status != "BROADCASTING"

    payload = reset_demo_environment(db)
    assert payload["offer_count"] == 10
    assert payload["offers_reset"] >= 1
    assert payload["placements_cleared"] >= 1
    db.refresh(offer)
    assert offer.compliance_lock_status == "BROADCASTING"
    assert offer.assigned_provider_id is None


def test_reset_demo_environment_is_idempotent_when_already_broadcasting(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    first = reset_demo_environment(db)
    second = reset_demo_environment(db)
    assert second["offer_count"] == 10
    assert second["offers_reset"] == 0
    assert second["placements_cleared"] == 0
    assert first["offer_count"] == 10


def test_demo_reset_endpoint(client: TestClient, db: Session) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    from app.services.demo_environment import build_demo_environment_status
    from app.models import MarylandProvider

    nj_offer = next(
        row for row in build_demo_environment_status(db)["offers"] if row["facility_name"] == "Paramus SNF at Bergen"
    )
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))
    response = client.post("/api/seed/demo-reset")
    assert response.status_code == 200
    body = response.json()
    assert body["offer_count"] == 10
    assert body["offers_reset"] >= 1
    assert body["placements_cleared"] >= 1


def test_admin_dashboard_includes_reset_demo_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "reset-demo-btn" in html.text
    assert "Reset demo environment" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-reset" in js.text


def test_deploy_checklist_mentions_demo_reset(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("Reset demo environment" in step for step in steps)


def test_demo_status_next_steps_mention_reset(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("Reset demo environment" in step for step in steps)
