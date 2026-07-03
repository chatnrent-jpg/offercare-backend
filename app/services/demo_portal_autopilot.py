"""Demo portal autopilot — one-click VMS → payroll → instant pay → replenish."""

from __future__ import annotations

from app.models import MarylandProvider
from app.services.clinician_payments import (
    complete_demo_portal_payouts,
    ensure_demo_portal_payments,
)
from app.services.demo_portal_lockable import (
    ensure_demo_replenish_after_payout,
    repair_demo_portal_placements,
)
from app.services.shift_matching import count_portal_lockable_shifts, is_demo_walkthrough_provider
from app.services.vms_submission import submit_demo_clinician_placements_to_vms
from sqlalchemy.orm import Session


def run_demo_portal_autopilot(db: Session, provider: MarylandProvider) -> dict:
    if not is_demo_walkthrough_provider(provider):
        return {"ok": False, "reason": "demo_only"}

    repaired = repair_demo_portal_placements(db, provider)
    vms_dispatched = submit_demo_clinician_placements_to_vms(db, provider)
    payments_created = ensure_demo_portal_payments(db, provider)
    payouts_completed = complete_demo_portal_payouts(db, provider)
    shifts_replenished = ensure_demo_replenish_after_payout(db, provider)
    lockable_count = count_portal_lockable_shifts(db, provider, limit=50)

    return {
        "ok": True,
        "repaired_placements": repaired,
        "vms_dispatched": vms_dispatched,
        "payments_created": payments_created,
        "payouts_completed": payouts_completed,
        "shifts_replenished": shifts_replenished,
        "lockable_count": lockable_count,
        "message": "Demo autopilot complete — VMS, payroll, instant pay, and next shift ready.",
    }
