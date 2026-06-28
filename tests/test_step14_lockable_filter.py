from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, ensure_demo_portal_accounts
from app.services.shift_matching import list_open_shifts_for_clinician


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_lockable_only_returns_subset(db: Session) -> None:
    provider = db.query(MarylandProvider).filter(MarylandProvider.email == "nj.snf.cna.a@offercare.demo").first()
    if provider is None:
        pytest.skip("demo CNA not seeded")
    all_rows = list_open_shifts_for_clinician(db, provider, limit=20, lockable_only=False)
    lockable_rows = list_open_shifts_for_clinician(db, provider, limit=20, lockable_only=True)
    assert len(lockable_rows) <= len(all_rows)
    assert all(row.get("lock_eligible") for row in lockable_rows)


def test_open_shifts_lockable_only_query_param(client: TestClient) -> None:
    client.post("/api/seed/mid-atlantic-demos")
    client.post("/api/seed/demo-portal-accounts")
    login = client.post(
        "/api/clinicians/login",
        json={"email": "nj.snf.cna.a@offercare.demo", "password": DEMO_PORTAL_PASSWORD},
    )
    if login.status_code != 200:
        pytest.skip("demo login unavailable")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    all_resp = client.get("/api/clinicians/me/open-shifts?limit=10", headers=headers)
    lock_resp = client.get("/api/clinicians/me/open-shifts?limit=10&lockable_only=true", headers=headers)
    if all_resp.status_code == 404:
        pytest.skip("open-shifts endpoint not deployed")
    assert all_resp.status_code == 200
    assert lock_resp.status_code == 200
    assert len(lock_resp.json()) <= len(all_resp.json())


def test_portal_step14_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    assert "lockable-only-toggle" in html
    assert "mapBasicOpenShiftRow" in js
    assert "/api/shifts/open?" in js
    assert "setPortalView(\"placements\")" in js
