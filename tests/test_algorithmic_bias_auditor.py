from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility, MarylandProvider, OfferCareJobOffer
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from compliance.algorithmic_bias_auditor import (
    build_claude_prompt_matrix,
    collect_objective_match_metrics,
    intercept_caregiver_shift_match,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _provider(db: Session) -> MarylandProvider:
    token = uuid4().hex[:8]
    email = f"bias.{token}@example.com"
    provider = MarylandProvider(
        full_name=f"Bias Audit {token}",
        email=email,
        phone_number=f"410555{int(token[:4], 16) % 10000:04d}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=f"CNA-BIAS-{token.upper()}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=22.0,
        latitude=39.2904,
        longitude=-76.6122,
    )
    db.add(provider)
    db.flush()
    return provider


def _shift_row(db: Session, provider: MarylandProvider) -> dict:
    facility = MarylandFacility(
        name="Bias Audit SNF",
        facility_type="SNF",
        county="Baltimore City",
        state="MD",
        latitude=39.3000,
        longitude=-76.6200,
    )
    db.add(facility)
    db.flush()
    offer = OfferCareJobOffer(
        facility_id=facility.facility_id,
        shift_role="CNA",
        hourly_pay_rate=28.0,
    )
    db.add(offer)
    db.flush()
    return {
        "offer_id": str(offer.offer_id),
        "facility_id": str(facility.facility_id),
        "facility_name": facility.name,
        "county": facility.county,
        "state": "MD",
        "facility_type": "SNF",
        "shift_role": "CNA",
        "hourly_pay_rate": 28.0,
        "care_tags": ["GNA", "DEMENTIA"],
    }


def test_collect_objective_match_metrics(db) -> None:
    provider = _provider(db)
    row = _shift_row(db, provider)
    metrics = collect_objective_match_metrics(db, provider=provider, shift_row=row)
    assert metrics.mbon_license_status == "VERIFIED"
    assert metrics.geographic_distance_miles is not None
    assert metrics.geographic_distance_miles < 5
    assert "CNA" in metrics.clinical_skills


def test_prompt_matrix_has_four_dimensions() -> None:
    from compliance.algorithmic_bias_auditor import ObjectiveMatchMetrics

    matrix = build_claude_prompt_matrix(
        ObjectiveMatchMetrics(
            mbon_license_status="VERIFIED",
            geographic_distance_miles=12.5,
            historical_facility_rating="md_license_status:ACTIVE",
            clinical_skills=["CNA", "GNA"],
        )
    )
    assert len(matrix["dimensions"]) == 4
    assert matrix["statute"] == "Maryland HB 1106"


def test_intercept_writes_hash_chained_audit_log(db, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_path = tmp_path / "maryland_hb1106_audit.log"
    monkeypatch.setattr("compliance.algorithmic_bias_auditor.settings.BIAS_AUDITOR_DRY_RUN", True)
    monkeypatch.setattr("compliance.algorithmic_bias_auditor.settings.BIAS_AUDITOR_ENABLED", True)
    monkeypatch.setattr("compliance.algorithmic_bias_auditor.settings.BIAS_AUDITOR_LOG_PATH", str(log_path))

    provider = _provider(db)
    row = _shift_row(db, provider)
    first = intercept_caregiver_shift_match(db, provider=provider, shift_row=row)
    second = intercept_caregiver_shift_match(db, provider=provider, shift_row=row)

    assert first.zero_illegal_demographic_bias is True
    assert second.previous_entry_hash == first.entry_hash
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    record = json.loads(lines[1])
    assert record["statute"] == "Maryland HB 1106"
    assert record["objective_metrics"]["mbon_license_status"] == "VERIFIED"
