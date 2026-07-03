from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Caregiver1099ContractorAccount,
    CaregiverProfile,
    CaregiverW2EmployeeAccount,
    MarylandProvider,
)
from app.services.care_taxonomy import synthetic_npi_for_caregiver


def _unique_phone() -> str:
    return f"+1{uuid4().int % 10**10:010d}"


def _cleanup(db: Session, profile_id) -> None:
    db.query(CaregiverW2EmployeeAccount).filter(
        CaregiverW2EmployeeAccount.caregiver_profile_id == profile_id
    ).delete(synchronize_session=False)
    db.query(Caregiver1099ContractorAccount).filter(
        Caregiver1099ContractorAccount.caregiver_profile_id == profile_id
    ).delete(synchronize_session=False)
    db.query(CaregiverProfile).filter(CaregiverProfile.caregiver_profile_id == profile_id).delete(
        synchronize_session=False
    )
    db.commit()


def test_caregiver_provision_w2_requires_admin(client: TestClient) -> None:
    response = client.post(
        "/api/caregivers/provision",
        json={
            "mbon_license_number": "CNAADMIN001",
            "full_name": "Admin Gate Test",
            "employment_tier": "TIER1_W2",
            "maryland_residence_county": "Howard",
        },
        headers={"X-Admin-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_caregiver_provision_w2_bundle(client: TestClient) -> None:
    token = uuid4().hex[:8].upper()
    license_number = f"CNAAPITEST{token}"
    response = client.post(
        "/api/caregivers/provision",
        json={
            "mbon_license_number": license_number,
            "full_name": "API W2 Caregiver",
            "employment_tier": "TIER1_W2",
            "credential_type": "CNA",
            "maryland_residence_county": "Montgomery",
            "local_tax_jurisdiction_code": "MD31001",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["employment_tier"] == "TIER1_W2"
    assert body["profile"]["mbon_license_number"] == license_number.upper()
    assert body["w2_account"]["maryland_residence_county"] == "Montgomery County"
    assert body["contractor_account"] is None

    profile_id = body["profile"]["caregiver_profile_id"]
    db = SessionLocal()
    try:
        lookup = client.get(f"/api/caregivers/profiles/mbon/{license_number}")
        assert lookup.status_code == 200
        assert lookup.json()["profile"]["caregiver_profile_id"] == profile_id
    finally:
        _cleanup(db, profile_id)
        db.close()


def test_caregiver_provision_1099_and_ein_validation(client: TestClient) -> None:
    token = uuid4().hex[:8].upper()
    license_number = f"CNA1099API{token}"
    response = client.post(
        "/api/caregivers/provision",
        json={
            "mbon_license_number": license_number,
            "full_name": "API 1099 Caregiver",
            "employment_tier": "TIER2_1099",
            "corporate_legal_name": "Care Services LLC",
            "corporate_ein": "12-3456789",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    contractor_id = body["contractor_account"]["contractor_account_id"]
    assert body["contractor_account"]["corporate_ein"] == "123456789"

    validated = client.post(
        f"/api/caregivers/1099-accounts/{contractor_id}/ein-validation",
        json={"status": "VALIDATED", "validation_reference": "IRS-TIN-API-001"},
    )
    assert validated.status_code == 200
    assert validated.json()["corporate_ein_validation_status"] == "VALIDATED"

    profile_id = body["profile"]["caregiver_profile_id"]
    db = SessionLocal()
    try:
        _cleanup(db, profile_id)
    finally:
        db.close()


def test_caregiver_provision_from_provider(client: TestClient) -> None:
    token = uuid4().hex[:8].upper()
    license_number = f"CNAPROVAPI{token}"
    email = f"caregiver.api.{token.lower()}@example.com"
    db = SessionLocal()
    try:
        provider = MarylandProvider(
            full_name=f"Provider {token}",
            email=email,
            phone_number=_unique_phone(),
            npi_number=synthetic_npi_for_caregiver(email),
            md_license_number=license_number,
            state="MD",
            credential_type="CNA",
            service_lines="NURSING_HOME",
            license_status="UNVERIFIED",
            min_hourly_rate=25.0,
            response_propensity=0.8,
            fatigue_score=0.0,
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)

        response = client.post(
            f"/api/caregivers/provision-from-provider/{provider.provider_id}",
            json={
                "employment_tier": "TIER1_W2",
                "maryland_residence_county": "Baltimore",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["profile"]["provider_id"] == str(provider.provider_id)
        assert body["w2_account"]["maryland_residence_county"] == "Baltimore County"

        profile_id = body["profile"]["caregiver_profile_id"]
        _cleanup(db, profile_id)
        db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider.provider_id).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()
