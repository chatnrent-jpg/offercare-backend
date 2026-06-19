from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility, MarylandProvider
from app.schemas import ClinicianApplyRequest
from app.seed import seed_home_health_demo, seed_nursing_home_demo
from app.services.care_taxonomy import (
    clinician_qualifies_for_shift_role,
    map_scraped_facility_type,
    normalize_credential_type,
    shift_templates_for_facility_type,
)
from app.services.license_verification import apply_as_clinician, is_valid_npi, run_license_auto_check
from app.services.shift_offer_generator import auto_create_shifts_for_facility, list_open_shifts
from app.services.shift_ranking import rank_offer_from_db


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_care_taxonomy_endpoint(client: TestClient) -> None:
    response = client.get("/api/care/taxonomy")
    assert response.status_code == 200
    body = response.json()
    role_codes = {row["code"] for row in body["shift_roles"]}
    facility_codes = {row["code"] for row in body["facility_types"]}
    credential_codes = {row["code"] for row in body["credential_types"]}
    assert "LPN" in role_codes
    assert "CNA" in role_codes
    assert "GNA" in role_codes
    assert "NURSING_ASSISTANT" in role_codes
    assert "NURSING_HOME" in facility_codes
    assert "HOME_HEALTH" in facility_codes
    assert "LPN" in credential_codes
    assert "CNA" in credential_codes
    assert "GNA" in credential_codes


def test_role_credential_matching_rules() -> None:
    assert clinician_qualifies_for_shift_role("RN", "ICU_RN")
    assert clinician_qualifies_for_shift_role("LPN", "LPN")
    assert clinician_qualifies_for_shift_role("CNA", "CNA")
    assert clinician_qualifies_for_shift_role("GNA", "GNA")
    assert clinician_qualifies_for_shift_role("CNA", "NURSING_ASSISTANT")
    assert not clinician_qualifies_for_shift_role("CNA", "ICU_RN")
    assert not clinician_qualifies_for_shift_role("LPN", "ICU_RN")


def test_service_line_matching_rules() -> None:
    from app.services.care_taxonomy import provider_supports_facility_type

    assert provider_supports_facility_type("HOSPITAL", "HOSPITAL")
    assert provider_supports_facility_type("HOME_HEALTH", "HOSPITAL") is False
    assert provider_supports_facility_type("ALL", "NURSING_HOME")


def test_nursing_home_shift_templates() -> None:
    templates = shift_templates_for_facility_type("NURSING_HOME")
    roles = {role for role, _rate in templates}
    assert {"LPN", "CNA", "GNA", "NURSING_ASSISTANT"}.issubset(roles)


def test_home_health_shift_templates() -> None:
    templates = shift_templates_for_facility_type("HOME_HEALTH")
    roles = {role for role, _rate in templates}
    assert {"HOME_HEALTH_RN", "LPN", "CNA"}.issubset(roles)


def test_map_scraped_facility_type_for_post_acute_settings() -> None:
    assert map_scraped_facility_type("Skilled Nursing Facility") == "NURSING_HOME"
    assert map_scraped_facility_type("Home Health Agency") == "HOME_HEALTH"


def test_nursing_home_seed_creates_post_acute_demo(db: Session) -> None:
    seeded = seed_nursing_home_demo(db)
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id == UUID(seeded["facility_id"]))
        .one()
    )
    assert facility.facility_type == "NURSING_HOME"
    rows = list_open_shifts(db, facility_type="NURSING_HOME", shift_role="LPN")
    assert any(str(row["offer_id"]) == seeded["offer_id"] for row in rows)
    assert rows[0]["facility_type_label"] == "Nursing home / SNF"
    assert rows[0]["shift_role_label"] == "LPN"


def test_home_health_seed_creates_visit_based_demo(db: Session) -> None:
    seeded = seed_home_health_demo(db)
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id == UUID(seeded["facility_id"]))
        .one()
    )
    assert facility.facility_type == "HOME_HEALTH"
    ranking = rank_offer_from_db(db, UUID(seeded["offer_id"]))
    ranked_credentials = {
        db.query(MarylandProvider)
        .filter(MarylandProvider.provider_id == row.provider_id)
        .one()
        .credential_type
        for row in ranking.ranked
    }
    assert ranked_credentials
    assert all(cred == "RN" for cred in ranked_credentials)


def test_auto_create_for_nursing_home_facility(db: Session) -> None:
    facility = MarylandFacility(
        name="Test SNF Auto Create",
        facility_type="NURSING_HOME",
        county="Anne Arundel County",
        state="MD",
    )
    db.add(facility)
    db.commit()
    result = auto_create_shifts_for_facility(db, facility)
    assert result.created_offers
    roles = {row["shift_role"] for row in list_open_shifts(db, limit=200) if row["facility_id"] == facility.facility_id}
    assert "CNA" in roles
    assert "LPN" in roles


def test_cna_apply_without_npi(db: Session) -> None:
    token = __import__("uuid").uuid4().hex[:6]
    payload = ClinicianApplyRequest(
        full_name="CNA Applicant",
        email=f"cna.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        md_license_number=f"CNA-MD-{token.upper()}",
        state="MD",
        credential_type="CNA",
        min_hourly_rate=18.0,
        password="SecretPass1",
    )
    provider, auto_check = apply_as_clinician(db, payload)
    assert auto_check.result == "STUB_PASS"
    assert normalize_credential_type(provider.credential_type) == "CNA"
    assert is_valid_npi(provider.npi_number)


def test_cna_auto_check_skips_npi_requirement() -> None:
    result = run_license_auto_check(
        npi_number=None,
        md_license_number="CNA-MD-9992",
        state="MD",
        credential_type="CNA",
    )
    assert result.result == "STUB_PASS"


def test_nursing_home_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/nursing-home")
    assert response.status_code == 200
    assert response.json()["facility_type"] == "NURSING_HOME"


def test_home_health_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/home-health")
    assert response.status_code == 200
    assert response.json()["facility_type"] == "HOME_HEALTH"


def test_admin_dashboard_includes_post_acute_seed_buttons(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "seed-nursing-home-btn" in html.text
    assert "seed-home-health-btn" in html.text
    portal = client.get("/portal")
    assert portal.status_code == 200
    assert "apply-credential" in portal.text
