from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.clinician_auth import create_portal_account
from app.services.shift_matching import explain_open_shift_lock


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_explain_open_shift_lock_pay_below_minimum(db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name=f"Preview {token}",
        email=f"preview.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"preview.{token}@offercare.demo"),
        md_license_number=f"CNA-MD-PREV{token.upper()}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=50.0,
        response_propensity=0.8,
        fatigue_score=0.0,
    )
    db.add(provider)
    db.flush()

    start = datetime.now(timezone.utc) + timedelta(days=2)
    explained = explain_open_shift_lock(
        db,
        provider,
        {
            "offer_id": uuid.uuid4(),
            "state": "MD",
            "facility_type": "NURSING_HOME",
            "shift_role": "CNA",
            "hourly_pay_rate": 30.0,
            "compliance_lock_status": "BROADCASTING",
            "shift_starts_at": start,
            "shift_ends_at": start + timedelta(hours=8),
        },
    )
    assert explained["lock_eligible"] is False
    assert "below your" in (explained["lock_preview"] or "").lower()


def test_open_shifts_include_lock_preview(client: TestClient, db: Session) -> None:
    provider = db.query(MarylandProvider).filter(MarylandProvider.email == "nj.snf.cna.a@offercare.demo").first()
    if provider is None:
        pytest.skip("demo CNA not seeded")
    create_portal_account(db, provider.provider_id, "SecretPass1")
    db.commit()
    login = client.post(
        "/api/clinicians/login",
        json={"email": provider.email, "password": "SecretPass1"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/clinicians/me/open-shifts?limit=5", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    if not rows:
        pytest.skip("no open shifts in db")
    assert "lock_preview" in rows[0]


def test_portal_step13_assets(client: TestClient) -> None:
    js = client.get("/portal/app.js").text
    assert "renderLockCell" in js
    assert "lock_preview" in js
    assert "vault_review_recommended" in js
    assert "lock-vault-btn" in js


def test_demo_status_includes_portal_lockable_count(db: Session) -> None:
    from app.services.demo_environment import build_demo_environment_status

    status = build_demo_environment_status(db)
    assert "portal_lockable_shift_count" in status
    assert isinstance(status["portal_lockable_shift_count"], int)
