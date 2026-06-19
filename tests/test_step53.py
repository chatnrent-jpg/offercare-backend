from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import verify_password
from app.database import SessionLocal
from app.models import ClinicianPortalAccount, MarylandProvider
from app.seed import seed_all_mid_atlantic_demos
from app.services.demo_environment import build_demo_environment_status
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, ensure_demo_portal_accounts


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_ensure_demo_portal_accounts_creates_logins(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    payload = ensure_demo_portal_accounts(db)
    assert payload["clinician_count"] >= 10
    assert payload["password_hint"] == DEMO_PORTAL_PASSWORD

    provider = db.query(MarylandProvider).filter(MarylandProvider.email == "nj.snf.cna.a@offercare.demo").first()
    account = (
        db.query(ClinicianPortalAccount)
        .filter(ClinicianPortalAccount.provider_id == provider.provider_id)
        .first()
    )
    assert account is not None
    assert verify_password(DEMO_PORTAL_PASSWORD, account.password_hash)


def test_ensure_demo_portal_accounts_is_idempotent_and_resets_password(db: Session) -> None:
    seed_all_mid_atlantic_demos(db)
    first = ensure_demo_portal_accounts(db)
    second = ensure_demo_portal_accounts(db)
    assert second["created"] == 0
    assert second["updated"] == first["clinician_count"]


def test_mid_atlantic_seed_ensures_portal_accounts(db: Session) -> None:
    payload = seed_all_mid_atlantic_demos(db)
    assert payload["portal_accounts"]["clinician_count"] >= 10
    status = build_demo_environment_status(db)
    assert status["portal_ready"] is True
    assert status["portal_account_count"] >= 10


def test_demo_portal_accounts_endpoint(client: TestClient) -> None:
    client.post("/api/seed/mid-atlantic-demos")
    response = client.post("/api/seed/demo-portal-accounts")
    assert response.status_code == 200
    body = response.json()
    assert body["clinician_count"] >= 10
    assert body["password_hint"] == DEMO_PORTAL_PASSWORD


def test_demo_clinician_can_login_after_portal_accounts(client: TestClient) -> None:
    client.post("/api/seed/mid-atlantic-demos")
    response = client.post(
        "/api/clinicians/login",
        json={"email": "nj.snf.cna.a@offercare.demo", "password": DEMO_PORTAL_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"]["email"] == "nj.snf.cna.a@offercare.demo"
    assert body["access_token"]


def test_demo_status_shows_portal_account_counts(client: TestClient) -> None:
    client.post("/api/seed/mid-atlantic-demos")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    body = response.json()
    assert body["portal_account_count"] >= 10
    assert body["portal_ready"] is True
    assert body["demo_portal_password_hint"] == DEMO_PORTAL_PASSWORD
    assert all(row["portal_enabled"] for row in body["clinicians"])


def test_admin_dashboard_includes_ensure_demo_portal_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "ensure-demo-portal-btn" in html.text
    assert "Ensure demo portal logins" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-portal-accounts" in js.text


def test_deploy_checklist_mentions_demo_portal_login(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("SecretPass1" in step for step in steps)
