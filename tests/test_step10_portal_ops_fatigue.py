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
from app.services.clinician_schedule import ops_create_schedule_block, ops_delete_schedule_block


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_provider(db: Session) -> MarylandProvider:
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name=f"Ops Vault {token}",
        email=f"ops.vault.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"ops.vault.{token}@offercare.demo"),
        md_license_number=f"CNA-MD-OPS{token.upper()}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=20.0,
        response_propensity=0.8,
        fatigue_score=0.0,
    )
    db.add(provider)
    db.flush()
    create_portal_account(db, provider.provider_id, "SecretPass1")
    db.commit()
    return provider


def test_portal_step10_structure_and_build(client: TestClient) -> None:
    html = client.get("/portal/")
    assert html.status_code == 200
    text = html.text
    assert 'data-portal-build="portal-step10-2026"' in text
    assert 'id="portal-section-nav"' in text
    assert 'data-view="overview"' in text
    assert 'data-view="shifts"' in text
    assert 'data-view="schedule"' in text
    assert 'data-view="placements"' in text
    assert 'id="fatigue-banner"' in text
    assert "portal-step10-2026" in text

    js = client.get("/portal/app.js")
    assert js.status_code == 200
    js_text = js.text
    assert "renderFatigueBanner" in js_text
    assert "setPortalView" in js_text
    assert "FATIGUE_SOFT_THRESHOLD" in js_text

    css = client.get("/portal/styles.css")
    assert css.status_code == 200
    assert "fatigue-banner" in css.text


def test_portal_login_and_dashboard_data(client: TestClient, db: Session) -> None:
    provider = _make_provider(db)
    login = client.post(
        "/api/clinicians/login",
        json={"email": provider.email, "password": "SecretPass1"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    app_status = client.get("/api/clinicians/me/application", headers=headers)
    assert app_status.status_code == 200
    body = app_status.json()
    assert body["provider"]["full_name"] == provider.full_name
    assert "fatigue_score" in body["provider"]

    schedule = client.get("/api/clinicians/me/schedule", headers=headers)
    assert schedule.status_code == 200

    matched = client.get("/api/clinicians/me/matched-shifts", headers=headers)
    assert matched.status_code == 200

    placements = client.get("/api/clinicians/me/placements", headers=headers)
    assert placements.status_code == 200


def test_portal_main_serves_step10_build_header(client: TestClient) -> None:
    response = client.get("/portal/")
    assert response.headers.get("X-Portal-Build") == "portal-step10-2026"


def test_ops_console_includes_vault_write_controls() -> None:
    from pathlib import Path

    text = Path("ui_dashboard/ops_console.py").read_text(encoding="utf-8")
    assert "_ops_create_calendar_block_safe" in text
    assert "_ops_delete_calendar_block_safe" in text
    assert "ops_vault_add_block" in text
    assert "ops_vault_delete_block" in text


def test_ops_vault_write_and_delete_block(db: Session) -> None:
    provider = _make_provider(db)
    start = datetime.now(timezone.utc) + timedelta(days=5)
    end = start + timedelta(hours=6)
    created = ops_create_schedule_block(
        db,
        provider_token=provider.md_license_number,
        event_type="BLACKOUT_UNAVAILABLE",
        start_time=start,
        end_time=end,
    )
    event_id = created["event_id"]
    assert created["event_type"] == "BLACKOUT_UNAVAILABLE"

    deleted = ops_delete_schedule_block(
        db,
        provider_token=provider.md_license_number,
        event_id=event_id,
    )
    assert deleted == event_id


def test_elevated_fatigue_provider_still_logs_in(client: TestClient, db: Session) -> None:
    provider = _make_provider(db)
    provider.fatigue_score = 3.25
    db.commit()

    login = client.post(
        "/api/clinicians/login",
        json={"email": provider.email, "password": "SecretPass1"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    app_status = client.get("/api/clinicians/me/application", headers=headers)
    assert float(app_status.json()["provider"]["fatigue_score"]) == 3.25
