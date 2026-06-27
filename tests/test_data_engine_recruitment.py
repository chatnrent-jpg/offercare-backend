"""Facility recruitment data_engine — contract margin gate, shift dedupe, lead CSV."""

from __future__ import annotations

from data_engine.contract_processor import extract_contract_terms
from data_engine.lead_schema import REQUIRED_LEAD_FIELDS, validate_lead_row
from data_engine.shift_ingest import shift_composite_hash, validate_shift_record


def test_lead_row_requires_guardrail_fields() -> None:
    errors = validate_lead_row({}, row_number=2)
    assert len(errors) == len(REQUIRED_LEAD_FIELDS)


def test_lead_row_accepts_valid_row() -> None:
    row = {
        "facility_name": "Mercy Baltimore",
        "contact_role": "CNO",
        "email_domain": "mercy.net",
        "procurement_urgency": "HIGH",
        "source_url": "https://procurement.maryland.gov/example",
    }
    assert validate_lead_row(row, row_number=2) == []


def test_shift_composite_hash_stable() -> None:
    a = shift_composite_hash(
        facility_id="abc",
        shift_date="2026-06-27",
        unit_dept="ICU",
        start_time="07:00",
    )
    b = shift_composite_hash(
        facility_id="abc",
        shift_date="2026-06-27",
        unit_dept="ICU",
        start_time="07:00",
    )
    assert a == b
    assert len(a) == 64


def test_shift_record_validation() -> None:
    assert validate_shift_record({}) == [
        "missing_facility_id",
        "missing_shift_date",
        "missing_unit_dept",
        "missing_start_time",
        "missing_shift_role",
        "missing_hourly_pay_rate",
    ]


def test_contract_margin_halts_dispatch(monkeypatch) -> None:
    monkeypatch.setattr("data_engine.contract_processor.settings.CONTRACT_MIN_MARGIN_PCT", 0.18)
    monkeypatch.setattr("data_engine.contract_processor.settings.CONTRACT_BASELINE_MIN_PAY_RATE", 28.0)

    text = """
    Facility Name: Sample SNF
    Bill Rate: $55.00 per hour
    Pay Rate: $52.00 per hour
    Must notify 2 hours prior to shift cancellation.
    Requires BLS, ACLS, and 2 years ICU experience.
    """
    extraction = extract_contract_terms(text, source_filename="sample.txt")
    assert extraction.review_status == "REVIEW_MARGINS"
    assert extraction.dispatch_halted is True
    assert extraction.margin_pct is not None
    assert extraction.margin_pct < 0.18


def test_contract_healthy_margin_active(monkeypatch) -> None:
    monkeypatch.setattr("data_engine.contract_processor.settings.CONTRACT_MIN_MARGIN_PCT", 0.18)
    monkeypatch.setattr("data_engine.contract_processor.settings.CONTRACT_BASELINE_MIN_PAY_RATE", 28.0)

    text = "Bill Rate: $60.00 per hour Pay Rate: $40.00 per hour Requires BLS"
    extraction = extract_contract_terms(text, source_filename="good.txt")
    assert extraction.review_status == "ACTIVE"
    assert extraction.dispatch_halted is False
    assert extraction.margin_pct is not None
    assert extraction.margin_pct >= 0.18
