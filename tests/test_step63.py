from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import build_demo_environment_status, run_full_demo_setup


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_admin_dashboard_includes_per_row_lock_test(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "demo-lock-smoke-offer-btn" in text
    assert "Lock test" in text
    assert "wireDemoLockSmokeButtons" in text
    assert "runDemoLockSmoke" in text


def test_demo_lock_smoke_endpoint_locks_specific_offer(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    response = client.post(f"/api/seed/demo-lock-smoke?offer_id={nj_offer['offer_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["facility_name"] == "Paramus SNF at Bergen"
    assert body["clinician_email"] == nj_offer["demo_clinician_email"]


def test_demo_status_offers_include_fields_for_lock_test_buttons(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    offers = build_demo_environment_status(db)["offers"]
    broadcasting = [row for row in offers if row.get("compliance_lock_status") == "BROADCASTING" and row.get("offer_id")]
    assert len(broadcasting) == 10
    assert all(row.get("loaded") for row in broadcasting)
    assert all(row.get("demo_clinician_email") for row in broadcasting)


def test_deploy_checklist_mentions_per_row_lock_test(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("lock test" in step.lower() and "row" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_per_row_lock_test(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("lock test" in step.lower() for step in steps)
