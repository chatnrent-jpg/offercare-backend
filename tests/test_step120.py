from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import DEMO_ADMIN_ACTION_DEMO_GATES, DEMO_GATE_DEFINITIONS
from app.services.shift_lock import lock_shift_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def assert_embedded_demo_gates_catalog(demo_gates: dict) -> None:
    assert demo_gates is not None
    assert demo_gates["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert demo_gates["demo_admin_action_count"] == len(DEMO_ADMIN_ACTION_DEMO_GATES)
    assert len(demo_gates["demo_admin_actions"]) == 8
    assert demo_gates["demo_admin_actions"][0]["field"] == "status.demo_gates"
    assert any(row["field"] == "demo_status.demo_gates" for row in demo_gates["demo_admin_actions"])


def test_demo_setup_embedded_demo_gates_include_admin_action_count_and_catalog(client: TestClient) -> None:
    body = client.post("/api/seed/demo-setup?notify_matched=false").json()
    assert_embedded_demo_gates_catalog(body["status"]["demo_gates"])


def test_demo_reset_embedded_demo_gates_include_admin_action_count_and_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.post("/api/seed/demo-reset").json()
    assert_embedded_demo_gates_catalog(body["status"]["demo_gates"])


def test_demo_reset_offer_embedded_demo_gates_include_admin_action_count_and_catalog(
    client: TestClient, db: Session
) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))
    body = client.post(f"/api/seed/demo-reset-offer?offer_id={nj_offer['offer_id']}").json()
    assert_embedded_demo_gates_catalog(body["status"]["demo_gates"])


def test_demo_lock_smoke_embedded_demo_gates_include_admin_action_count_and_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.post("/api/seed/demo-lock-smoke").json()
    assert_embedded_demo_gates_catalog(body["demo_status"]["demo_gates"])


def test_notify_matched_demos_embedded_demo_gates_include_admin_action_count_and_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.post("/api/seed/notify-matched-demos").json()
    assert_embedded_demo_gates_catalog(body["demo_status"]["demo_gates"])


def test_demo_notify_matched_offer_embedded_demo_gates_include_admin_action_count_and_catalog(
    client: TestClient,
) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    offer_id = next(row["offer_id"] for row in status["offers"] if row.get("loaded"))
    body = client.post(f"/api/seed/demo-notify-matched?offer_id={offer_id}").json()
    assert_embedded_demo_gates_catalog(body["demo_status"]["demo_gates"])


def test_demo_portal_accounts_embedded_demo_gates_include_admin_action_count_and_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.post("/api/seed/demo-portal-accounts").json()
    assert_embedded_demo_gates_catalog(body["demo_status"]["demo_gates"])


def test_demo_push_subscriptions_embedded_demo_gates_include_admin_action_count_and_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.post("/api/seed/demo-push-subscriptions").json()
    assert_embedded_demo_gates_catalog(body["demo_status"]["demo_gates"])


def test_demo_walkthrough_documents_embedded_demo_gates_admin_action_snapshot(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    markdown = client.get("/api/seed/demo-walkthrough.md").text
    assert "demo_admin_action_count" in markdown
    assert "demo_admin_actions catalog on every mutating response" in markdown


def test_deploy_checklist_demo_steps_mention_embedded_demo_gates_admin_action_snapshot(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "embedded demo_gates with demo_admin_action_count and the demo_admin_actions catalog" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_embedded_demo_gates_admin_action_snapshot(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "embedded demo_gates with demo_admin_action_count and the demo_admin_actions catalog" in step.lower()
        for step in steps
    )
