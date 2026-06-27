"""Twilio SMS delivery with dry-run fallback for local dev."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class SmsResult:
    status: str
    mode: str
    message_body: str
    twilio_sid: str | None = None
    error: str | None = None


def build_shift_alert_message(
    *,
    facility_name: str,
    shift_role: str,
    hourly_pay_rate: float,
    reply_keyword: str = "YES",
    shift_starts_at=None,
    shift_ends_at=None,
) -> str:
    from app.services.shift_schedule import format_shift_window_et

    when = ""
    if shift_starts_at is not None and shift_ends_at is not None:
        when = f" · {format_shift_window_et(shift_starts_at, shift_ends_at)}"
    return (
        f"VettedCare.ai · {facility_name} · {shift_role} · ${hourly_pay_rate:.2f}/hr{when}. "
        f"Reply {reply_keyword} to lock this shift. Reply STOP to opt out, HELP for help."
    )


def send_shift_sms(*, to_number: str, message_body: str) -> SmsResult:
    if settings.SMS_DRY_RUN:
        return SmsResult(
            status="DRY_RUN",
            mode="dry_run",
            message_body=message_body,
            twilio_sid=None,
        )

    if not settings.twilio_configured:
        return SmsResult(
            status="FAILED",
            mode="misconfigured",
            message_body=message_body,
            error="Twilio credentials missing while SMS_DRY_RUN=false",
        )

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_FROM_NUMBER,
            to=to_number,
        )
        return SmsResult(
            status="SENT",
            mode="twilio",
            message_body=message_body,
            twilio_sid=message.sid,
        )
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        if "TwilioException" in type(exc).__name__:
            error = str(exc)
        return SmsResult(
            status="FAILED",
            mode="twilio_error",
            message_body=message_body,
            error=error,
        )
