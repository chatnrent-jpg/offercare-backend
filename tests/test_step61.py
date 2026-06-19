from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_environment import (
    build_demo_environment_status,
    check_demo_hint_for_clinician,
    run_full_demo_setup,
)
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _provider(db: Session, email: str) -> MarylandProvider:
    provider = db.query(MarylandProvider).filter(MarylandProvider.email == email).first()
    assert provider is not None
    return provider


def test_check_demo_hint_for_clinician_matches_expected_user(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    nj_offer = next(
        row for row in build_demo_environment_status(db)["offers"] if row["facility_name"] == "Paramus SNF at Bergen"
    )
    provider = _provider(db, nj_offer["demo_clinician_email"])
    payload = check_demo_hint_for_clinician(db, UUID(nj_offer["offer_id"]), provider)
    assert payload is not None
    assert payload["matches"] is True
    assert payload["expected_clinician_email"] == nj_offer["demo_clinician_email"]
    assert payload["signed_in_email"] == nj_offer["demo_clinician_email"]


def test_check_demo_hint_for_clinician_flags_wrong_user(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    saint_jude = next(row for row in status["offers"] if row["facility_name"] == "Saint Jude's ICU")
    wrong_provider = _provider(db, saint_jude["demo_clinician_email"])
    payload = check_demo_hint_for_clinician(db, UUID(nj_offer["offer_id"]), wrong_provider)
    assert payload is not None
    assert payload["matches"] is False
    assert payload["expected_clinician_email"] == nj_offer["demo_clinician_email"]
    assert payload["signed_in_email"] == saint_jude["demo_clinician_email"]
    assert "Sign out and sign in" in payload["message"]


def test_portal_demo_hint_check_endpoint_matches(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    login = client.post(
        "/api/clinicians/login",
        json={"email": nj_offer["demo_clinician_email"], "password": DEMO_PORTAL_PASSWORD},
    )
    token = login.json()["access_token"]
    response = client.get(
        f"/api/portal/demo-hint/check?offer_id={nj_offer['offer_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matches"] is True
    assert body["expected_clinician_email"] == nj_offer["demo_clinician_email"]


def test_portal_demo_hint_check_endpoint_flags_wrong_clinician(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    saint_jude = next(row for row in status["offers"] if row["facility_name"] == "Saint Jude's ICU")
    login = client.post(
        "/api/clinicians/login",
        json={"email": saint_jude["demo_clinician_email"], "password": DEMO_PORTAL_PASSWORD},
    )
    token = login.json()["access_token"]
    response = client.get(
        f"/api/portal/demo-hint/check?offer_id={nj_offer['offer_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matches"] is False
    assert body["expected_clinician_email"] == nj_offer["demo_clinician_email"]
    assert body["signed_in_email"] == saint_jude["demo_clinician_email"]


def test_portal_demo_hint_check_requires_auth(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    response = client.get(f"/api/portal/demo-hint/check?offer_id={nj_offer['offer_id']}")
    assert response.status_code == 401


def test_portal_page_includes_wrong_clinician_banner(client: TestClient) -> None:
    html = client.get("/portal/")
    assert html.status_code == 200
    assert "demo-hint-mismatch-banner" in html.text
    js = client.get("/portal/app.js")
    assert "/api/portal/demo-hint/check" in js.text
    assert "refreshDemoHintMismatch" in js.text
    assert "Wrong demo clinician" in js.text


def test_deploy_checklist_mentions_wrong_demo_clinician_warning(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("wrong demo clinician" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_wrong_clinician_warning(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("wrong demo clinician" in step.lower() for step in steps)
