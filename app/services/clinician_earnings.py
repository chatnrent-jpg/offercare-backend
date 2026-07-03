"""Clinician earnings summary — paid / pending totals for the portal overview."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.clinician_payments import list_clinician_payments


def _week_start_utc(now: datetime) -> datetime:
    """Monday 00:00 UTC for the current ISO week."""
    anchor = now.astimezone(timezone.utc)
    return (anchor - timedelta(days=anchor.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def summarize_clinician_earnings(db: Session, provider_id: UUID) -> dict:
    payments = list_clinician_payments(db, provider_id)
    now = datetime.now(timezone.utc)
    week_start = _week_start_utc(now)

    lifetime_paid = 0.0
    week_paid = 0.0
    pending_payroll = 0.0
    shifts_paid = 0
    last_paid_at: datetime | None = None

    for row in payments:
        gross = float(row.get("gross_pay_amount") or 0)
        status = str(row.get("payout_status") or "").upper()
        paid_at = row.get("paid_at")

        if status == "PAID":
            lifetime_paid += gross
            shifts_paid += 1
            if paid_at is not None:
                paid_ts = paid_at if paid_at.tzinfo else paid_at.replace(tzinfo=timezone.utc)
                if paid_ts >= week_start:
                    week_paid += gross
                if last_paid_at is None or paid_ts > last_paid_at:
                    last_paid_at = paid_ts
        elif status in {"SUBMITTED", "PROCESSING"}:
            pending_payroll += gross

    return {
        "week_paid_amount": round(week_paid, 2),
        "lifetime_paid_amount": round(lifetime_paid, 2),
        "pending_payroll_amount": round(pending_payroll, 2),
        "shifts_paid_count": shifts_paid,
        "last_paid_at": last_paid_at,
        "currency": "USD",
    }
