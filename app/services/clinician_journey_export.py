"""Export clinician journey summary for demo sign-off."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models import MarylandProvider
from app.services.clinician_activity import list_clinician_activity
from app.services.clinician_earnings import summarize_clinician_earnings
from app.services.clinician_journey_status import build_clinician_journey_status
from app.services.clinician_payments import list_clinician_payments
from app.services.shift_matching import count_portal_lockable_shifts
from app.services.vms_submission import list_clinician_placements
from sqlalchemy.orm import Session


def build_clinician_journey_export(db: Session, provider: MarylandProvider) -> dict:
    lockable = count_portal_lockable_shifts(db, provider, limit=50)
    status = build_clinician_journey_status(db, provider)
    earnings = summarize_clinician_earnings(db, provider.provider_id)
    placements = list_clinician_placements(db, provider.provider_id)
    payments = list_clinician_payments(db, provider.provider_id)
    activity = list_clinician_activity(db, provider.provider_id, lockable_count=lockable)

    lines = [
        "VettedMe.ai — Clinician Journey Export",
        "=" * 44,
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Clinician: {provider.full_name}",
        f"Email: {provider.email}",
        f"Phase: {status.get('phase_label')} ({status.get('phase')})",
        f"Next action: {status.get('next_action')}",
        "",
        "Earnings",
        f"  Lifetime paid: ${float(earnings.get('lifetime_paid_amount') or 0):,.2f}",
        f"  This week: ${float(earnings.get('week_paid_amount') or 0):,.2f}",
        f"  Pending payroll: ${float(earnings.get('pending_payroll_amount') or 0):,.2f}",
        f"  Shifts paid: {earnings.get('shifts_paid_count', 0)}",
        "",
        "Placements",
    ]
    if not placements:
        lines.append("  (none)")
    for row in placements:
        lines.append(
            f"  - {row.get('facility_name')} · {row.get('clinical_unit')} · "
            f"VMS {row.get('vms_submission_status')} · ref {row.get('vms_external_ref') or '—'}"
        )

    lines.extend(["", "Payments"])
    if not payments:
        lines.append("  (none)")
    for row in payments:
        lines.append(
            f"  - ${float(row.get('gross_pay_amount') or 0):,.2f} · "
            f"{row.get('payout_status')} · {row.get('stripe_payout_id') or '—'}"
        )

    lines.extend(["", "Activity timeline"])
    if not activity:
        lines.append("  (none)")
    for row in activity:
        ts = row.get("occurred_at")
        stamp = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "—")
        lines.append(f"  - [{stamp}] {row.get('label')} — {row.get('detail') or ''}")

    text = "\n".join(lines)
    token = str(provider.provider_id).replace("-", "")[:8].lower()
    return {
        "filename": f"vettedme-journey-{token}.txt",
        "export_text": text,
        "phase": status.get("phase"),
        "phase_label": status.get("phase_label"),
        "lockable_count": lockable,
        "paid_shifts_count": status.get("paid_shifts_count", 0),
        "lifetime_paid_amount": float(status.get("lifetime_paid_amount") or 0),
    }
