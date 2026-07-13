from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider, OfferCareJobOffer
from app.services.demo_environment import (
    build_demo_environment_status,
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


def test_run_full_demo_setup_resets_locked_shift_before_seed(db: Session) -> None:
    first = run_full_demo_setup(db, notify_matched=False)
    nj_offer = next(
        row for row in first["status"]["offers"] if row["facility_name"] == "Paramus SNF at Bergen"
    )
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))

    second = run_full_demo_setup(db, notify_matched=False)
    assert second["reset"]["offers_reset"] >= 1
    assert second["reset"]["placements_cleared"] >= 1
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == nj_offer["offer_id"]).first()
    db.refresh(offer)
    assert offer.compliance_lock_status == "BROADCASTING"
    assert offer.assigned_provider_id is None


def test_run_full_demo_setup_includes_reset_payload(db: Session) -> None:
    payload = run_full_demo_setup(db, notify_matched=False)
    assert payload["reset"]["offer_count"] == 10
    assert payload["reset"]["offers_reset"] == 0
    assert payload["reset"]["placements_cleared"] == 0


def test_build_demo_walkthrough_script_lists_all_demo_shifts(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    script = build_demo_walkthrough_script(db)
    assert script["offer_count"] == 10
    assert "# VettedMe Mid-Atlantic Demo Walkthrough" in script["markdown"]
    assert "Paramus SNF at Bergen" in script["markdown"]
    assert "nj.snf.cna.a@offercare.demo" in script["markdown"]
    assert "/portal/?offer=" in script["markdown"]
    assert "Reset demo environment" in script["markdown"]


def test_demo_walkthrough_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-walkthrough")
    assert response.status_code == 200
    body = response.json()
    assert body["offer_count"] == 10
    assert "Saint Jude's ICU" in body["markdown"]


def test_demo_setup_endpoint_includes_reset(client: TestClient) -> None:
    response = client.post("/api/seed/demo-setup?notify_matched=false")
    assert response.status_code == 200
    body = response.json()
    assert body["reset"]["offer_count"] == 10


def test_admin_dashboard_includes_copy_walkthrough_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "copy-demo-walkthrough-btn" in html.text
    assert "Copy demo walkthrough" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-walkthrough" in js.text


def test_deploy_checklist_mentions_demo_walkthrough(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("walkthrough" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_walkthrough(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("walkthrough" in step.lower() for step in steps)
