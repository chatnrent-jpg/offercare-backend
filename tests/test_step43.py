from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.seed import seed_nursing_home_demo
from app.services.care_taxonomy import normalize_service_lines
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.clinician_auth import create_portal_account
from app.services.clinician_preferences import update_clinician_preferences
from app.services.license_verification import verify_clinician
from app.services.shift_matching import list_matched_shifts_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_normalize_service_lines_all_wins() -> None:
    assert normalize_service_lines(["HOSPITAL", "ALL", "NURSING_HOME"]) == "ALL"
    assert normalize_service_lines("HOSPITAL,NURSING_HOME") == "HOSPITAL,NURSING_HOME"


def test_normalize_service_lines_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="invalid_service_lines"):
        normalize_service_lines(["HOSPITAL", "INVALID"])


def test_preferences_change_matched_shift_count(db: Session) -> None:
    seed_nursing_home_demo(db)
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == "snf.lpn.a@offercare.demo")
        .first()
    )
    assert provider is not None

    provider.min_hourly_rate = 30.0
    provider.service_lines = "NURSING_HOME"
    db.commit()

    matched = list_matched_shifts_for_provider(db, provider, limit=20)
    assert matched

    update_clinician_preferences(db, provider.provider_id, min_hourly_rate=100.0)
    db.refresh(provider)
    assert not list_matched_shifts_for_provider(db, provider, limit=20)

    update_clinician_preferences(db, provider.provider_id, min_hourly_rate=30.0, service_lines="HOSPITAL")
    db.refresh(provider)
    assert not list_matched_shifts_for_provider(db, provider, limit=20)


def test_preferences_endpoint_requires_auth(client: TestClient) -> None:
    response = client.get("/api/clinicians/me/preferences")
    assert response.status_code == 401


def test_preferences_endpoint_get_and_patch(db: Session, client: TestClient) -> None:
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name="Prefs Tester",
        email=f"prefs.tester.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"prefs.tester.{token}@offercare.demo"),
        md_license_number=f"LPN-MD-{token.upper()}",
        state="MD",
        credential_type="LPN",
        service_lines="NURSING_HOME",
        license_status="UNVERIFIED",
        min_hourly_rate=25.0,
        response_propensity=0.8,
        fatigue_score=0.0,
    )
    db.add(provider)
    db.flush()
    create_portal_account(db, provider.provider_id, "SecretPass1")
    verify_clinician(db, provider.provider_id, action="VERIFY", reviewer="admin")
    login = client.post(
        "/api/clinicians/login",
        json={"email": provider.email, "password": "SecretPass1"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    get_resp = client.get("/api/clinicians/me/preferences", headers=headers)
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["min_hourly_rate"] == 25.0
    assert body["service_lines"] == "NURSING_HOME"
    assert any(row["code"] == "ALL" for row in body["service_line_options"])

    patch_resp = client.patch(
        "/api/clinicians/me/preferences",
        headers=headers,
        json={"min_hourly_rate": 40.0, "service_lines": ["HOSPITAL", "HOME_HEALTH"]},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["min_hourly_rate"] == 40.0
    assert patched["service_lines"] == "HOSPITAL,HOME_HEALTH"


def test_portal_includes_preferences_ui(client: TestClient) -> None:
    html = client.get("/portal/")
    assert html.status_code == 200
    assert "preferences-form" in html.text
    assert "Shift preferences" in html.text
    js = client.get("/portal/app.js")
    assert "/api/clinicians/me/preferences" in js.text
    assert "renderPreferencesForm" in js.text
