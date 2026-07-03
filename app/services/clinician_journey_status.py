"""Clinician journey status — repeat loop / next shift desk for the portal."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import MarylandProvider
from app.services.clinician_activity import _list_activity_placements
from app.services.clinician_earnings import summarize_clinician_earnings
from app.services.clinician_payments import list_clinician_payments
from app.services.shift_matching import count_portal_lockable_shifts, list_open_shifts_for_clinician

PHASE_LABELS = {
    "GET_STARTED": "Get started",
    "IN_PROGRESS": "Journey in progress",
    "AWAITING_PAYOUT": "Awaiting instant pay",
    "JOURNEY_COMPLETE": "Journey complete",
    "READY_FOR_NEXT_SHIFT": "Ready for next shift",
}


def build_clinician_journey_status(db: Session, provider: MarylandProvider) -> dict:
    payments = list_clinician_payments(db, provider.provider_id)
    paid_count = sum(1 for row in payments if str(row.get("payout_status") or "").upper() == "PAID")
    submitted_count = sum(
        1
        for row in payments
        if str(row.get("payout_status") or "").upper() in {"SUBMITTED", "PROCESSING"}
    )
    placements = _list_activity_placements(db, provider.provider_id)
    lockable_count = count_portal_lockable_shifts(db, provider, limit=50)
    earnings = summarize_clinician_earnings(db, provider.provider_id)

    next_shift: dict | None = None
    lockable_rows = list_open_shifts_for_clinician(
        db,
        provider,
        limit=1,
        lockable_only=True,
    )
    if lockable_rows:
        row = lockable_rows[0]
        next_shift = {
            "offer_id": row["offer_id"],
            "facility_name": row.get("facility_name"),
            "shift_role": row.get("shift_role"),
            "hourly_pay_rate": float(row.get("hourly_pay_rate") or 0),
            "shift_starts_at": row.get("shift_starts_at"),
            "shift_ends_at": row.get("shift_ends_at"),
        }

    if paid_count > 0 and lockable_count > 0:
        phase = "READY_FOR_NEXT_SHIFT"
        next_action = "Lock your next shift to run the journey again"
    elif paid_count > 0:
        phase = "JOURNEY_COMPLETE"
        next_action = "Instant pay complete — next shift loading"
    elif submitted_count > 0:
        phase = "AWAITING_PAYOUT"
        next_action = "Instant pay processing"
    elif placements:
        phase = "IN_PROGRESS"
        next_action = "Complete dispatch and payroll"
    else:
        phase = "GET_STARTED"
        next_action = "Lock a matched shift to begin"

    return {
        "phase": phase,
        "phase_label": PHASE_LABELS.get(phase, phase.replace("_", " ").title()),
        "next_action": next_action,
        "lockable_count": lockable_count,
        "paid_shifts_count": paid_count,
        "lifetime_paid_amount": float(earnings.get("lifetime_paid_amount") or 0),
        "can_repeat_journey": paid_count > 0 and lockable_count > 0,
        "next_lockable_shift": next_shift,
    }
