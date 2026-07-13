"""Clinician alert inbox — SMS, push, and portal notifications for the shift journey."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ShiftNotificationLog
from app.services.clinician_activity import _list_activity_placements, list_clinician_activity

ALERT_CHANNELS = {
    "SHIFT_MATCH": "SMS",
    "SHIFT_LOCKED": "PORTAL",
    "VMS_SUBMITTED": "SMS",
    "PAYROLL_SUBMITTED": "PORTAL",
    "INSTANT_PAYOUT_PAID": "PUSH",
    "NEXT_SHIFT_AVAILABLE": "PUSH",
}

ALERT_TITLES = {
    "SHIFT_MATCH": "Matched shift alert",
    "SHIFT_LOCKED": "Shift locked",
    "VMS_SUBMITTED": "Facility confirmed",
    "PAYROLL_SUBMITTED": "Payroll submitted",
    "INSTANT_PAYOUT_PAID": "Instant pay deposited",
    "NEXT_SHIFT_AVAILABLE": "Next shift ready",
}


def list_clinician_alerts(
    db: Session,
    provider_id: UUID,
    *,
    lockable_count: int = 0,
    limit: int = 30,
) -> list[dict]:
    alerts: list[dict] = []
    seen_ids: set[str] = set()

    log_rows = (
        db.query(ShiftNotificationLog)
        .filter(ShiftNotificationLog.provider_id == provider_id)
        .order_by(ShiftNotificationLog.sent_at.desc())
        .limit(limit)
        .all()
    )
    for row in log_rows:
        alert_id = str(row.notification_id)
        seen_ids.add(alert_id)
        alerts.append(
            {
                "alert_id": alert_id,
                "alert_type": "SHIFT_MATCH",
                "channel": str(row.channel or "SMS").upper(),
                "title": ALERT_TITLES["SHIFT_MATCH"],
                "body": row.message_body,
                "reference": str(row.offer_id),
                "amount": None,
                "sent_at": row.sent_at,
                "status": str(row.status or "DELIVERED").upper(),
            }
        )

    placements = _list_activity_placements(db, provider_id)
    if placements and not any(a["alert_type"] == "SHIFT_MATCH" for a in alerts):
        placement = placements[0]
        facility = str(placement.get("facility_name") or "Facility")
        role = str(placement.get("clinical_unit") or "CNA")
        rate = float(placement.get("hourly_bill_rate") or 0)
        match_id = f"{placement['placement_id']}:match"
        if match_id not in seen_ids:
            seen_ids.add(match_id)
            alerts.append(
                {
                    "alert_id": match_id,
                    "alert_type": "SHIFT_MATCH",
                    "channel": "SMS",
                    "title": ALERT_TITLES["SHIFT_MATCH"],
                    "body": (
                        f"VettedMe: {role} at {facility}"
                        f"{f' · ${rate:.2f}/hr' if rate else ''} — reply YES or lock in portal."
                    ),
                    "reference": str(placement.get("offer_id")),
                    "amount": None,
                    "sent_at": placement.get("outbound_payload_timestamp"),
                    "status": "DELIVERED",
                }
            )

    for event in list_clinician_activity(db, provider_id, lockable_count=lockable_count):
        event_type = str(event.get("event_type") or "")
        alert_id = f"alert:{event.get('event_id')}"
        if alert_id in seen_ids:
            continue
        seen_ids.add(alert_id)
        alerts.append(
            {
                "alert_id": alert_id,
                "alert_type": event_type,
                "channel": ALERT_CHANNELS.get(event_type, "PORTAL"),
                "title": event.get("label") or ALERT_TITLES.get(event_type, event_type),
                "body": event.get("detail"),
                "reference": event.get("reference"),
                "amount": event.get("amount"),
                "sent_at": event.get("occurred_at"),
                "status": "DELIVERED",
            }
        )

    alerts.sort(
        key=lambda row: row.get("sent_at") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return alerts[:limit]


def ensure_demo_portal_alerts(db: Session, provider) -> int:
    """Backfill one SMS matched-shift log row for demo inbox when empty."""
    if not is_demo_walkthrough_provider(provider):
        return 0

    existing = (
        db.query(ShiftNotificationLog)
        .filter(ShiftNotificationLog.provider_id == provider.provider_id)
        .count()
    )
    if existing:
        return 0

    placements = _list_activity_placements(db, provider.provider_id)
    if not placements:
        return 0

    placement = placements[0]
    offer_id = placement.get("offer_id")
    if offer_id is None:
        return 0
    facility = str(placement.get("facility_name") or "Facility")
    role = str(placement.get("clinical_unit") or "CNA")
    rate = float(placement.get("hourly_bill_rate") or 0)
    db.add(
        ShiftNotificationLog(
            offer_id=placement["offer_id"],
            provider_id=provider.provider_id,
            channel="SMS",
            status="DELIVERED",
            message_body=(
                f"VettedMe: {role} at {facility}"
                f"{f' · ${rate:.2f}/hr' if rate else ''} — reply YES to lock."
            ),
        )
    )
    db.commit()
    return 1
