"""B2B facility invoicing markup engine — gross pay, platform margin, employer FICA."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    ClinicalPlacementLedger,
    FacilityBillingAuditLedger,
    MarylandFacility,
    OfferCareJobOffer,
)
from app.services.clinician_payments import _shift_hours
from app.services.shift_schedule import resolve_offer_shift_window

logger = logging.getLogger(__name__)

EMPLOYER_FICA_MATCH_RATE = Decimal("0.0765")


@dataclass(frozen=True)
class FacilityInvoiceLineItem:
    label: str
    amount: Decimal
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "amount": float(self.amount),
            "description": self.description,
        }


@dataclass
class FacilityInvoicePayload:
    hours_worked: Decimal
    gross_caregiver_pay_rate: Decimal
    margin_pct: Decimal
    employer_fica_rate: Decimal
    gross_pay: Decimal
    platform_margin: Decimal
    employer_taxes: Decimal
    total_facility_bill: Decimal
    line_items: list[FacilityInvoiceLineItem]
    calculated_at_utc: str
    timesheet_id: str | None = None
    provider_id: str | None = None
    facility_id: str | None = None
    offer_id: str | None = None
    facility_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["hours_worked"] = float(self.hours_worked)
        payload["gross_caregiver_pay_rate"] = float(self.gross_caregiver_pay_rate)
        payload["margin_pct"] = float(self.margin_pct)
        payload["employer_fica_rate"] = float(self.employer_fica_rate)
        payload["gross_pay"] = float(self.gross_pay)
        payload["platform_margin"] = float(self.platform_margin)
        payload["employer_taxes"] = float(self.employer_taxes)
        payload["total_facility_bill"] = float(self.total_facility_bill)
        payload["line_items"] = [item.to_dict() for item in self.line_items]
        return payload


def _money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rate(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _default_margin_pct() -> Decimal:
    configured = getattr(settings, "B2B_INVOICE_MARGIN_PCT", None)
    if configured is not None:
        return _rate(configured)
    return Decimal("0.40")


def calculate_facility_invoice_payload(
    hours_worked: float | Decimal,
    gross_caregiver_pay_rate: float | Decimal,
    *,
    margin_pct: float | Decimal | None = None,
    employer_fica_rate: float | Decimal | None = None,
    timesheet_id: str | UUID | None = None,
    provider_id: str | UUID | None = None,
    facility_id: str | UUID | None = None,
    offer_id: str | UUID | None = None,
    facility_name: str | None = None,
) -> dict[str, Any]:
    """Compute itemized facility invoice from logged shift hours and caregiver pay rate."""
    hours = _money(hours_worked)
    if hours <= 0:
        raise ValueError("hours_worked_must_be_positive")

    pay_rate = _money(gross_caregiver_pay_rate)
    if pay_rate <= 0:
        raise ValueError("gross_caregiver_pay_rate_must_be_positive")

    margin = _rate(margin_pct if margin_pct is not None else _default_margin_pct())
    fica_rate = _rate(employer_fica_rate if employer_fica_rate is not None else EMPLOYER_FICA_MATCH_RATE)

    gross_pay = _money(hours * pay_rate)
    platform_margin = _money(gross_pay * margin)
    employer_taxes = _money(gross_pay * fica_rate)
    total_facility_bill = _money(gross_pay + platform_margin + employer_taxes)

    line_items = [
        FacilityInvoiceLineItem(
            label="Gross Pay",
            amount=gross_pay,
            description=f"{hours} hrs × ${pay_rate}/hr caregiver gross pay",
        ),
        FacilityInvoiceLineItem(
            label="Platform Margin",
            amount=platform_margin,
            description=f"{float(margin * 100):.2f}% markup on gross pay",
        ),
        FacilityInvoiceLineItem(
            label="Employer Taxes",
            amount=employer_taxes,
            description=f"Employer FICA match {float(fica_rate * 100):.2f}% (Social Security + Medicare)",
        ),
        FacilityInvoiceLineItem(
            label="Total Facility Bill",
            amount=total_facility_bill,
            description="Gross Pay + Platform Margin + Employer Taxes",
        ),
    ]

    invoice = FacilityInvoicePayload(
        hours_worked=hours,
        gross_caregiver_pay_rate=pay_rate,
        margin_pct=margin,
        employer_fica_rate=fica_rate,
        gross_pay=gross_pay,
        platform_margin=platform_margin,
        employer_taxes=employer_taxes,
        total_facility_bill=total_facility_bill,
        line_items=line_items,
        calculated_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        timesheet_id=str(timesheet_id) if timesheet_id else None,
        provider_id=str(provider_id) if provider_id else None,
        facility_id=str(facility_id) if facility_id else None,
        offer_id=str(offer_id) if offer_id else None,
        facility_name=facility_name,
    )
    return invoice.to_dict()


def _resolve_shift_billing_context(
    db: Session,
    *,
    timesheet_id: UUID,
    provider_id: UUID,
    gross_pay_amount: Decimal | None = None,
    hours_worked: float | None = None,
    caregiver_hourly_pay_rate: float | None = None,
) -> dict[str, Any]:
    placement = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.placement_id == timesheet_id)
        .first()
    )
    offer = None
    facility = None
    if placement is not None:
        offer = (
            db.query(OfferCareJobOffer)
            .filter(OfferCareJobOffer.offer_id == placement.offer_id)
            .first()
        )
        if offer is not None and offer.facility_id is not None:
            facility = (
                db.query(MarylandFacility)
                .filter(MarylandFacility.facility_id == offer.facility_id)
                .first()
            )

    resolved_hours = hours_worked
    if resolved_hours is None and offer is not None:
        start, end = resolve_offer_shift_window(
            offer,
            fallback_anchor=placement.outbound_payload_timestamp if placement else None,
        )
        resolved_hours = _shift_hours(start, end)

    resolved_rate = caregiver_hourly_pay_rate
    if resolved_rate is None and offer is not None:
        resolved_rate = float(offer.hourly_pay_rate or 0)
    if resolved_rate is None and placement is not None and resolved_hours:
        resolved_rate = float(placement.hourly_bill_rate or 0)

    if gross_pay_amount is not None and resolved_hours and not resolved_rate:
        resolved_rate = float(_money(Decimal(str(gross_pay_amount)) / Decimal(str(resolved_hours))))

    if resolved_hours is None or resolved_rate is None:
        raise ValueError("shift_billing_context_incomplete")

    return {
        "hours_worked": resolved_hours,
        "gross_caregiver_pay_rate": resolved_rate,
        "timesheet_id": str(timesheet_id),
        "provider_id": str(provider_id),
        "offer_id": str(placement.offer_id) if placement else None,
        "facility_id": str(facility.facility_id) if facility else None,
        "facility_name": placement.facility_name if placement else None,
    }


def persist_facility_billing_audit(
    db: Session,
    invoice_payload: dict[str, Any],
    *,
    commit: bool = False,
    encrypt: bool = True,
) -> FacilityBillingAuditLedger:
    # Encrypt sensitive invoice data if enabled
    if encrypt and settings.INVOICE_ENCRYPTION_ENABLED:
        from app.services.invoice_encryption import encrypt_invoice
        
        encrypted_payload = encrypt_invoice(invoice_payload.copy())
        logger.info(f"[B2B INVOICING] Encrypted invoice data for audit persistence")
    else:
        encrypted_payload = invoice_payload
    
    row = FacilityBillingAuditLedger(
        audit_id=uuid4(),
        timesheet_id=UUID(str(encrypted_payload["timesheet_id"]))
        if encrypted_payload.get("timesheet_id")
        else None,
        provider_id=UUID(str(encrypted_payload["provider_id"]))
        if encrypted_payload.get("provider_id")
        else None,
        facility_id=UUID(str(encrypted_payload["facility_id"]))
        if encrypted_payload.get("facility_id")
        else None,
        offer_id=UUID(str(encrypted_payload["offer_id"])) if encrypted_payload.get("offer_id") else None,
        hours_worked=encrypted_payload["hours_worked"],
        gross_caregiver_pay_rate=encrypted_payload["gross_caregiver_pay_rate"],
        margin_pct=encrypted_payload["margin_pct"],
        employer_fica_rate=encrypted_payload["employer_fica_rate"],
        gross_pay=encrypted_payload["gross_pay"],
        platform_margin=encrypted_payload["platform_margin"],
        employer_taxes=encrypted_payload["employer_taxes"],
        total_facility_bill=encrypted_payload["total_facility_bill"],
        invoice_payload_json=json.dumps(encrypted_payload, separators=(",", ":")),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def calculate_and_log_facility_invoice_on_shift_complete(
    db: Session,
    *,
    timesheet_id: UUID,
    provider_id: UUID,
    gross_pay_amount: Decimal | None = None,
    hours_worked: float | None = None,
    caregiver_hourly_pay_rate: float | None = None,
    margin_pct: float | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    """Hook listener — run when a caregiver completes a shift (supervisor sign-off)."""
    if not getattr(settings, "B2B_INVOICING_ENABLED", True):
        return {"skipped": True, "reason": "b2b_invoicing_disabled"}

    context = _resolve_shift_billing_context(
        db,
        timesheet_id=timesheet_id,
        provider_id=provider_id,
        gross_pay_amount=gross_pay_amount,
        hours_worked=hours_worked,
        caregiver_hourly_pay_rate=caregiver_hourly_pay_rate,
    )
    invoice_payload = calculate_facility_invoice_payload(
        context["hours_worked"],
        context["gross_caregiver_pay_rate"],
        margin_pct=margin_pct,
        timesheet_id=context["timesheet_id"],
        provider_id=context["provider_id"],
        facility_id=context.get("facility_id"),
        offer_id=context.get("offer_id"),
        facility_name=context.get("facility_name"),
    )
    audit_row = persist_facility_billing_audit(db, invoice_payload, commit=commit)
    logger.info(
        "B2B facility invoice logged audit=%s timesheet=%s total=%s",
        audit_row.audit_id,
        timesheet_id,
        invoice_payload["total_facility_bill"],
    )
    return {
        "audit_id": str(audit_row.audit_id),
        "invoice": invoice_payload,
    }
