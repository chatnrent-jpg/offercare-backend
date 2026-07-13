"""Instant pay receipt — downloadable pay stub for completed clinician payouts."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import MarylandProvider
from app.services.clinician_payments import list_clinician_payments, payment_status_label


def _fmt_ts(value: datetime | None) -> str:
    if value is None:
        return "—"
    ts = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _build_receipt_text(provider: MarylandProvider, payment: dict) -> str:
    lines = [
        "VettedMe.ai — Instant Pay Receipt",
        "=" * 42,
        f"Receipt ID: VC-PAY-{str(payment['payout_id']).replace('-', '')[:8].upper()}",
        f"Clinician: {provider.full_name}",
        f"Email: {provider.email}",
        "",
        f"Facility: {payment.get('facility_name') or 'Shift payout'}",
        f"Role: {payment.get('shift_role') or '—'}",
        f"Shift start: {_fmt_ts(payment.get('shift_starts_at'))}",
        f"Shift end: {_fmt_ts(payment.get('shift_ends_at'))}",
        "",
        f"Gross pay: ${float(payment.get('gross_pay_amount') or 0):,.2f}",
        f"Status: {payment.get('payout_status_label') or payment_status_label(payment.get('payout_status'))}",
        f"Paid at: {_fmt_ts(payment.get('paid_at'))}",
        f"Stripe ref: {payment.get('stripe_payout_id') or '—'}",
        "",
        "This is a demo dry-run receipt for walkthrough purposes.",
        "Funds were not transferred to a live bank account.",
    ]
    return "\n".join(lines)


def get_clinician_payment_receipt(
    db: Session,
    provider_id: UUID,
    payout_id: UUID,
) -> dict | None:
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.provider_id == provider_id)
        .first()
    )
    if provider is None:
        return None

    payment = next(
        (
            row
            for row in list_clinician_payments(db, provider_id)
            if str(row["payout_id"]) == str(payout_id)
        ),
        None,
    )
    if payment is None:
        return None

    if str(payment.get("payout_status") or "").upper() != "PAID":
        return None

    token = str(payment["payout_id"]).replace("-", "")[:8].upper()
    receipt_id = f"VC-PAY-{token}"
    receipt_text = _build_receipt_text(provider, payment)
    return {
        "receipt_id": receipt_id,
        "payout_id": payment["payout_id"],
        "placement_id": payment["placement_id"],
        "clinician_name": provider.full_name,
        "clinician_email": str(provider.email),
        "facility_name": payment.get("facility_name") or "Shift payout",
        "shift_role": payment.get("shift_role"),
        "gross_pay_amount": float(payment.get("gross_pay_amount") or 0),
        "paid_at": payment.get("paid_at"),
        "stripe_payout_id": payment.get("stripe_payout_id"),
        "payout_status": payment.get("payout_status"),
        "receipt_filename": f"vettedme-receipt-{token.lower()}.txt",
        "receipt_text": receipt_text,
    }
