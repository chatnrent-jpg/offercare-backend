from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
    build_demo_environment_status,
    build_demo_health,
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


def test_demo_health_locked_row_not_counted_as_unloaded() -> None:
    health = build_demo_health(
        loaded=False,
        facility_count=10,
        expected_facility_count=10,
        portal_ready=True,
        push_subscriptions_ready=True,
        offers=[
            {
                "facility_name": "Paramus SNF at Bergen",
                "offer_id": "00000000-0000-0000-0000-000000000001",
                "loaded": False,
                "resettable": True,
                "compliance_lock_status": "LOCKED",
                "matched_clinician_count": 1,
            },
            *[
                {
                    "facility_name": f"Demo Facility {index}",
                    "offer_id": f"00000000-0000-0000-0000-0000000000{index:02d}",
                    "loaded": True,
                    "resettable": False,
                    "compliance_lock_status": "BROADCASTING",
                    "matched_clinician_count": 1,
                }
                for index in range(2, 11)
            ],
        ],
    )
    assert health["status"] == "yellow"
    assert any("locked" in issue.lower() for issue in health["issues"])
    assert not any("missing" in issue.lower() for issue in health["issues"])
    assert not any("present" in issue.lower() and "10/10" not in issue for issue in health["issues"])


def test_present_facility_count_includes_locked_rows(db: Session) -> None:
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
    assert status["facility_count"] == 9
    assert status["present_facility_count"] == 10
    assert status["health"]["status"] == "yellow"
    assert any("locked" in issue.lower() for issue in status["health"]["issues"])
    assert not any("missing" in issue.lower() for issue in status["health"]["issues"])


def test_lock_smoke_returns_resettable_offer_row(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    payload = run_demo_lock_smoke_test(db, offer_id=UUID(nj_offer["offer_id"]))
    assert payload["ok"] is True
    assert payload["offer_row"] is not None
    assert payload["offer_row"]["facility_name"] == "Paramus SNF at Bergen"
    assert payload["offer_row"]["loaded"] is False
    assert payload["offer_row"]["resettable"] is True
    assert payload["offer_row"]["compliance_lock_status"] == "LOCKED"


def test_demo_status_endpoint_includes_present_facility_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    body = response.json()
    assert body["present_facility_count"] == 10
    assert body["facility_count"] == 10


def test_demo_status_csv_includes_resettable_and_present_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status.csv")
    assert response.status_code == 200
    text = response.text.replace(" ", "")
    assert "present_facility_count,10" in text
    assert "resettable" in text


def test_admin_dashboard_mentions_present_facility_count(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "present_facility_count" in js.text
    assert "Broadcasting" in js.text


def test_deploy_checklist_mentions_locked_rows_present_in_health(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("locked rows as present" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_locked_rows_present_in_health(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("locked rows as present" in step.lower() for step in steps)
