from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility, MarylandProvider, OfferCareJobOffer
from app.schemas import ClinicianApplyRequest
from app.seed import seed_dc_nursing_home_demo, seed_nursing_home_demo
from app.services.care_taxonomy import (
    GNA_LICENSE_STATES,
    clinician_qualifies_for_shift_role,
    credential_valid_in_state,
    shift_role_credentials_for_state,
    synthetic_npi_for_caregiver,
)
from app.services.shift_ranking import rank_offer_from_db
from app.services.shift_schedule import apply_default_shift_schedule


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_gna_license_states() -> None:
    assert GNA_LICENSE_STATES == frozenset({"MD", "DC"})


def test_pa_gna_shift_accepts_cna_not_gna_credential() -> None:
    assert shift_role_credentials_for_state("GNA", "PA") == ("CNA", "NA")
    assert clinician_qualifies_for_shift_role("CNA", "GNA", facility_state="PA")
    assert not clinician_qualifies_for_shift_role("GNA", "GNA", facility_state="PA")


def test_md_gna_shift_accepts_gna_and_cna() -> None:
    assert shift_role_credentials_for_state("GNA", "MD") == ("GNA", "CNA")
    assert clinician_qualifies_for_shift_role("GNA", "GNA", facility_state="MD")
    assert clinician_qualifies_for_shift_role("CNA", "GNA", facility_state="MD")


def test_credential_valid_in_state_for_gna() -> None:
    assert credential_valid_in_state("GNA", "MD")
    assert credential_valid_in_state("GNA", "DC")
    assert not credential_valid_in_state("GNA", "PA")
    assert credential_valid_in_state("CNA", "PA")


def test_gna_apply_rejected_for_pennsylvania() -> None:
    token = uuid.uuid4().hex[:6]
    with pytest.raises(ValidationError):
        ClinicianApplyRequest(
            full_name="PA GNA Applicant",
            email=f"pa.gna.{token}@offercare.demo",
            phone_number=f"+1215{int(token, 16) % 10_000_000:07d}",
            md_license_number=f"GNA-PA-{token.upper()}",
            state="PA",
            credential_type="GNA",
            min_hourly_rate=18.0,
            password="SecretPass1",
        )


def test_pa_gna_shift_ranks_local_cna(db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    facility = MarylandFacility(
        name=f"PA SNF {token}",
        facility_type="NURSING_HOME",
        county="Philadelphia County",
        state="PA",
    )
    db.add(facility)
    db.flush()
    offer = OfferCareJobOffer(
        facility_id=facility.facility_id,
        shift_role="GNA",
        hourly_pay_rate=24.0,
        compliance_lock_status="BROADCASTING",
    )
    apply_default_shift_schedule(offer)
    db.add(offer)
    cna = MarylandProvider(
        full_name="PA CNA Rank Test",
        email=f"pa.cna.rank.{token}@offercare.demo",
        phone_number=f"+1215{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"pa.cna.rank.{token}@offercare.demo"),
        md_license_number=f"CNA-PA-{token.upper()}",
        state="PA",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=16.0,
        response_propensity=0.9,
        fatigue_score=0.0,
    )
    db.add(cna)
    db.commit()

    ranking = rank_offer_from_db(db, offer.offer_id)
    assert ranking.ranked
    assert all(row.credential_type == "CNA" for row in ranking.ranked)
    assert any(row.provider_id == cna.provider_id for row in ranking.ranked)


def test_md_gna_shift_ranks_gna_and_cna(db: Session) -> None:
    seeded = seed_nursing_home_demo(db)
    gna_offer = (
        db.query(OfferCareJobOffer)
        .filter(
            OfferCareJobOffer.facility_id == UUID(seeded["facility_id"]),
            OfferCareJobOffer.shift_role == "GNA",
        )
        .first()
    )
    if gna_offer is None:
        gna_offer = OfferCareJobOffer(
            facility_id=UUID(seeded["facility_id"]),
            shift_role="GNA",
            hourly_pay_rate=24.0,
            compliance_lock_status="BROADCASTING",
        )
        apply_default_shift_schedule(gna_offer)
        db.add(gna_offer)
        db.commit()

    ranking = rank_offer_from_db(db, gna_offer.offer_id)
    credentials = {row.credential_type for row in ranking.ranked}
    assert "GNA" in credentials
    assert "CNA" in credentials


def test_dc_nursing_home_seed_creates_gna_demo(db: Session) -> None:
    payload = seed_dc_nursing_home_demo(db)
    assert payload["state"] == "DC"
    assert payload["facility_type"] == "NURSING_HOME"
    ranking = rank_offer_from_db(db, UUID(payload["offer_id"]))
    credentials = {row.credential_type for row in ranking.ranked}
    assert "GNA" in credentials
    assert "CNA" in credentials


def test_dc_nursing_home_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/dc-nursing-home")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "DC"
    assert body["facility_type"] == "NURSING_HOME"


def test_care_taxonomy_includes_state_credential_rules(client: TestClient) -> None:
    response = client.get("/api/care/taxonomy")
    assert response.status_code == 200
    rules = response.json()["state_credential_rules"]
    assert "MD" in rules["gna_license_states"]
    assert "DC" in rules["gna_license_states"]
    assert "PA" in rules["gna_shift_fills_with_cna_in"]


def test_admin_dashboard_includes_dc_nursing_home_seed(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "seed-dc-nursing-home-btn" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/dc-nursing-home" in js.text
