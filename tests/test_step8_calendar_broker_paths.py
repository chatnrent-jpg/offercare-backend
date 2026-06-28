from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.demo_environment import find_demo_clinician_for_shift
from app.services.geo_matching import list_geo_matched_providers_for_offer
from app.services.matched_shift_alerts import list_matched_providers_for_offer
from app.services.shift_matching import provider_matches_open_shift


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _provider() -> MarylandProvider:
    token = uuid.uuid4().hex[:6]
    return MarylandProvider(
        full_name=f"Broker Path {token}",
        email=f"broker.path.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"broker.path.{token}@offercare.demo"),
        md_license_number=f"CNA-MD-BRK{token.upper()}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=20.0,
        response_propensity=0.8,
        fatigue_score=0.0,
    )


def test_match_services_import_provider_matches_open_shift() -> None:
    import app.services.demo_environment as demo_environment
    import app.services.geo_matching as geo_matching
    import app.services.matched_shift_alerts as matched_shift_alerts

    assert "provider_matches_open_shift" in geo_matching.__dict__
    assert "provider_matches_open_shift" in matched_shift_alerts.__dict__
    assert "provider_matches_open_shift" in demo_environment.__dict__


def test_provider_matches_open_shift_honors_broker_rejection(db: Session) -> None:
    provider = _provider()
    row = {
        "offer_id": str(uuid.uuid4()),
        "state": "MD",
        "facility_type": "NURSING_HOME",
        "shift_role": "CNA",
        "hourly_pay_rate": 25.0,
        "shift_starts_at": None,
        "shift_ends_at": None,
        "facility_id": str(uuid.uuid4()),
        "facility_name": "Test SNF",
        "county": "Baltimore",
    }
    with patch(
        "app.services.shift_matching._broker_confirms_provider_match",
        return_value=False,
    ):
        assert provider_matches_open_shift(db, provider, row) is False


def test_find_demo_clinician_for_shift_uses_broker_gate(db: Session) -> None:
    from app.seed import seed_nursing_home_demo
    from app.services.shift_offer_generator import get_open_shift_by_id

    seeded = seed_nursing_home_demo(db)
    row = get_open_shift_by_id(db, seeded["offer_id"])
    assert row is not None
    with patch(
        "app.services.shift_matching._broker_confirms_provider_match",
        return_value=False,
    ):
        assert find_demo_clinician_for_shift(db, row) is None


def test_geo_and_push_match_helpers_callable(db: Session) -> None:
    from app.seed import seed_nursing_home_demo

    seeded = seed_nursing_home_demo(db)
    offer_id = seeded["offer_id"]
    assert isinstance(list_matched_providers_for_offer(db, offer_id), list)
    assert isinstance(list_geo_matched_providers_for_offer(db, offer_id), list)
