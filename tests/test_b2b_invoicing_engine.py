from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import FacilityBillingAuditLedger, MarylandProvider
from app.services.b2b_invoicing_engine import (
    EMPLOYER_FICA_MATCH_RATE,
    calculate_and_log_facility_invoice_on_shift_complete,
    calculate_facility_invoice_payload,
    persist_facility_billing_audit,
)
from app.services.care_taxonomy import synthetic_npi_for_caregiver


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_calculate_facility_invoice_payload_default_margin() -> None:
    payload = calculate_facility_invoice_payload(10.0, 50.0)

    assert payload["gross_pay"] == 500.0
    assert payload["platform_margin"] == 200.0
    assert payload["employer_taxes"] == float(Decimal("500.00") * EMPLOYER_FICA_MATCH_RATE)
    assert payload["total_facility_bill"] == round(
        payload["gross_pay"] + payload["platform_margin"] + payload["employer_taxes"],
        2,
    )
    labels = [item["label"] for item in payload["line_items"]]
    assert labels == ["Gross Pay", "Platform Margin", "Employer Taxes", "Total Facility Bill"]


def test_calculate_facility_invoice_payload_custom_margin() -> None:
    payload = calculate_facility_invoice_payload(8.0, 40.0, margin_pct=0.25)

    assert payload["gross_pay"] == 320.0
    assert payload["platform_margin"] == 80.0
    assert payload["margin_pct"] == 0.25


def test_persist_facility_billing_audit(db: Session) -> None:
    token = uuid4().hex[:8]
    provider = MarylandProvider(
        full_name=f"Invoice Audit {token}",
        email=f"invoice.{token}@example.com",
        phone_number=f"410555{int(token[:4], 16) % 10000:04d}",
        npi_number=synthetic_npi_for_caregiver(f"invoice.{token}@example.com"),
        md_license_number=f"CNA-INV-{token}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=25.0,
        home_zip="21201",
    )
    db.add(provider)
    db.flush()

    timesheet_id = uuid4()
    invoice = calculate_facility_invoice_payload(
        12.0,
        45.0,
        timesheet_id=timesheet_id,
        provider_id=provider.provider_id,
    )
    row = persist_facility_billing_audit(db, invoice, commit=False)
    db.flush()

    stored = db.query(FacilityBillingAuditLedger).filter(FacilityBillingAuditLedger.audit_id == row.audit_id).one()
    assert stored.timesheet_id == timesheet_id
    assert float(stored.gross_pay) == invoice["gross_pay"]
    assert float(stored.total_facility_bill) == invoice["total_facility_bill"]
    assert "Platform Margin" in stored.invoice_payload_json


def test_calculate_and_log_from_explicit_hours_and_rate(db: Session) -> None:
    token = uuid4().hex[:8]
    provider = MarylandProvider(
        full_name=f"Invoice Hook {token}",
        email=f"hook.{token}@example.com",
        phone_number=f"410555{int(token[:4], 16) % 10000:04d}",
        npi_number=synthetic_npi_for_caregiver(f"hook.{token}@example.com"),
        md_license_number=f"CNA-HOOK-{token}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=25.0,
        home_zip="21201",
    )
    db.add(provider)
    db.flush()

    timesheet_id = uuid4()
    result = calculate_and_log_facility_invoice_on_shift_complete(
        db,
        timesheet_id=timesheet_id,
        provider_id=provider.provider_id,
        hours_worked=10.0,
        caregiver_hourly_pay_rate=50.0,
        commit=False,
    )
    db.flush()

    assert result["invoice"]["gross_pay"] == 500.0
    audit = db.query(FacilityBillingAuditLedger).filter(
        FacilityBillingAuditLedger.audit_id == result["audit_id"]
    ).one()
    assert audit.timesheet_id == timesheet_id
