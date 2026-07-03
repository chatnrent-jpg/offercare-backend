"""Clinician portal activity feed — lock → VMS → payroll → paid journey timeline."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ClinicalPlacementLedger, OfferCareJobOffer
from app.services.clinician_payments import list_clinician_payments
from app.services.shift_schedule import resolve_offer_shift_window

ACTIVITY_LABELS = {
    "SHIFT_LOCKED": "Shift locked",
    "VMS_SUBMITTED": "Confirmed with facility",
    "PAYROLL_SUBMITTED": "Submitted to payroll",
    "INSTANT_PAYOUT_PAID": "Instant pay deposited",
    "NEXT_SHIFT_AVAILABLE": "Next shift available",
}


def _list_activity_placements(db: Session, provider_id: UUID, *, limit: int = 25) -> list[dict]:
    """Ledger rows without inner-join on offers — avoids empty feed when offer row is missing."""
    rows = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.assigned_clinician_id == provider_id)
        .order_by(ClinicalPlacementLedger.outbound_payload_timestamp.desc())
        .limit(limit)
        .all()
    )
    results: list[dict] = []
    for placement in rows:
        offer = (
            db.query(OfferCareJobOffer)
            .filter(OfferCareJobOffer.offer_id == placement.offer_id)
            .first()
        )
        shift_starts_at = shift_ends_at = None
        if offer is not None:
            shift_starts_at, shift_ends_at = resolve_offer_shift_window(
                offer,
                fallback_anchor=placement.outbound_payload_timestamp,
            )
        results.append(
            {
                "placement_id": placement.placement_id,
                "offer_id": placement.offer_id,
                "facility_name": placement.facility_name,
                "clinical_unit": placement.clinical_unit,
                "vms_submission_status": placement.vms_submission_status,
                "vms_external_ref": placement.vms_external_ref,
                "vms_submitted_at": placement.vms_submitted_at,
                "outbound_payload_timestamp": placement.outbound_payload_timestamp,
                "shift_starts_at": shift_starts_at,
                "shift_ends_at": shift_ends_at,
            }
        )
    return results


def list_clinician_activity(
    db: Session,
    provider_id: UUID,
    *,
    lockable_count: int = 0,
    limit: int = 40,
) -> list[dict]:
    placements = _list_activity_placements(db, provider_id)
    payments = list_clinician_payments(db, provider_id)
    payment_by_placement = {str(row["placement_id"]): row for row in payments}

    events: list[dict] = []
    has_paid = False
    seen_placement_ids: set[str] = set()

    for placement in placements:
        placement_id = str(placement["placement_id"])
        seen_placement_ids.add(placement_id)
        locked_at = (
            placement.get("outbound_payload_timestamp")
            or placement.get("shift_starts_at")
            or placement.get("vms_submitted_at")
        )
        facility = str(placement.get("facility_name") or "Facility")
        role = str(placement.get("clinical_unit") or "CNA")

        events.append(
            _event(
                event_id=f"{placement_id}:locked",
                event_type="SHIFT_LOCKED",
                label=ACTIVITY_LABELS["SHIFT_LOCKED"],
                detail=f"{facility} · {role}",
                occurred_at=locked_at,
            )
        )

        vms_status = str(placement.get("vms_submission_status") or "").upper()
        if vms_status in {"SUBMITTED", "ESCROW_LOCKED"}:
            events.append(
                _event(
                    event_id=f"{placement_id}:vms",
                    event_type="VMS_SUBMITTED",
                    label=ACTIVITY_LABELS["VMS_SUBMITTED"],
                    detail=facility,
                    reference=placement.get("vms_external_ref"),
                    occurred_at=placement.get("vms_submitted_at") or locked_at,
                )
            )

        payout = payment_by_placement.get(placement_id)
        if payout is not None:
            has_paid = _append_payment_events(
                events,
                placement_id=placement_id,
                facility=facility,
                payout=payout,
                fallback_at=locked_at,
                has_paid=has_paid,
            ) or has_paid

    for payment in payments:
        placement_id = str(payment["placement_id"])
        if placement_id in seen_placement_ids:
            continue
        facility = str(payment.get("facility_name") or "Shift payout")
        has_paid = _append_payment_events(
            events,
            placement_id=placement_id,
            facility=facility,
            payout=payment,
            fallback_at=payment.get("shift_starts_at") or payment.get("payout_eligible_at"),
            has_paid=has_paid,
        ) or has_paid

    if has_paid and lockable_count > 0:
        events.append(
            _event(
                event_id="demo:next-shift",
                event_type="NEXT_SHIFT_AVAILABLE",
                label=ACTIVITY_LABELS["NEXT_SHIFT_AVAILABLE"],
                detail="Open shifts tab — lock your next assignment",
                occurred_at=datetime.now(timezone.utc),
            )
        )

    events.sort(key=lambda row: row["occurred_at"] or datetime.min.replace(tzinfo=timezone.utc))
    if len(events) > limit:
        events = events[-limit:]
    return events


def _append_payment_events(
    events: list[dict],
    *,
    placement_id: str,
    facility: str,
    payout: dict,
    fallback_at: datetime | None,
    has_paid: bool,
) -> bool:
    payout_status = str(payout.get("payout_status") or "").upper()
    payroll_at = payout.get("payout_eligible_at") or payout.get("paid_at") or fallback_at

    if payout_status in {"SUBMITTED", "PROCESSING", "PAID"}:
        events.append(
            _event(
                event_id=f"{placement_id}:payroll",
                event_type="PAYROLL_SUBMITTED",
                label=ACTIVITY_LABELS["PAYROLL_SUBMITTED"],
                detail=facility,
                amount=float(payout.get("gross_pay_amount") or 0),
                occurred_at=payroll_at,
            )
        )

    if payout_status == "PAID":
        events.append(
            _event(
                event_id=f"{placement_id}:paid",
                event_type="INSTANT_PAYOUT_PAID",
                label=ACTIVITY_LABELS["INSTANT_PAYOUT_PAID"],
                detail=facility,
                amount=float(payout.get("gross_pay_amount") or 0),
                reference=payout.get("stripe_payout_id"),
                occurred_at=payout.get("paid_at") or payroll_at,
            )
        )
        return True
    return has_paid


def _event(
    *,
    event_id: str,
    event_type: str,
    label: str,
    detail: str | None = None,
    amount: float | None = None,
    reference: str | None = None,
    occurred_at: datetime | None,
    status: str = "done",
) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "label": label,
        "detail": detail,
        "amount": amount,
        "reference": reference,
        "occurred_at": occurred_at,
        "status": status,
    }
