"""Credential safety alerts — notify clinicians and admins when status changes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import CredentialSafetyAlert, MarylandProvider
from app.services.email_alerts import EmailResult, send_shift_email
from app.services.sms import SmsResult, send_shift_sms
from app.services.vetted_status import ALL_VETTED_STATUSES


def _brand_name() -> str:
    name = str(settings.PROJECT_NAME or "VettedCare.ai")
    if "vetted" in name.lower():
        return name.split("—")[0].split("-")[0].strip() or "VettedCare.ai"
    return "VettedCare.ai"


def build_clinician_safety_message(*, full_name: str, vetted_status: str, reason: str) -> str:
    first = (full_name or "Clinician").split()[0]
    brand = _brand_name()
    if vetted_status == "EXPIRING":
        return (
            f"{brand}: Hi {first}, a credential on file is expiring soon. "
            f"{reason} Please update documents in your portal to stay active. Reply HELP for help."
        )
    if vetted_status == "BLOCKED":
        return (
            f"{brand}: Hi {first}, your profile requires immediate attention before patient care placement. "
            f"{reason} Contact compliance or update your portal. Reply HELP for help."
        )
    if vetted_status == "ACTION_NEEDED":
        return (
            f"{brand}: Hi {first}, action is required on your credential file. "
            f"{reason} Please complete verification in your portal."
        )
    return (
        f"{brand}: Hi {first}, your credential profile is CLEAR and active. "
        f"No action needed at this time."
    )


def build_admin_safety_email(*, provider: MarylandProvider, vetted_status: str, reason: str) -> tuple[str, str]:
    brand = _brand_name()
    subject = f"{brand} safety alert · {provider.full_name} · {vetted_status}"
    body = (
        f"Credential safety alert\n\n"
        f"Clinician: {provider.full_name}\n"
        f"Status: {vetted_status}\n"
        f"License: {provider.license_status}\n"
        f"Dispatch: {provider.dispatch_status}\n"
        f"NPI: {provider.npi_number}\n\n"
        f"Reason: {reason}\n\n"
        f"Review in admin: /admin\n"
        f"— {brand}"
    )
    return subject, body


def _record_alert(
    db: Session,
    *,
    provider_id: UUID,
    channel: str,
    alert_type: str,
    vetted_status: str,
    message_body: str,
    result_status: str,
) -> CredentialSafetyAlert:
    row = CredentialSafetyAlert(
        provider_id=provider_id,
        channel=channel,
        alert_type=alert_type,
        vetted_status=vetted_status,
        message_body=message_body[:1000],
        delivery_status=result_status,
    )
    db.add(row)
    return row


def notify_status_change(
    db: Session,
    provider: MarylandProvider,
    *,
    previous_status: str | None,
    new_status: str,
    reason: str,
    alert_type: str = "STATUS_CHANGE",
) -> dict:
    if new_status not in ALL_VETTED_STATUSES:
        raise ValueError("invalid_vetted_status")

    if not settings.VETTED_ALERTS_ENABLED:
        return {"skipped": True, "reason": "vetted_alerts_disabled"}

    # Only alert on meaningful transitions (not initial CLEAR sync)
    if previous_status == new_status:
        return {"skipped": True, "reason": "no_change"}

    clinician_message = build_clinician_safety_message(
        full_name=provider.full_name,
        vetted_status=new_status,
        reason=reason,
    )

    sms_result: SmsResult | None = None
    if str(provider.sms_opt_out or "false").lower() != "true":
        sms_result = send_shift_sms(to_number=provider.phone_number, message_body=clinician_message)
        _record_alert(
            db,
            provider_id=provider.provider_id,
            channel="SMS",
            alert_type=alert_type,
            vetted_status=new_status,
            message_body=clinician_message,
            result_status=sms_result.status,
        )

    email_results: list[dict] = []
    admin_email = str(settings.VETTED_ADMIN_ALERT_EMAIL or "").strip()
    targets = [provider.email]
    if admin_email and admin_email.lower() != provider.email.lower():
        targets.append(admin_email)

    subject, body = build_admin_safety_email(provider=provider, vetted_status=new_status, reason=reason)
    for address in targets:
        email_result: EmailResult = send_shift_email(
            to_address=address,
            subject=subject,
            message_body=body,
        )
        email_results.append({"to": address, "status": email_result.status})
        _record_alert(
            db,
            provider_id=provider.provider_id,
            channel="EMAIL",
            alert_type=alert_type,
            vetted_status=new_status,
            message_body=body[:1000],
            result_status=email_result.status,
        )

    db.commit()
    return {
        "provider_id": str(provider.provider_id),
        "previous_status": previous_status,
        "new_status": new_status,
        "sms_status": sms_result.status if sms_result else "SKIPPED",
        "email_results": email_results,
    }


def list_recent_alerts(db: Session, *, limit: int = 50) -> list[dict]:
    rows = (
        db.query(CredentialSafetyAlert)
        .order_by(CredentialSafetyAlert.sent_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return [
        {
            "alert_id": str(row.alert_id),
            "provider_id": str(row.provider_id),
            "channel": row.channel,
            "alert_type": row.alert_type,
            "vetted_status": row.vetted_status,
            "delivery_status": row.delivery_status,
            "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        }
        for row in rows
    ]
