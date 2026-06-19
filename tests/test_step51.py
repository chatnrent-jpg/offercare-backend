from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicianPushSubscription, MarylandProvider
from app.seed import DEMO_FACILITY_NAMES, seed_all_mid_atlantic_demos
from app.services.demo_environment import build_demo_environment_status
from app.services.push_subscriptions import register_push_subscription


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_demo_status_lists_all_ten_facilities_after_mid_atlantic_seed(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    payload = build_demo_environment_status(db)
    assert payload["loaded"] is True
    assert payload["facility_count"] == 10
    assert payload["expected_facility_count"] == 10
    assert len(payload["offers"]) == len(DEMO_FACILITY_NAMES)
    assert all(row["loaded"] for row in payload["offers"])
    assert len(payload["clinicians"]) >= 10


def test_demo_status_shows_matched_and_push_ready_counts(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    provider = db.query(MarylandProvider).filter(MarylandProvider.email == "nj.snf.cna.a@offercare.demo").first()
    db.query(ClinicianPushSubscription).filter(
        ClinicianPushSubscription.provider_id == provider.provider_id
    ).delete(synchronize_session=False)
    db.commit()

    payload = build_demo_environment_status(db)
    nj_offer = next(row for row in payload["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    assert nj_offer["matched_clinician_count"] >= 1
    assert nj_offer["push_ready_count"] == 0

    register_push_subscription(
        db,
        provider.provider_id,
        endpoint="https://push.example.test/step51-nj",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
    )
    refreshed = build_demo_environment_status(db)
    nj_refreshed = next(row for row in refreshed["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    assert nj_refreshed["push_ready_count"] >= 1


def test_demo_status_endpoint(client: TestClient) -> None:
    client.post("/api/seed/mid-atlantic-demos")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    body = response.json()
    assert body["facility_count"] == 10
    assert body["loaded"] is True
    assert len(body["offers"]) == 10
    assert len(body["clinicians"]) >= 10
    assert body["next_steps"]


def test_admin_dashboard_includes_demo_status_panel(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "demo-offers-table" in html.text
    assert "refresh-demo-status-btn" in html.text
    assert "Demo environment" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-status" in js.text
    assert "renderDemoStatus" in js.text


def test_deploy_checklist_mentions_demo_environment_status(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("Demo environment panel" in step for step in steps)
    assert any("Seed full demo environment" in step for step in steps)
