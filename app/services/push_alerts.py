"""Shift alert Web Push delivery with VAPID and dry-run fallback."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from app.config import settings

# Dev-only public key for portal subscription when VAPID_PUBLIC_KEY is unset.
DEV_VAPID_PUBLIC_KEY = (
    "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrnZgGgSnrjUThz_jBVehPu5y0rFL17qkhX-R-Zg"
)


@dataclass(frozen=True)
class PushResult:
    status: str
    mode: str
    title: str
    message_body: str
    receipt_id: str | None = None
    error: str | None = None


def effective_vapid_public_key() -> str | None:
    configured = str(settings.VAPID_PUBLIC_KEY or "").strip()
    if configured:
        return configured
    if settings.PUSH_DRY_RUN:
        return DEV_VAPID_PUBLIC_KEY
    return None


def build_shift_alert_push(
    *,
    facility_name: str,
    shift_role: str,
    hourly_pay_rate: float,
    reply_keyword: str = "YES",
    schedule_line: str = "",
) -> tuple[str, str]:
    title = f"OfferCare shift · {facility_name}"
    body = (
        f"{shift_role} · ${hourly_pay_rate:.2f}/hr"
        f"{schedule_line}. Open /portal to lock or reply {reply_keyword} by SMS."
    )
    return title, body


def build_matched_shift_alert_push(
    *,
    facility_name: str,
    shift_role: str,
    hourly_pay_rate: float,
    schedule_line: str = "",
) -> tuple[str, str]:
    title = f"Matched shift · {facility_name}"
    body = (
        f"{shift_role} · ${hourly_pay_rate:.2f}/hr"
        f"{schedule_line}. Open /portal to lock this shift."
    )
    return title, body


def send_shift_push(
    *,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
    title: str,
    message_body: str,
    data: dict | None = None,
) -> PushResult:
    if not settings.PUSH_ALERTS_ENABLED:
        return PushResult(
            status="SKIPPED",
            mode="disabled",
            title=title,
            message_body=message_body,
        )

    if settings.PUSH_DRY_RUN:
        return PushResult(
            status="DRY_RUN",
            mode="dry_run",
            title=title,
            message_body=message_body,
            receipt_id=f"dryrun-{uuid.uuid4().hex[:12]}",
        )

    if not settings.push_configured:
        return PushResult(
            status="FAILED",
            mode="misconfigured",
            title=title,
            message_body=message_body,
            error="VAPID keys missing while PUSH_DRY_RUN=false",
        )

    payload = json.dumps(
        {
            "title": title,
            "body": message_body,
            **(data or {}),
        }
    )
    try:
        from pywebpush import WebPushException, webpush

        response = webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {"p256dh": p256dh_key, "auth": auth_key},
            },
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
        )
        receipt_id = None
        if response is not None and getattr(response, "headers", None):
            receipt_id = response.headers.get("location")
        return PushResult(
            status="SENT",
            mode="webpush",
            title=title,
            message_body=message_body,
            receipt_id=receipt_id,
        )
    except WebPushException as exc:
        return PushResult(
            status="FAILED",
            mode="webpush_error",
            title=title,
            message_body=message_body,
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        return PushResult(
            status="FAILED",
            mode="webpush_error",
            title=title,
            message_body=message_body,
            error=str(exc),
        )
