from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.schemas import ClinicianApplyRequest
from app.services.license_verification import apply_as_clinician, is_valid_npi, verify_clinician


def _make_valid_npi(seed: int) -> str:
    base9 = f"{seed % 1_000_000_000:09d}"
    for check in range(10):
        candidate = f"{base9}{check}"
        if is_valid_npi(candidate):
            return candidate
    raise ValueError("unable to build valid NPI")


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_clinician_portal_static_page(client: TestClient) -> None:
    response = client.get("/portal/")
    assert response.status_code == 200
    assert "VettedCare.ai Portal" in response.text
    assert "/portal/app.js" in response.text
    assert "Your placements" in response.text
    assert "Mid-Atlantic clinicians" in response.text


def test_clinician_me_placements_endpoint(db: Session, client: TestClient) -> None:
    token = uuid.uuid4().hex[:6]
    seed = int(token, 16)
    payload = ClinicianApplyRequest(
        full_name="Portal Placement Nurse",
        email=f"portal.place.{token}@offercare.demo",
        phone_number=f"410{seed % 10_000_000:07d}",
        npi_number=_make_valid_npi(seed),
        md_license_number=f"RN-MD-{token.upper()}",
        min_hourly_rate=95.0,
        password="SecretPass1",
    )
    provider, _ = apply_as_clinician(db, payload)
    verify_clinician(db, provider.provider_id, action="VERIFY", reviewer="admin")

    login_resp = client.post(
        "/api/clinicians/login",
        json={"email": payload.email, "password": "SecretPass1"},
    )
    assert login_resp.status_code == 200
    bearer = login_resp.json()["access_token"]

    placements_resp = client.get(
        "/api/clinicians/me/placements",
        headers={"Authorization": f"Bearer {bearer}"},
    )
    assert placements_resp.status_code == 200
    assert placements_resp.json() == []

    unauth_resp = client.get("/api/clinicians/me/placements")
    assert unauth_resp.status_code == 401
