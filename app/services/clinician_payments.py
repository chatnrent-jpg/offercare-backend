"""Clinician payments — instant pay / timesheet payout read models for the portal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import ClinicalPlacementLedger, MarylandProvider, OfferCareJobOffer, ShiftTimesheetPayout
from app.services.shift_matching import is_demo_walkthrough_provider
from app.services.shift_schedule import resolve_offer_shift_window
from app.services.vms_submission import list_clinician_placements

PAYMENT_STATUS_LABELS = {
    "PENDING": "Queued for instant pay",
    "SUBMITTED": "Submitted to payroll",
    "PROCESSING": "Processing payout",
    "PAID": "Paid",
    "FAILED": "Payout review needed",
}


def payment_status_label(status: str | None) -> str:
    key = str(status or "PENDING").upper()
    return PAYMENT_STATUS_LABELS.get(key, key.replace("_", " ").title())


def _shift_hours(start: datetime | None, end: datetime | None) -> float:
    if start is None or end is None:
        return 12.0
    delta = end - start
    hours = delta.total_seconds() / 3600.0
    return round(max(hours, 0.5), 2)


def list_clinician_payments(db: Session, provider_id: UUID, *, limit: int = 25) -> list[dict]:
    rows = (
        db.query(ShiftTimesheetPayout, ClinicalPlacementLedger, OfferCareJobOffer)
        .outerjoin(
            ClinicalPlacementLedger,
            ClinicalPlacementLedger.placement_id == ShiftTimesheetPayout.timesheet_id,
        )
        .outerjoin(
            OfferCareJobOffer,
            OfferCareJobOffer.offer_id == ClinicalPlacementLedger.offer_id,
        )
        .filter(ShiftTimesheetPayout.provider_id == provider_id)
        .order_by(ShiftTimesheetPayout.created_at.desc())
        .limit(limit)
        .all()
    )
    results: list[dict] = []
    for payout, placement, offer in rows:
        facility_name = placement.facility_name if placement else "Shift payout"
        shift_role = placement.clinical_unit if placement else None
        hourly_rate = float(placement.hourly_bill_rate) if placement else None
        shift_starts_at = shift_ends_at = None
        if offer is not None:
            shift_starts_at, shift_ends_at = resolve_offer_shift_window(
                offer,
                fallback_anchor=placement.outbound_payload_timestamp if placement else None,
            )
        results.append(
            {
                "payout_id": payout.payout_id,
                "timesheet_id": payout.timesheet_id,
                "placement_id": placement.placement_id if placement else payout.timesheet_id,
                "facility_name": facility_name,
                "shift_role": shift_role,
                "hourly_rate": hourly_rate,
                "gross_pay_amount": float(payout.gross_pay_amount),
                "payout_status": payout.payout_status,
                "payout_status_label": payment_status_label(payout.payout_status),
                "payout_eligible_at": payout.payout_eligible_at,
                "paid_at": payout.paid_at,
                "stripe_payout_id": payout.stripe_payout_id,
                "shift_starts_at": shift_starts_at,
                "shift_ends_at": shift_ends_at,
            }
        )
    return results


def ensure_demo_portal_payments(db: Session, provider: MarylandProvider) -> int:
    """Create submitted payroll rows for VMS-confirmed demo placements."""
    if not is_demo_walkthrough_provider(provider):
        return 0

    created = 0
    now = datetime.now(timezone.utc)
    window = int(settings.INSTANT_PAY_WINDOW_MINUTES)
    for row in list_clinician_placements(db, provider.provider_id):
        if str(row.get("vms_submission_status") or "").upper() != "SUBMITTED":
            continue
        placement_id = row["placement_id"]
        existing = (
            db.query(ShiftTimesheetPayout)
            .filter(ShiftTimesheetPayout.timesheet_id == placement_id)
            .first()
        )
        if existing is not None:
            continue

        offer = (
            db.query(OfferCareJobOffer)
            .filter(OfferCareJobOffer.offer_id == row["offer_id"])
            .first()
        )
        start, end = resolve_offer_shift_window(
            offer,
            fallback_anchor=row.get("outbound_payload_timestamp"),
        ) if offer is not None else (row.get("shift_starts_at"), row.get("shift_ends_at"))
        hours = _shift_hours(start, end)
        hourly = float(row.get("hourly_bill_rate") or 24.0)
        gross = Decimal(str(round(hours * hourly, 2)))

        db.add(
            ShiftTimesheetPayout(
                timesheet_id=placement_id,
                provider_id=provider.provider_id,
                gross_pay_amount=gross,
                supervisor_name="Demo DON",
                supervisor_signed_at=now,
                payout_eligible_at=now + timedelta(minutes=window),
                payout_status="SUBMITTED",
            )
        )
        created += 1

    if created:
        db.commit()
    return created


def complete_demo_portal_payouts(db: Session, provider: MarylandProvider) -> int:
    """Demo walkthrough — dry-run instant pay completion after payroll submit."""
    if not is_demo_walkthrough_provider(provider):
        return 0

    now = datetime.now(timezone.utc)
    rows = (
        db.query(ShiftTimesheetPayout)
        .filter(
            ShiftTimesheetPayout.provider_id == provider.provider_id,
            ShiftTimesheetPayout.payout_status.in_(["SUBMITTED", "PROCESSING"]),
        )
        .all()
    )
    completed = 0
    for payout in rows:
        token = str(payout.payout_id).replace("-", "")[:8].upper()
        payout.payout_status = "PAID"
        payout.stripe_mode = "DRY_RUN"
        payout.stripe_payout_id = f"DRYRUN-PAY-{token}"
        payout.paid_at = now
        payout.failure_reason = None
        completed += 1

    if completed:
        db.commit()
    return completed
