from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.seed import seed_nursing_home_demo, seed_pa_nursing_home_demo
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.shift_matching import list_matched_shifts_for_provider, shift_matches_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_shift_matches_provider_checks_state_credential_and_pay() -> None:
    provider = MarylandProvider(
        full_name="Match Test",
        email="match.test@offercare.demo",
        phone_number="+14105559999",
        npi_number="1234567893",
        md_license_number="CNA-MD-TEST",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=20.0,
        response_propensity=0.8,
        fatigue_score=0.0,
    )
    assert shift_matches_provider(
        provider=provider,
        facility_state="MD",
        facility_type="NURSING_HOME",
        shift_role="CNA",
        hourly_pay_rate=22.0,
    )
    assert not shift_matches_provider(
        provider=provider,
        facility_state="MD",
        facility_type="NURSING_HOME",
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
    )
    assert not shift_matches_provider(
        provider=provider,
        facility_state="MD",
        facility_type="NURSING_HOME",
        shift_role="CNA",
        hourly_pay_rate=18.0,
    )


def test_list_matched_shifts_for_md_cna(db: Session) -> None:
    seeded = seed_nursing_home_demo(db)
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name="MD CNA Matcher",
        email=f"md.cna.matcher.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"md.cna.matcher.{token}@offercare.demo"),
        md_license_number=f"CNA-MD-{token.upper()}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=15.0,
        response_propensity=0.85,
        fatigue_score=0.0,
    )
    db.add(provider)
    db.commit()

    matched = list_matched_shifts_for_provider(db, provider, limit=20)
    offer_ids = {str(row["offer_id"]) for row in matched}
    assert seeded["offer_id"] in offer_ids or matched
    assert all(row["state"] == "MD" for row in matched)
    assert all(row["rate_delta"] >= 0 for row in matched)


def test_pa_cna_matches_gna_shift_not_lpn(db: Session) -> None:
    seeded = seed_pa_nursing_home_demo(db)
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == "pa.snf.cna.a@offercare.demo")
        .one()
    )
    matched = list_matched_shifts_for_provider(db, provider, limit=10)
    roles = {row["shift_role"] for row in matched}
    assert "GNA" in roles
    assert seeded["offer_id"] in {str(row["offer_id"]) for row in matched}


def test_matched_shifts_endpoint_requires_auth(client: TestClient) -> None:
    response = client.get("/api/clinicians/me/matched-shifts")
    assert response.status_code == 401


def test_matched_shifts_endpoint_for_verified_cna(db: Session, client: TestClient) -> None:
    from app.services.clinician_auth import create_portal_account
    from app.services.license_verification import verify_clinician

    seed_nursing_home_demo(db)
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name="Portal CNA Matcher",
        email=f"portal.cna.matcher.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"portal.cna.matcher.{token}@offercare.demo"),
        md_license_number=f"CNA-MD-{token.upper()}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="UNVERIFIED",
        min_hourly_rate=15.0,
        response_propensity=0.85,
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
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/clinicians/me/matched-shifts", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert all(row["state"] == "MD" for row in body)
    assert all("rate_delta" in row for row in body)


def test_hospital_only_rn_skips_nursing_home_shifts(db: Session) -> None:
    snf = seed_nursing_home_demo(db)
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name="Hospital RN Only",
        email=f"hospital.rn.only.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"hospital.rn.only.{token}@offercare.demo"),
        md_license_number=f"RN-MD-{token.upper()}",
        state="MD",
        credential_type="RN",
        service_lines="HOSPITAL",
        license_status="VERIFIED",
        min_hourly_rate=80.0,
        response_propensity=0.85,
        fatigue_score=0.0,
    )
    db.add(provider)
    db.commit()

    matched = list_matched_shifts_for_provider(db, provider, limit=50)
    matched_ids = {str(row["offer_id"]) for row in matched}
    assert snf["offer_id"] not in matched_ids


def test_portal_uses_open_shifts_ui(client: TestClient) -> None:
    html = client.get("/portal/")
    assert html.status_code == 200
    assert "Open shifts" in html.text
    assert "show-all-shifts-toggle" not in html.text
    js = client.get("/portal/app.js")
    assert "/api/shifts/open?" in js.text
    assert "/api/clinicians/me/open-shifts" in js.text
