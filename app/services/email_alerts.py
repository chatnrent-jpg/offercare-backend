"""Shift alert email delivery with SMTP and dry-run fallback."""

from __future__ import annotations

import smtplib
import uuid
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import settings


@dataclass(frozen=True)
class EmailResult:
    status: str
    mode: str
    subject: str
    message_body: str
    message_id: str | None = None
    error: str | None = None


def build_shift_alert_email(
    *,
    facility_name: str,
    shift_role: str,
    hourly_pay_rate: float,
    reply_keyword: str = "YES",
    clinician_name: str | None = None,
    schedule_line: str = "",
) -> tuple[str, str]:
    greeting = f"Hi {clinician_name}," if clinician_name else "Hi,"
    subject = f"VettedMe.ai shift · {facility_name} · {shift_role}"
    body = (
        f"{greeting}\n\n"
        f"Urgent shift available:\n"
        f"  Facility: {facility_name}\n"
        f"  Role: {shift_role}\n"
        f"  Pay: ${hourly_pay_rate:.2f}/hr"
        f"{schedule_line}\n\n"
        f"Reply {reply_keyword} by SMS to your registered phone to lock this shift.\n\n"
        f"— VettedMe.ai Grid"
    )
    return subject, body


def send_shift_email(*, to_address: str, subject: str, message_body: str) -> EmailResult:
    if not settings.EMAIL_ALERTS_ENABLED:
        return EmailResult(
            status="SKIPPED",
            mode="disabled",
            subject=subject,
            message_body=message_body,
        )

    if settings.EMAIL_DRY_RUN:
        return EmailResult(
            status="DRY_RUN",
            mode="dry_run",
            subject=subject,
            message_body=message_body,
            message_id=f"dryrun-{uuid.uuid4().hex[:12]}",
        )

    if not settings.email_configured:
        return EmailResult(
            status="FAILED",
            mode="misconfigured",
            subject=subject,
            message_body=message_body,
            error="SMTP settings missing while EMAIL_DRY_RUN=false",
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_address
    message.set_content(message_body)

    try:
        if settings.SMTP_USE_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        return EmailResult(
            status="SENT",
            mode="smtp",
            subject=subject,
            message_body=message_body,
            message_id=message.get("Message-ID"),
        )
    except Exception as exc:  # noqa: BLE001
        return EmailResult(
            status="FAILED",
            mode="smtp_error",
            subject=subject,
            message_body=message_body,
            error=str(exc),
        )
