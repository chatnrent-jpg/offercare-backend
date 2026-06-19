from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicalPlacementLedger, MarylandFacility, MarylandProvider
from app.seed import seed_saint_judes_demo
from app.services.license_verification import is_valid_npi
from app.services.shift_lock import lock_shift_from_sms_reply
from app.services.shift_ranking import notify_top_clinicians_for_offer
from app.services.vms_submission import list_placements


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


def test_admin_dashboard_static_page(client: TestClient) -> None:
    response = client.get("/admin/")
    assert response.status_code == 200
    assert "OfferCare.ai Admin" in response.text
    assert "/admin/app.js" in response.text


def test_list_placements_endpoint(client: TestClient, db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = uuid.UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    lock = lock_shift_from_sms_reply(db, from_phone="+14105550001", message_body="YES")
    assert lock.placement_id is not None

    response = client.get("/api/vms/placements")
    assert response.status_code == 200
    rows = response.json()
    assert any(row["placement_id"] == str(lock.placement_id) for row in rows)


def test_list_placements_service(db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    seed = int(token, 16)
    provider = MarylandProvider(
        full_name="Placement Nurse",
        email=f"place.{token}@offercare.demo",
        phone_number=f"+1410{seed % 10_000_000:07d}",
        npi_number=_make_valid_npi(seed),
        md_license_number=f"RN-MD-{token.upper()}",
        license_status="VERIFIED",
        min_hourly_rate=90.0,
    )
    facility = MarylandFacility(
        name=f"Placement Hospital {token}",
        facility_type="HOSPITAL",
        county="Howard County",
    )
    db.add_all([provider, facility])
    db.flush()

    from app.models import OfferCareJobOffer

    offer = OfferCareJobOffer(
        facility_id=facility.facility_id,
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
        compliance_lock_status="LOCKED",
        assigned_provider_id=provider.provider_id,
    )
    db.add(offer)
    db.flush()

    placement = ClinicalPlacementLedger(
        offer_id=offer.offer_id,
        facility_name=facility.name,
        clinical_unit="ICU_RN",
        hourly_bill_rate=120.0,
        assigned_clinician_id=provider.provider_id,
        compliance_snapshot_token="abc123",
        vms_submission_status="PENDING",
    )
    db.add(placement)
    db.commit()

    rows = list_placements(db, status="PENDING", limit=10)
    assert any(row["placement_id"] == placement.placement_id for row in rows)
    assert rows[0]["clinician_name"] == "Placement Nurse"
