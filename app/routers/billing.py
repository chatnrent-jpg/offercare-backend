"""
B2B Billing API — Invoice calculation and audit retrieval.

Sprint: VCAI-B2B-BILLING-API-2026-07-07
Purpose: HTTP endpoints for facility billing, invoice calculation, and audit logs.

Endpoints:
1. POST /api/billing/calculate — Real-time invoice calculation
2. GET /api/billing/audits/{facility_id} — Historical invoices by facility
3. GET /api/billing/audits/shift/{timesheet_id} — Invoice by timesheet/shift
4. GET /api/billing/summary/{facility_id} — Billing summary statistics
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.config import settings
from app.database import get_db
from app.models import FacilityBillingAuditLedger, MarylandFacility
from app.services.b2b_invoicing_engine import (
    calculate_facility_invoice_payload,
    persist_facility_billing_audit,
)
from app.services.invoice_encryption import decrypt_invoice

router = APIRouter(prefix="/api/billing", tags=["billing"])


# ═══════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE SCHEMAS
# ═══════════════════════════════════════════════════════════════════


class InvoiceCalculationRequest(BaseModel):
    """Real-time invoice calculation request."""

    hours_worked: float = Field(..., gt=0, description="Shift hours worked")
    gross_caregiver_pay_rate: float = Field(..., gt=0, description="Caregiver hourly pay rate")
    margin_pct: float | None = Field(None, ge=0, le=1, description="Platform margin percentage (0.40 = 40%)")
    employer_fica_rate: float | None = Field(None, ge=0, le=1, description="Employer FICA rate (default 0.0765)")
    timesheet_id: str | None = Field(None, description="Optional timesheet ID for audit trail")
    provider_id: str | None = Field(None, description="Optional provider ID for audit trail")
    facility_id: str | None = Field(None, description="Optional facility ID for audit trail")
    facility_name: str | None = Field(None, description="Optional facility name for audit trail")
    persist_audit: bool = Field(False, description="Persist invoice to audit ledger")


class InvoiceLineItem(BaseModel):
    """Invoice line item."""

    label: str
    amount: float
    description: str


class InvoiceCalculationResponse(BaseModel):
    """Real-time invoice calculation response."""

    hours_worked: float
    gross_caregiver_pay_rate: float
    margin_pct: float
    employer_fica_rate: float
    gross_pay: float
    platform_margin: float
    employer_taxes: float
    total_facility_bill: float
    line_items: list[InvoiceLineItem]
    calculated_at_utc: str
    audit_id: str | None = None
    timesheet_id: str | None = None
    provider_id: str | None = None
    facility_id: str | None = None
    facility_name: str | None = None


class BillingAuditRecord(BaseModel):
    """Historical billing audit record."""

    audit_id: str
    timesheet_id: str | None
    provider_id: str | None
    facility_id: str | None
    offer_id: str | None
    hours_worked: float
    gross_caregiver_pay_rate: float
    margin_pct: float
    gross_pay: float
    platform_margin: float
    employer_taxes: float
    total_facility_bill: float
    created_at: datetime


class BillingAuditListResponse(BaseModel):
    """List of billing audit records."""

    total: int
    records: list[BillingAuditRecord]
    facility_id: str | None = None
    facility_name: str | None = None


class BillingSummaryResponse(BaseModel):
    """Billing summary statistics for a facility."""

    facility_id: str
    facility_name: str | None
    total_invoices: int
    total_billed: float
    total_gross_pay: float
    total_platform_margin: float
    total_employer_taxes: float
    average_hourly_rate: float
    date_range_start: datetime | None
    date_range_end: datetime | None


# ═══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════


@router.post("/calculate", response_model=InvoiceCalculationResponse)
def calculate_invoice(
    payload: InvoiceCalculationRequest,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin_api_key),
) -> dict[str, Any]:
    """
    Real-time invoice calculation endpoint.
    
    Calculates facility billing from shift hours and pay rate.
    Optionally persists to audit ledger for recordkeeping.
    
    **Authority:** Amendment B (§5.14) - B2B Invoicing Markup Engine
    """
    if not settings.B2B_INVOICING_ENABLED:
        raise HTTPException(status_code=503, detail="B2B invoicing is disabled")

    try:
        invoice = calculate_facility_invoice_payload(
            hours_worked=payload.hours_worked,
            gross_caregiver_pay_rate=payload.gross_caregiver_pay_rate,
            margin_pct=payload.margin_pct,
            employer_fica_rate=payload.employer_fica_rate,
            timesheet_id=payload.timesheet_id,
            provider_id=payload.provider_id,
            facility_id=payload.facility_id,
            facility_name=payload.facility_name,
        )

        # Optionally persist to audit ledger
        audit_id = None
        if payload.persist_audit:
            audit_row = persist_facility_billing_audit(db, invoice, commit=True)
            audit_id = str(audit_row.audit_id)

        return {**invoice, "audit_id": audit_id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"invoice_calculation_failed: {str(e)}")


@router.get("/audits/facility/{facility_id}", response_model=BillingAuditListResponse)
def get_facility_billing_audits(
    facility_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin_api_key),
) -> dict[str, Any]:
    """
    Retrieve historical billing audit records for a facility.
    
    Returns all invoices generated for a specific facility,
    ordered by most recent first.
    
    **Authority:** Amendment B (§5.14) - B2B Invoicing Markup Engine
    """
    if not settings.B2B_INVOICING_ENABLED:
        raise HTTPException(status_code=503, detail="B2B invoicing is disabled")

    # Check if facility exists
    facility = db.query(MarylandFacility).filter(
        MarylandFacility.facility_id == facility_id
    ).first()

    if not facility:
        raise HTTPException(status_code=404, detail="facility_not_found")

    # Query audit records
    query = (
        db.query(FacilityBillingAuditLedger)
        .filter(FacilityBillingAuditLedger.facility_id == facility_id)
        .order_by(desc(FacilityBillingAuditLedger.created_at))
    )

    total = query.count()
    records = query.offset(offset).limit(limit).all()

    audit_records = []
    for record in records:
        # Decrypt encrypted fields if present
        decrypted_data = {
            "gross_pay": record.gross_pay,
            "platform_margin": record.platform_margin,
            "employer_taxes": record.employer_taxes,
            "total_facility_bill": record.total_facility_bill,
            "gross_caregiver_pay_rate": record.gross_caregiver_pay_rate,
            "_encrypted": getattr(record, "_encrypted", False)
        }
        
        if settings.INVOICE_ENCRYPTION_ENABLED:
            decrypted_data = decrypt_invoice(decrypted_data)
        
        audit_records.append(BillingAuditRecord(
            audit_id=str(record.audit_id),
            timesheet_id=str(record.timesheet_id) if record.timesheet_id else None,
            provider_id=str(record.provider_id) if record.provider_id else None,
            facility_id=str(record.facility_id) if record.facility_id else None,
            offer_id=str(record.offer_id) if record.offer_id else None,
            hours_worked=float(record.hours_worked),
            gross_caregiver_pay_rate=float(decrypted_data.get("gross_caregiver_pay_rate", record.gross_caregiver_pay_rate)),
            margin_pct=float(record.margin_pct),
            gross_pay=float(decrypted_data.get("gross_pay", record.gross_pay)),
            platform_margin=float(decrypted_data.get("platform_margin", record.platform_margin)),
            employer_taxes=float(decrypted_data.get("employer_taxes", record.employer_taxes)),
            total_facility_bill=float(decrypted_data.get("total_facility_bill", record.total_facility_bill)),
            created_at=record.created_at,
        ))

    return {
        "total": total,
        "records": audit_records,
        "facility_id": str(facility_id),
        "facility_name": facility.name,
    }


@router.get("/audits/shift/{timesheet_id}", response_model=BillingAuditRecord)
def get_shift_billing_audit(
    timesheet_id: UUID,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin_api_key),
) -> dict[str, Any]:
    """
    Retrieve billing audit record for a specific shift/timesheet.
    
    Returns the invoice generated for a completed shift.
    
    **Authority:** Amendment B (§5.14) - B2B Invoicing Markup Engine
    """
    if not settings.B2B_INVOICING_ENABLED:
        raise HTTPException(status_code=503, detail="B2B invoicing is disabled")

    record = (
        db.query(FacilityBillingAuditLedger)
        .filter(FacilityBillingAuditLedger.timesheet_id == timesheet_id)
        .first()
    )

    if not record:
        raise HTTPException(status_code=404, detail="billing_audit_not_found")

    # Decrypt encrypted fields if present
    decrypted_data = {
        "gross_pay": record.gross_pay,
        "platform_margin": record.platform_margin,
        "employer_taxes": record.employer_taxes,
        "total_facility_bill": record.total_facility_bill,
        "gross_caregiver_pay_rate": record.gross_caregiver_pay_rate,
        "_encrypted": getattr(record, "_encrypted", False)
    }
    
    if settings.INVOICE_ENCRYPTION_ENABLED:
        decrypted_data = decrypt_invoice(decrypted_data)
    
    return BillingAuditRecord(
        audit_id=str(record.audit_id),
        timesheet_id=str(record.timesheet_id) if record.timesheet_id else None,
        provider_id=str(record.provider_id) if record.provider_id else None,
        facility_id=str(record.facility_id) if record.facility_id else None,
        offer_id=str(record.offer_id) if record.offer_id else None,
        hours_worked=float(record.hours_worked),
        gross_caregiver_pay_rate=float(decrypted_data.get("gross_caregiver_pay_rate", record.gross_caregiver_pay_rate)),
        margin_pct=float(record.margin_pct),
        gross_pay=float(decrypted_data.get("gross_pay", record.gross_pay)),
        platform_margin=float(decrypted_data.get("platform_margin", record.platform_margin)),
        employer_taxes=float(decrypted_data.get("employer_taxes", record.employer_taxes)),
        total_facility_bill=float(decrypted_data.get("total_facility_bill", record.total_facility_bill)),
        created_at=record.created_at,
    )


@router.get("/summary/{facility_id}", response_model=BillingSummaryResponse)
def get_facility_billing_summary(
    facility_id: UUID,
    date_start: datetime | None = None,
    date_end: datetime | None = None,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin_api_key),
) -> dict[str, Any]:
    """
    Retrieve billing summary statistics for a facility.
    
    Aggregates total invoices, revenue, and average rates
    for a given facility over an optional date range.
    
    **Authority:** Amendment B (§5.14) - B2B Invoicing Markup Engine
    """
    if not settings.B2B_INVOICING_ENABLED:
        raise HTTPException(status_code=503, detail="B2B invoicing is disabled")

    # Check if facility exists
    facility = db.query(MarylandFacility).filter(
        MarylandFacility.facility_id == facility_id
    ).first()

    if not facility:
        raise HTTPException(status_code=404, detail="facility_not_found")

    # Build query with optional date range
    query = db.query(FacilityBillingAuditLedger).filter(
        FacilityBillingAuditLedger.facility_id == facility_id
    )

    if date_start:
        query = query.filter(FacilityBillingAuditLedger.created_at >= date_start)
    if date_end:
        query = query.filter(FacilityBillingAuditLedger.created_at <= date_end)

    # Calculate aggregates
    aggregates = query.with_entities(
        func.count(FacilityBillingAuditLedger.audit_id).label("total_invoices"),
        func.sum(FacilityBillingAuditLedger.total_facility_bill).label("total_billed"),
        func.sum(FacilityBillingAuditLedger.gross_pay).label("total_gross_pay"),
        func.sum(FacilityBillingAuditLedger.platform_margin).label("total_platform_margin"),
        func.sum(FacilityBillingAuditLedger.employer_taxes).label("total_employer_taxes"),
        func.avg(FacilityBillingAuditLedger.gross_caregiver_pay_rate).label("average_hourly_rate"),
        func.min(FacilityBillingAuditLedger.created_at).label("date_range_start"),
        func.max(FacilityBillingAuditLedger.created_at).label("date_range_end"),
    ).first()

    return {
        "facility_id": str(facility_id),
        "facility_name": facility.name,
        "total_invoices": aggregates.total_invoices or 0,
        "total_billed": float(aggregates.total_billed or 0),
        "total_gross_pay": float(aggregates.total_gross_pay or 0),
        "total_platform_margin": float(aggregates.total_platform_margin or 0),
        "total_employer_taxes": float(aggregates.total_employer_taxes or 0),
        "average_hourly_rate": float(aggregates.average_hourly_rate or 0),
        "date_range_start": aggregates.date_range_start,
        "date_range_end": aggregates.date_range_end,
    }
