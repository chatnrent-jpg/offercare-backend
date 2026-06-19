"""Twilio live SMS production runbook — outbound alerts + inbound YES lock (step 135)."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.config import settings
from app.services.integrations import get_twilio_status, twilio_inbound_webhook_url

TWILIO_SMS_PRODUCTION_RUNBOOK_JSON_FILENAME = "offercare-twilio-sms-production-runbook.json"


def _public_base() -> str:
    return str(settings.PUBLIC_BASE_URL or "").strip().rstrip("/")


def build_twilio_sms_production_runbook(db: Session) -> dict:
    del db  # reserved for future DB-backed smoke history
    twilio = get_twilio_status()
    public_base = _public_base()
    webhook_url = twilio_inbound_webhook_url()
    https_ok = public_base.startswith("https://")
    signatures_ok = settings.TWILIO_VALIDATE_SIGNATURES

    checks: list[dict] = []

    if twilio.configured:
        cred_status = "ready"
        cred_detail = "TWILIO_ACCOUNT_SID, auth token, and from number configured"
        cred_action = None
    else:
        cred_status = "blocked"
        cred_detail = "Twilio credentials missing"
        cred_action = "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER"
    checks.append(
        {
            "id": "twilio_credentials",
            "title": "Twilio credentials",
            "status": cred_status,
            "detail": cred_detail,
            "action": cred_action,
        }
    )

    if not settings.SMS_DRY_RUN:
        sms_status = "ready"
        sms_detail = "SMS_DRY_RUN=false — outbound SMS enabled"
        sms_action = None
    else:
        sms_status = "blocked"
        sms_detail = "SMS still in dry-run — clinicians will not receive real texts"
        sms_action = "Set SMS_DRY_RUN=false when ready to send live shift alerts"
    checks.append(
        {
            "id": "sms_live_mode",
            "title": "Live SMS mode",
            "status": sms_status,
            "detail": sms_detail,
            "action": sms_action,
        }
    )

    checks.append(
        {
            "id": "public_https",
            "title": "Public HTTPS base URL",
            "status": "ready" if https_ok else "blocked",
            "detail": f"PUBLIC_BASE_URL={public_base or '(not set)'}",
            "action": None if https_ok else "Set PUBLIC_BASE_URL=https://your-domain.com",
        }
    )

    if webhook_url and https_ok:
        webhook_status = "ready"
        webhook_detail = f"Inbound webhook → {webhook_url}"
        webhook_action = None
    elif webhook_url:
        webhook_status = "warning"
        webhook_detail = f"Webhook URL generated but PUBLIC_BASE_URL is not HTTPS: {webhook_url}"
        webhook_action = "Use HTTPS PUBLIC_BASE_URL before wiring Twilio Console"
    else:
        webhook_status = "blocked"
        webhook_detail = "Set PUBLIC_BASE_URL to generate inbound webhook URL"
        webhook_action = "Set PUBLIC_BASE_URL=https://your-domain.com"
    checks.append(
        {
            "id": "twilio_inbound_webhook",
            "title": "Twilio inbound webhook",
            "status": webhook_status,
            "detail": webhook_detail,
            "action": webhook_action,
        }
    )

    if signatures_ok:
        sig_status = "ready"
        sig_detail = "TWILIO_VALIDATE_SIGNATURES=true — inbound webhook verified"
        sig_action = None
    elif twilio.live_ready:
        sig_status = "warning"
        sig_detail = "Signature validation off — enable before public Twilio webhook"
        sig_action = "Set TWILIO_VALIDATE_SIGNATURES=true in production .env"
    else:
        sig_status = "pending"
        sig_detail = "TWILIO_VALIDATE_SIGNATURES=false (acceptable for local dev)"
        sig_action = "Set TWILIO_VALIDATE_SIGNATURES=true before production launch"
    checks.append(
        {
            "id": "twilio_signatures",
            "title": "Twilio signature validation",
            "status": sig_status,
            "detail": sig_detail,
            "action": sig_action,
        }
    )

    reply_keyword = str(settings.TWILIO_REPLY_KEYWORD or "YES").strip().upper()
    checks.append(
        {
            "id": "lock_reply_keyword",
            "title": "SMS lock reply keyword",
            "status": "ready",
            "detail": f"Clinicians reply {reply_keyword} to lock a matched shift",
            "action": None,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")
    production_ready = (
        blocked == 0
        and warnings == 0
        and twilio.live_ready
        and https_ok
        and bool(webhook_url)
        and signatures_ok
    )

    env_lines = [
        "# Twilio live SMS production (OfferCare step 135)",
        "SMS_DRY_RUN=false",
        f"TWILIO_ACCOUNT_SID={settings.TWILIO_ACCOUNT_SID or '<your-account-sid>'}",
        "TWILIO_AUTH_TOKEN=<your-auth-token>",
        f"TWILIO_FROM_NUMBER={settings.TWILIO_FROM_NUMBER or '+1XXXXXXXXXX'}",
        f"PUBLIC_BASE_URL={public_base or 'https://api.yourdomain.com'}",
        "TWILIO_VALIDATE_SIGNATURES=true",
        f"TWILIO_REPLY_KEYWORD={reply_keyword}",
    ]

    steps = [
        "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, and SMS_DRY_RUN=false",
        f"Set PUBLIC_BASE_URL to your public HTTPS API base (no trailing slash)",
        f"Twilio Console → Phone Numbers → your OfferCare number → Messaging → A MESSAGE COMES IN",
        f"Paste webhook URL: {webhook_url or '<PUBLIC_BASE_URL>/shift-sniper/twilio/sms'} (HTTP POST)",
        "Set TWILIO_VALIDATE_SIGNATURES=true before exposing the webhook publicly",
        "Admin → Integrations → Test SMS to verify outbound delivery",
        "Admin → Integrations → Run lock reply smoke to verify YES reply locks a broadcasting shift",
        "Notify matched on a demo or live shift, then text YES from the clinician handset to confirm end-to-end",
        "Deploy checklist live_sms_ready should flip to READY when credentials, HTTPS, and webhook are green",
    ]

    return {
        "production_ready": production_ready,
        "live_sms_ready": twilio.live_ready and https_ok and bool(webhook_url),
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "twilio_live_ready": twilio.live_ready,
            "inbound_webhook_url": webhook_url,
            "signature_validation": signatures_ok,
            "reply_keyword": reply_keyword,
        },
        "checks": checks,
        "steps": steps,
        "env_snippet": "\n".join(env_lines),
        "twilio_console_steps": [
            "Twilio Console → Phone Numbers → Manage → Active numbers → select your OfferCare number",
            "Messaging configuration → A MESSAGE COMES IN → Webhook",
            f"URL: {webhook_url or '<PUBLIC_BASE_URL>/shift-sniper/twilio/sms'}",
            "HTTP method: POST",
            "Save — clinicians can reply YES to lock shifts",
        ],
    }


def build_twilio_sms_production_runbook_json(db: Session) -> dict:
    snapshot = build_twilio_sms_production_runbook(db)
    return {
        "filename": TWILIO_SMS_PRODUCTION_RUNBOOK_JSON_FILENAME,
        "content": json.dumps(snapshot, indent=2),
    }
