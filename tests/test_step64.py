from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicianPushSubscription, MarylandProvider
from app.seed import seed_all_mid_atlantic_demos
from app.services.demo_environment import build_demo_environment_status, build_demo_health, run_full_demo_setup


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_demo_health_green_after_full_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    health = build_demo_environment_status(db)["health"]
    assert health["status"] == "green"
    assert health["label"] == "READY"
    assert health["issues"] == []


def test_demo_health_red_when_no_demo_loaded() -> None:
    health = build_demo_health(
        loaded=False,
        facility_count=0,
        expected_facility_count=10,
        portal_ready=False,
        push_subscriptions_ready=False,
        offers=[],
    )
    assert health["status"] == "red"
    assert health["label"] == "NOT READY"
    assert "No demo facilities loaded" in health["issues"][0]


def test_demo_health_yellow_when_push_subscriptions_missing(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    clinicians = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email.like("%@offercare.demo"))
        .all()
    )
    provider_ids = [provider.provider_id for provider in clinicians]
    if provider_ids:
        db.query(ClinicianPushSubscription).filter(
            ClinicianPushSubscription.provider_id.in_(provider_ids)
        ).delete(synchronize_session=False)
        db.commit()
    health = build_demo_environment_status(db)["health"]
    assert health["status"] == "yellow"
    assert health["label"] == "PARTIAL"
    assert any("push subscriptions" in issue.lower() for issue in health["issues"])


def test_demo_health_yellow_reports_locked_shift() -> None:
    health = build_demo_health(
        loaded=False,
        facility_count=9,
        expected_facility_count=10,
        portal_ready=True,
        push_subscriptions_ready=True,
        offers=[
            {
                "facility_name": "Paramus SNF at Bergen",
                "offer_id": "00000000-0000-0000-0000-000000000001",
                "loaded": False,
                "compliance_lock_status": "LOCKED",
                "matched_clinician_count": 0,
            },
            *[
                {
                    "facility_name": f"Demo Facility {index}",
                    "offer_id": f"00000000-0000-0000-0000-0000000000{index:02d}",
                    "loaded": True,
                    "compliance_lock_status": "BROADCASTING",
                    "matched_clinician_count": 1,
                }
                for index in range(2, 11)
            ],
        ],
    )
    assert health["status"] == "yellow"
    assert any("locked" in issue.lower() for issue in health["issues"])


def test_demo_status_endpoint_includes_health(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    body = response.json()
    assert body["health"]["status"] == "green"
    assert body["health"]["label"] == "READY"


def test_admin_dashboard_includes_demo_health_badge(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "demo-health-badge" in html.text
    js = client.get("/admin/app.js")
    assert "renderDemoHealth" in js.text
    css = client.get("/admin/styles.css")
    assert ".demo-health-badge.green" in css.text
    assert ".demo-health-badge.yellow" in css.text
    assert ".demo-health-badge.red" in css.text


def test_deploy_checklist_mentions_demo_health_badge(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("health badge" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_health_badge(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("health badge" in step.lower() for step in steps)
