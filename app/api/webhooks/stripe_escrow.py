"""Stripe escrow webhook — capture authorized funds after autonomous worker dispatch."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["stripe-escrow"])

_ESCROW_EVENT_TYPES = frozenset({"payment_intent.succeeded", "charge.captured"})
_ESCROW_LOCKED_STATUS = "ESCROW_LOCKED"


class StripeEscrowHardStop(RuntimeError):
    """Hive halt — stripe escrow webhook dependency or compile failure."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stripe_webhook_secret() -> str:
    try:
        from app.config import settings

        return str(getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or os.getenv("STRIPE_WEBHOOK_SECRET", "")).strip()
    except Exception as exc:  # noqa: BLE001
        raise StripeEscrowHardStop("settings_import_failed") from exc


def _lazy_session_local():
    try:
        from app.database import SessionLocal
    except Exception as exc:  # noqa: BLE001
        raise StripeEscrowHardStop("database_session_import_failed") from exc
    return SessionLocal


def _construct_stripe_event(payload: bytes, signature_header: str, secret: str) -> dict[str, Any]:
    try:
        import stripe
    except ImportError as exc:
        raise StripeEscrowHardStop("stripe_dependency_missing") from exc

    try:
        event = stripe.Webhook.construct_event(payload, signature_header, secret)
    except stripe.error.SignatureVerificationError as exc:
        raise ValueError("stripe_signature_invalid") from exc
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError("stripe_event_parse_failed") from exc

    if hasattr(event, "to_dict"):
        return event.to_dict()
    if isinstance(event, dict):
        return event
    raise ValueError("stripe_event_unexpected_shape")


def _event_timestamp(event: dict[str, Any]) -> datetime:
    created = event.get("created")
    if isinstance(created, (int, float)):
        return datetime.fromtimestamp(float(created), tz=timezone.utc)
    return _utc_now()


def _metadata_from_object(obj: dict[str, Any]) -> dict[str, str]:
    raw = obj.get("metadata") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}


def _extract_escrow_metadata(event: dict[str, Any]) -> tuple[str, str, str, datetime] | None:
    event_type = str(event.get("type") or "")
    obj = event.get("data", {}).get("object") or {}
    if not isinstance(obj, dict):
        return None

    metadata = _metadata_from_object(obj)
    if event_type == "charge.captured" and not metadata.get("timesheet_token"):
        payment_intent = obj.get("payment_intent")
        if isinstance(payment_intent, dict):
            metadata = _metadata_from_object(payment_intent) or metadata

    timesheet_token = str(metadata.get("timesheet_token") or "").strip()
    provider_id = str(metadata.get("provider_id") or "").strip()
    if not timesheet_token or not provider_id:
        return None

    event_id = str(event.get("id") or obj.get("id") or "").strip()
    return timesheet_token, provider_id, event_id, _event_timestamp(event)


def _settle_escrow_ledger(
    *,
    timesheet_token: str,
    provider_id: str,
    stripe_event_id: str,
    captured_at: datetime,
) -> None:
    """Atomically lock escrow on clinical_placements_ledger (idempotent)."""
    session_factory = _lazy_session_local()
    db = session_factory()
    try:
        from app.models import ClinicalPlacementLedger

        try:
            provider_uuid = UUID(str(provider_id))
        except ValueError:
            logger.warning("stripe escrow rejected — invalid provider_id=%s", provider_id)
            return

        row = (
            db.query(ClinicalPlacementLedger)
            .filter(ClinicalPlacementLedger.compliance_snapshot_token == timesheet_token)
            .with_for_update()
            .first()
        )
        if row is None:
            logger.warning(
                "stripe escrow skipped — timesheet_token not found token=%s event=%s",
                timesheet_token,
                stripe_event_id,
            )
            return

        if row.assigned_clinician_id != provider_uuid:
            logger.warning(
                "stripe escrow rejected — provider mismatch token=%s expected=%s got=%s",
                timesheet_token,
                row.assigned_clinician_id,
                provider_uuid,
            )
            return

        current_status = str(row.vms_submission_status or "").upper()
        if current_status == _ESCROW_LOCKED_STATUS:
            logger.info(
                "stripe escrow idempotent skip — already locked token=%s event=%s",
                timesheet_token,
                stripe_event_id,
            )
            return

        row.vms_submission_status = _ESCROW_LOCKED_STATUS
        row.vms_submitted_at = captured_at
        if stripe_event_id:
            row.vms_external_ref = stripe_event_id[:100]
        db.commit()
        logger.info(
            "stripe escrow locked token=%s provider=%s event=%s at=%s",
            timesheet_token,
            provider_uuid,
            stripe_event_id,
            captured_at.isoformat(),
        )
    except Exception:
        db.rollback()
        logger.exception(
            "stripe escrow settlement failed token=%s event=%s",
            timesheet_token,
            stripe_event_id,
        )
    finally:
        db.close()


@router.post("/stripe-escrow")
async def stripe_escrow_webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Verify Stripe signature, queue escrow ledger settlement, return 200 immediately."""
    payload = await request.body()
    signature_header = request.headers.get("Stripe-Signature") or ""
    secret = _stripe_webhook_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="stripe_webhook_secret_not_configured")
    if not signature_header:
        raise HTTPException(status_code=400, detail="stripe_signature_missing")

    try:
        event = _construct_stripe_event(payload, signature_header, secret)
    except ValueError as exc:
        detail = str(exc) or "stripe_signature_invalid"
        raise HTTPException(status_code=400, detail=detail) from exc

    event_type = str(event.get("type") or "")
    if event_type not in _ESCROW_EVENT_TYPES:
        return {"ok": True, "received": True, "ignored": event_type}

    parsed = _extract_escrow_metadata(event)
    if parsed is None:
        logger.warning("stripe escrow event missing metadata event_type=%s", event_type)
        return {"ok": True, "received": True, "ignored": "missing_metadata"}

    timesheet_token, provider_id, stripe_event_id, captured_at = parsed
    background_tasks.add_task(
        _settle_escrow_ledger,
        timesheet_token=timesheet_token,
        provider_id=provider_id,
        stripe_event_id=stripe_event_id,
        captured_at=captured_at,
    )
    return {"ok": True, "received": True, "queued": True}


def register_stripe_escrow_webhook(app) -> None:
    app.include_router(router)


if __name__ == "__main__":
    print("COMPILE_OK stripe_escrow_webhook")
