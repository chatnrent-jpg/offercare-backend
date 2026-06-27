"""External agentic routing layer — Vapi voice + Checkr background intake webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LicenseVerificationLog, MarylandProvider
from app.services.vetted_status import VETTED_ACTION_NEEDED, VETTED_BLOCKED, sync_provider_vetted_status

logger = logging.getLogger(__name__)

PROFILE_PENDING_BACKGROUND_CHECK = "PENDING_BACKGROUND_CHECK"
PROFILE_VERIFICATION_QUEUE = "VERIFICATION_QUEUE"
REJECTED_COMPLIANCE = "REJECTED_COMPLIANCE"

ENV_INTAKE_BEARER = "INTAKE_WEBHOOK_BEARER_TOKEN"
ENV_CHECKR_WEBHOOK_SECRET = "CHECKR_WEBHOOK_SECRET"

router = APIRouter(prefix="/api/v1/intake", tags=["intake"])


# ---------------------------------------------------------------------------
# Security perimeter
# ---------------------------------------------------------------------------


def _configured_intake_bearer() -> str:
    return str(os.getenv(ENV_INTAKE_BEARER, "") or "").strip()


async def require_intake_bearer_token(request: Request) -> None:
    configured = _configured_intake_bearer()
    if not configured:
        raise HTTPException(status_code=503, detail="intake_webhook_token_not_configured")

    header = request.headers.get("Authorization", "")
    token = ""
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    if not token or not hmac.compare_digest(token, configured):
        raise HTTPException(status_code=401, detail="intake_unauthorized")


def _verify_checkr_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    if not secret or not signature_header:
        return False
    try:
        parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
        timestamp = parts.get("t", "")
        received = parts.get("v1", "")
        if not timestamp or not received:
            return False
        signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}"
        expected = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, received)
    except (ValueError, UnicodeDecodeError):
        return False


async def require_checkr_signature(request: Request) -> bytes:
    await require_intake_bearer_token(request)
    secret = str(os.getenv(ENV_CHECKR_WEBHOOK_SECRET, "") or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="checkr_webhook_secret_not_configured")

    raw_body = await request.body()
    signature = request.headers.get("X-Checkr-Signature") or request.headers.get("Checkr-Signature")
    if not _verify_checkr_signature(raw_body, signature, secret):
        raise HTTPException(status_code=401, detail="invalid_checkr_signature")
    return raw_body


# ---------------------------------------------------------------------------
# Payload contracts
# ---------------------------------------------------------------------------


class VapiExperienceMetadata(BaseModel):
    years_experience: float | None = None
    certifications: list[str] = Field(default_factory=list)
    specialty_areas: list[str] = Field(default_factory=list)
    facility_types: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class VapiVoiceScreeningIn(BaseModel):
    provider_id: UUID
    screening_status: str = Field(..., min_length=3, max_length=32)
    call_id: str | None = None
    transcription: str | None = None
    extracted_metadata: VapiExperienceMetadata | None = None


class IntakeWebhookResponse(BaseModel):
    ok: bool = True
    provider_id: str
    action: str
    profile_state: str | None = None
    detail: str | None = None


# ---------------------------------------------------------------------------
# Internal database adapter
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _append_verification_log(
    db: Session,
    *,
    provider_id: UUID,
    event_type: str,
    check_result: str,
    notes: str,
    reviewer: str,
) -> None:
    db.add(
        LicenseVerificationLog(
            provider_id=provider_id,
            event_type=event_type,
            check_result=check_result,
            notes=notes[:500],
            reviewer=reviewer,
        )
    )


def _get_provider_or_404(db: Session, provider_id: UUID) -> MarylandProvider:
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise HTTPException(status_code=404, detail="provider_not_found")
    return provider


def advance_provider_pending_background_check(
    db: Session,
    *,
    provider_id: UUID,
    transcription: str | None,
    metadata: VapiExperienceMetadata | None,
    call_id: str | None,
) -> MarylandProvider:
    provider = _get_provider_or_404(db, provider_id)
    provider.license_status = PROFILE_PENDING_BACKGROUND_CHECK
    provider.vetted_status_updated_at = _utc_now()

    meta_blob = metadata.model_dump() if metadata is not None else {}
    note_payload = {
        "call_id": call_id,
        "transcription_preview": (transcription or "")[:360],
        "extracted_metadata": meta_blob,
    }
    _append_verification_log(
        db,
        provider_id=provider_id,
        event_type="VAPI_VOICE_SCREENING",
        check_result="COMPLETED",
        notes=json.dumps(note_payload, ensure_ascii=False),
        reviewer="intake_vapi_webhook",
    )
    db.commit()
    db.refresh(provider)
    return provider


def advance_provider_verification_queue(
    db: Session,
    *,
    provider_id: UUID,
    checkr_status: str,
    report_id: str | None,
) -> MarylandProvider:
    provider = _get_provider_or_404(db, provider_id)
    provider.license_status = "UNVERIFIED"
    provider.vetted_status = VETTED_ACTION_NEEDED
    provider.vetted_status_updated_at = _utc_now()
    _append_verification_log(
        db,
        provider_id=provider_id,
        event_type="CHECKR_BACKGROUND",
        check_result="CLEAR",
        notes=json.dumps({"status": checkr_status, "report_id": report_id}, ensure_ascii=False),
        reviewer="intake_checkr_webhook",
    )
    sync_provider_vetted_status(db, provider, actor="intake_checkr_webhook")
    db.commit()
    db.refresh(provider)
    return provider


def flag_provider_rejected_compliance(
    db: Session,
    *,
    provider_id: UUID,
    checkr_status: str,
    report_id: str | None,
) -> MarylandProvider:
    provider = _get_provider_or_404(db, provider_id)
    provider.license_status = REJECTED_COMPLIANCE
    provider.dispatch_status = "SUSPENDED"
    provider.vetted_status = VETTED_BLOCKED
    provider.vetted_status_updated_at = _utc_now()
    _append_verification_log(
        db,
        provider_id=provider_id,
        event_type="CHECKR_BACKGROUND",
        check_result=REJECTED_COMPLIANCE,
        notes=json.dumps({"status": checkr_status, "report_id": report_id}, ensure_ascii=False),
        reviewer="intake_checkr_webhook",
    )
    db.commit()
    db.refresh(provider)
    return provider


def _resolve_checkr_provider_id(payload: dict[str, Any]) -> UUID:
    direct = payload.get("provider_id")
    if direct:
        return UUID(str(direct))

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    obj = data.get("object") if isinstance(data.get("object"), dict) else {}
    for key in ("provider_id", "external_id", "custom_id"):
        token = obj.get(key) or payload.get(key)
        if token:
            return UUID(str(token))

    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    if metadata.get("provider_id"):
        return UUID(str(metadata["provider_id"]))

    raise HTTPException(status_code=422, detail="checkr_provider_id_missing")


def _resolve_checkr_status(payload: dict[str, Any]) -> str:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    obj = data.get("object") if isinstance(data.get("object"), dict) else {}
    status = obj.get("status") or payload.get("status") or ""
    return str(status).strip().lower()


def _resolve_checkr_report_id(payload: dict[str, Any]) -> str | None:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    obj = data.get("object") if isinstance(data.get("object"), dict) else {}
    token = obj.get("id") or payload.get("report_id")
    return str(token) if token else None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/vapi-webhook",
    response_model=IntakeWebhookResponse,
    dependencies=[Depends(require_intake_bearer_token)],
)
def vapi_voice_screening_intake(payload: VapiVoiceScreeningIn, db: Session = Depends(get_db)) -> IntakeWebhookResponse:
    status = str(payload.screening_status or "").strip().upper()
    if status != "COMPLETED":
        logger.info(
            "Vapi intake ignored for provider=%s status=%s",
            payload.provider_id,
            status,
        )
        return IntakeWebhookResponse(
            ok=True,
            provider_id=str(payload.provider_id),
            action="ignored",
            profile_state=None,
            detail=f"screening_status={status}",
        )

    provider = advance_provider_pending_background_check(
        db,
        provider_id=payload.provider_id,
        transcription=payload.transcription,
        metadata=payload.extracted_metadata,
        call_id=payload.call_id,
    )
    logger.info("Vapi intake advanced provider=%s to %s", provider.provider_id, PROFILE_PENDING_BACKGROUND_CHECK)
    return IntakeWebhookResponse(
        ok=True,
        provider_id=str(provider.provider_id),
        action="advanced_pending_background_check",
        profile_state=PROFILE_PENDING_BACKGROUND_CHECK,
        detail="Voice screening transcription logged; background check may proceed.",
    )


@router.post(
    "/checkr-webhook",
    response_model=IntakeWebhookResponse,
)
async def checkr_background_intake(
    request: Request,
    db: Session = Depends(get_db),
    raw_body: bytes = Depends(require_checkr_signature),
) -> IntakeWebhookResponse:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_json") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="invalid_checkr_payload")

    provider_id = _resolve_checkr_provider_id(payload)
    checkr_status = _resolve_checkr_status(payload)
    report_id = _resolve_checkr_report_id(payload)

    if checkr_status == "clear":
        provider = advance_provider_verification_queue(
            db,
            provider_id=provider_id,
            checkr_status=checkr_status,
            report_id=report_id,
        )
        return IntakeWebhookResponse(
            ok=True,
            provider_id=str(provider.provider_id),
            action="queued_verification",
            profile_state=PROFILE_VERIFICATION_QUEUE,
            detail="Background check clear — provider routed to verification queue.",
        )

    if checkr_status == "consider":
        provider = flag_provider_rejected_compliance(
            db,
            provider_id=provider_id,
            checkr_status=checkr_status,
            report_id=report_id,
        )
        return IntakeWebhookResponse(
            ok=True,
            provider_id=str(provider.provider_id),
            action="rejected_compliance",
            profile_state=REJECTED_COMPLIANCE,
            detail="Background check consider — provider flagged REJECTED_COMPLIANCE.",
        )

    logger.info(
        "Checkr intake no-op provider=%s status=%s report=%s",
        provider_id,
        checkr_status,
        report_id,
    )
    return IntakeWebhookResponse(
        ok=True,
        provider_id=str(provider_id),
        action="ignored",
        profile_state=None,
        detail=f"checkr_status={checkr_status or 'unknown'}",
    )


def register_intake_webhooks(app) -> None:
    """Mount intake routes on an existing FastAPI application."""
    app.include_router(router)
