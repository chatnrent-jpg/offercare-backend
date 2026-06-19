from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import build_demo_environment_status, run_full_demo_setup
from app.services.shift_lock import lock_shift_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_demo_health_includes_facility_counts_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    health = build_demo_environment_status(db)["health"]
    assert health["present_facility_count"] == 10
    assert health["broadcasting_facility_count"] == 10
    assert health["expected_facility_count"] == 10


def test_demo_health_facility_counts_when_one_shift_locked(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))

    health = build_demo_environment_status(db)["health"]
    assert health["present_facility_count"] == 10
    assert health["broadcasting_facility_count"] == 9
    assert health["expected_facility_count"] == 10
    assert health["status"] == "yellow"


def test_demo_status_endpoint_includes_health_facility_counts(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    health = response.json()["health"]
    assert health["present_facility_count"] == 10
    assert health["broadcasting_facility_count"] == 10
    assert health["expected_facility_count"] == 10


def test_demo_status_csv_includes_health_facility_counts(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status.csv")
    assert response.status_code == 200
    text = response.text.replace(" ", "")
    assert "health_present_facility_count,10" in text
    assert "health_broadcasting_facility_count,10" in text


def test_admin_dashboard_renders_health_facility_counts(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "demo-health-facilities" in js.text
    assert "present_facility_count" in js.text
    assert "broadcasting_facility_count" in js.text
    css = client.get("/admin/styles.css")
    assert ".demo-health-facilities" in css.text


def test_deploy_checklist_mentions_health_badge_facility_counts(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("health badge" in step.lower() and "present vs broadcasting" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_health_badge_facility_counts(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("health badge" in step.lower() and "present vs broadcasting" in step.lower() for step in steps)
