"""Maryland market localization — MBON validator, MD leads, contract margins."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from compliance.md_licensure_validator import (
    REJECTED_COMPLIANCE,
    MarylandComplianceValidator,
    build_mbon_lookup_request,
    is_malformed_license_number,
    verify_provider_md_licensure,
)
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from data_engine.contract_processor import extract_contract_terms
from data_engine.md_lead_schema import MD_REQUIRED_LEAD_FIELDS, validate_md_lead_row
from data_engine.md_outreach_sequencer import build_outreach_copy


def test_md_lead_requires_market_fields() -> None:
    errors = validate_md_lead_row({}, row_number=2)
    assert len(errors) >= len(MD_REQUIRED_LEAD_FIELDS)


def test_md_lead_accepts_snf_row() -> None:
    row = {
        "facility_name": "FutureCare Northpoint",
        "facility_type": "SNF",
        "md_license_status": "ACTIVE",
        "decision_maker_name": "Jane Smith",
        "decision_maker_title": "Director of Nursing",
        "direct_email": "jsmith@futurecare.com",
        "facility_county": "Baltimore",
        "procurement_urgency": "HIGH",
        "source_url": "https://health.maryland.gov/ohcq/",
    }
    assert validate_md_lead_row(row, row_number=2) == []


def test_malformed_license_skips_safely() -> None:
    assert is_malformed_license_number("CNA", "")
    assert is_malformed_license_number("CNA", "X")
    assert not is_malformed_license_number("CNA", "CNA-MD-12345")


def test_contract_review_margins_below_md_floor(monkeypatch) -> None:
    monkeypatch.setattr("data_engine.contract_processor.settings.MD_CNA_MIN_BILL_RATE", 28.0)
    monkeypatch.setattr("data_engine.contract_processor.settings.MD_CNA_MIN_MARGIN_PCT", 0.16)
    text = "CNA Bill Rate: $24.00 per hour CNA Pay Rate: $18.00 per hour"
    extraction = extract_contract_terms(text, source_filename="low_cna.txt")
    assert extraction.review_status == "REVIEW_MARGINS"
    assert extraction.dispatch_halted is True
    assert extraction.staffing_role == "CNA"


def test_contract_healthy_cna_margin_active(monkeypatch) -> None:
    monkeypatch.setattr("data_engine.contract_processor.settings.MD_CNA_MIN_BILL_RATE", 28.0)
    monkeypatch.setattr("data_engine.contract_processor.settings.MD_CNA_MIN_MARGIN_PCT", 0.16)
    text = "CNA Bill Rate: $34.00 per hour CNA Pay Rate: $24.00 per hour"
    extraction = extract_contract_terms(text, source_filename="good_cna.txt")
    assert extraction.review_status == "ACTIVE"
    assert extraction.dispatch_halted is False


def test_outreach_copy_mentions_mbon() -> None:
    class Lead:
        facility_name = "Test SNF"
        facility_type = "SNF"
        facility_county = "Baltimore"
        county = "Baltimore"
        decision_maker_name = "Jane Smith"
        decision_maker_title = "DON"
        contact_name = None
        contact_role = "DON"

    copy = build_outreach_copy(Lead())  # type: ignore[arg-type]
    assert "MBON" in copy["email_body"]
    assert copy["sms_body"]


def test_evaluate_mbon_blocks_discipline_and_expiry() -> None:
    from compliance.md_licensure_validator import FacilityTarget, MarylandComplianceValidator, ProviderCompliancePayload

    expires = datetime.now(timezone.utc) + timedelta(days=10)
    result = MarylandComplianceValidator().validate_for_facility(
        ProviderCompliancePayload(
            credential_type="CNA",
            license_number="CNA-MD-TEST",
            license_expires_on=expires,
            has_gna_endorsement=True,
            ohcq_sanction_flag=True,
            mbon_status="ACTIVE",
        ),
        FacilityTarget(facility_type="SNF", county="Baltimore"),
    )
    assert result.compliant is False
    assert "ohcq_sanction_active" in result.errors
    assert "license_expires_within_buffer" in result.errors


@pytest.mark.parametrize(
    "license_suffix,expect_block",
    [
        ("D", True),
        ("X", True),
        ("", False),
    ],
)
def test_md_licensure_validator_blocks_sanctions_and_expiry(
    client, license_suffix: str, expect_block: bool
) -> None:
    from app.database import SessionLocal
    from app.models import MarylandProvider

    token = uuid4().hex[:8].upper()
    email = f"cna.{token}@example.com"
    db = SessionLocal()
    try:
        provider = MarylandProvider(
            full_name="Test CNA",
            email=email,
            phone_number=f"410555{token[:4]}",
            npi_number=synthetic_npi_for_caregiver(email),
            md_license_number=f"CNA-MD-{token}{license_suffix}",
            state="MD",
            credential_type="CNA",
            service_lines="NURSING_HOME",
            license_status="UNVERIFIED",
            min_hourly_rate=22.0,
            response_propensity=0.5,
            fatigue_score=0.0,
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)

        outcome = verify_provider_md_licensure(db, provider)
        if expect_block:
            assert outcome.block_dispatch is True
            assert outcome.disposition == REJECTED_COMPLIANCE
        else:
            assert outcome.disposition == "VERIFIED"

        lookup = build_mbon_lookup_request(provider)
        assert lookup is not None
        assert lookup.requires_gna_endorsement is True
    finally:
        db.close()


def test_md_licensure_malformed_exits_without_block() -> None:
    from compliance.md_licensure_validator import verify_provider_md_licensure
    from app.models import MarylandProvider

    provider = MarylandProvider(
        full_name="Bad License",
        email="bad.unit@example.com",
        phone_number="4105570001",
        npi_number="8084012345",
        md_license_number="XX",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="UNVERIFIED",
        min_hourly_rate=22.0,
        response_propensity=0.5,
        fatigue_score=0.0,
    )
    outcome = verify_provider_md_licensure(None, provider)  # type: ignore[arg-type]
    assert outcome.disposition == "SKIPPED_MALFORMED"
    assert outcome.block_dispatch is False


def test_md_facility_contact_role_normalization() -> None:
    from data_engine.md_facility_import import (
        _normalize_contact_role,
        _normalize_facility_type,
        _outreach_status_for_type,
    )

    assert _normalize_contact_role("DON") == "DON"
    assert _normalize_contact_role("Director of Nursing") == "DON"
    assert _normalize_contact_role("HR Manager") == "HR_HEAD"
    assert _normalize_facility_type("SNF") == "SNF"
    assert _normalize_facility_type("Assisted Living") == "ALF"
    assert _normalize_facility_type("Home Health Agency") == "HHA"
    assert _outreach_status_for_type("SNF") == "READY"
    assert _outreach_status_for_type("ALF") == "PENDING"


def test_import_scraped_facilities_csv(client) -> None:
    from pathlib import Path
    from sqlalchemy import inspect

    from app.database import SessionLocal
    from data_engine.md_facility_import import import_scraped_facilities_csv

    csv_path = Path(__file__).resolve().parents[1] / "data_engine" / "raw_leads" / "md_facilities_scraped.csv"
    if not csv_path.is_file():
        pytest.skip("md_facilities_scraped.csv not present")

    db = SessionLocal()
    try:
        if "facilities" not in inspect(db.get_bind()).get_table_names():
            pytest.skip("facilities table not migrated — run alembic upgrade head")
        result = import_scraped_facilities_csv(db, csv_path)
        assert result["skipped"] == 0
        assert result["inserted_facilities"] + result["updated_facilities"] >= 10
        assert len(result["rows"]) >= 10
        assert result.get("outreach_sync") is not None
        assert result["outreach_sync"]["payloads_generated"] >= 0
    finally:
        db.close()


def test_sync_ready_facility_contacts_to_outreach(client) -> None:
    from sqlalchemy import inspect

    from app.database import SessionLocal
    from app.models import MdOutreachPayload
    from data_engine.md_outreach_sequencer import export_manus_outreach_queue

    db = SessionLocal()
    try:
        if "facility_contact_id" not in {
            col["name"] for col in inspect(db.get_bind()).get_columns("md_outreach_payloads")
        }:
            pytest.skip("facility_contact_id column not migrated — run alembic upgrade head")

        queue = export_manus_outreach_queue(db, limit=50)
        assert queue["count"] >= 1
        snf_payloads = [row for row in queue["payloads"] if row.get("facility_type") == "SNF"]
        assert snf_payloads
        assert snf_payloads[0]["source"] == "facility_contacts"
        assert snf_payloads[0]["direct_email"]
        assert "MBON" in snf_payloads[0]["email_body"]

        linked = (
            db.query(MdOutreachPayload)
            .filter(MdOutreachPayload.facility_contact_id.isnot(None))
            .count()
        )
        assert linked >= 1
    finally:
        db.close()
