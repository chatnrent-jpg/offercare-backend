"""Live Twilio + VMS integration status and smoke tests."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class ChannelStatus:
    name: str
    configured: bool
    dry_run: bool
    live_ready: bool
    detail: str


def twilio_inbound_webhook_url() -> str | None:
    base = str(settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/shift-sniper/twilio/sms"


def get_twilio_status() -> ChannelStatus:
    configured = settings.twilio_configured
    dry_run = settings.SMS_DRY_RUN
    if dry_run:
        detail = "SMS dry-run enabled — messages are not sent."
    elif not configured:
        detail = "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER and SMS_DRY_RUN=false."
    else:
        detail = "Live Twilio SMS enabled."
    webhook = twilio_inbound_webhook_url()
    if webhook and configured and not dry_run:
        detail = f"{detail} Inbound webhook: {webhook}"
    return ChannelStatus(
        name="twilio",
        configured=configured,
        dry_run=dry_run,
        live_ready=configured and not dry_run,
        detail=detail,
    )


def get_vms_status() -> ChannelStatus:
    configured = bool(str(settings.VMS_SUBMISSION_URL or "").strip())
    dry_run = settings.VMS_DRY_RUN
    if dry_run:
        detail = "VMS dry-run enabled — submissions return DRYRUN references."
    elif not configured:
        detail = "Set VMS_SUBMISSION_URL and VMS_DRY_RUN=false for live submissions."
    else:
        detail = f"Live VMS enabled → {settings.VMS_SUBMISSION_URL}"
    return ChannelStatus(
        name="vms",
        configured=configured,
        dry_run=dry_run,
        live_ready=configured and not dry_run,
        detail=detail,
    )


def get_email_status() -> ChannelStatus:
    if not settings.EMAIL_ALERTS_ENABLED:
        return ChannelStatus(
            name="email",
            configured=False,
            dry_run=True,
            live_ready=False,
            detail="Email alerts disabled (EMAIL_ALERTS_ENABLED=false).",
        )
    configured = settings.email_configured
    dry_run = settings.EMAIL_DRY_RUN
    if dry_run:
        detail = "Email dry-run enabled — messages are logged, not sent."
    elif not configured:
        detail = "Set SMTP_HOST, EMAIL_FROM and EMAIL_DRY_RUN=false for live email."
    else:
        detail = f"Live SMTP email enabled via {settings.SMTP_HOST}."
    return ChannelStatus(
        name="email",
        configured=configured,
        dry_run=dry_run,
        live_ready=configured and not dry_run,
        detail=detail,
    )


def get_push_status() -> ChannelStatus:
    from app.services.push_alerts import effective_vapid_public_key

    if not settings.PUSH_ALERTS_ENABLED:
        return ChannelStatus(
            name="push",
            configured=False,
            dry_run=True,
            live_ready=False,
            detail="Push alerts disabled (PUSH_ALERTS_ENABLED=false).",
        )
    configured = settings.push_configured
    dry_run = settings.PUSH_DRY_RUN
    public_key = effective_vapid_public_key()
    if dry_run:
        detail = "Push dry-run enabled — alerts are logged, not delivered to devices."
    elif not configured:
        detail = "Set VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY and PUSH_DRY_RUN=false for live push."
    else:
        detail = "Live Web Push enabled via VAPID."
    if public_key and dry_run:
        detail = f"{detail} Dev public key available for portal subscriptions."
    return ChannelStatus(
        name="push",
        configured=configured or bool(public_key),
        dry_run=dry_run,
        live_ready=configured and not dry_run,
        detail=detail,
    )


def integration_snapshot() -> dict:
    twilio = get_twilio_status()
    email = get_email_status()
    push = get_push_status()
    vms = get_vms_status()
    from app.services.push_alerts import effective_vapid_public_key

    return {
        "twilio": {
            "configured": twilio.configured,
            "dry_run": twilio.dry_run,
            "live_ready": twilio.live_ready,
            "signature_validation": settings.TWILIO_VALIDATE_SIGNATURES,
            "inbound_webhook_url": twilio_inbound_webhook_url(),
            "detail": twilio.detail,
        },
        "email": {
            "configured": email.configured,
            "dry_run": email.dry_run,
            "live_ready": email.live_ready,
            "from_address": settings.EMAIL_FROM or None,
            "smtp_host": settings.SMTP_HOST or None,
            "detail": email.detail,
        },
        "push": {
            "configured": push.configured,
            "dry_run": push.dry_run,
            "live_ready": push.live_ready,
            "vapid_public_key": effective_vapid_public_key(),
            "detail": push.detail,
        },
        "vms": {
            "configured": vms.configured,
            "dry_run": vms.dry_run,
            "live_ready": vms.live_ready,
            "submission_url": settings.VMS_SUBMISSION_URL or None,
            "detail": vms.detail,
        },
    }
