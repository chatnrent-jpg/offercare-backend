"""Workstream text-to-apply webhook — route candidate SMS replies to caregiver_intake_queue."""

from __future__ import annotations

import hmac
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.baltimore_instant_pay_landing import LANDING_SLUG
from app.services.caregiver_intake_queue import queue_caregiver_text_intake
from app.services.worker_consent import WORKER_CONSENT_VERSION

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks/workstream", tags=["workstream-webhooks"])

ENV_WEBHOOK_BEARER = "WORKSTREAM_WEBHOOK_BEARER_TOKEN"


class WorkstreamTextApplyWebhookIn(BaseModel):
    event: str | None = None
    phone: str | None = None
    phone_number: str | None = None
    global_phone_number: str | None = None
    sms_phone_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None
    referer_source: str | None = None
    source: str | None = None
    board: str | None = None
    message: str | None = None
    body: str | None = None
    landing_slug: str | None = Field(default=LANDING_SLUG)
    credential_type: str = Field(default="CNA")
    consent_sms_dispatch: bool = Field(default=True)
    consent_version: str = Field(default=WORKER_CONSENT_VERSION)
    position: dict[str, Any] | None = None
    applicant: dict[str, Any] | None = None
    position_application: dict[str, Any] | None = None


class WorkstreamTextApplyWebhookOut(BaseModel):
    ok: bool = True
    intake_id: str
    queue_status: str
    phone_number_masked: str
    source_channel: str | None = None
    message: str


def _configured_bearer() -> str:
    return str(os.environ.get(ENV_WEBHOOK_BEARER) or "").strip()


async def require_workstream_webhook_bearer(request: Request) -> None:
    configured = _configured_bearer()
    if not configured:
        raise HTTPException(status_code=503, detail="workstream_webhook_token_not_configured")

    header = request.headers.get("Authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not token or not hmac.compare_digest(token, configured):
        raise HTTPException(status_code=401, detail="workstream_webhook_unauthorized")


def _pick_phone(payload: WorkstreamTextApplyWebhookIn) -> str:
    nested = payload.applicant or payload.position_application or {}
    for candidate in (
        payload.phone,
        payload.phone_number,
        payload.global_phone_number,
        payload.sms_phone_number,
        nested.get("phone"),
        nested.get("global_phone_number"),
        nested.get("sms_phone_number"),
    ):
        if candidate:
            return str(candidate)
    raise ValueError("phone_required")


def _pick_name(payload: WorkstreamTextApplyWebhookIn) -> str | None:
    nested = payload.applicant or payload.position_application or {}
    if payload.first_name:
        last = str(payload.last_name or "").strip()
        return f"{payload.first_name} {last}".strip()
    for candidate in (payload.name, nested.get("name")):
        if candidate:
            return str(candidate).strip()
    first = nested.get("first_name")
    if first:
        last = str(nested.get("last_name") or "").strip()
        return f"{first} {last}".strip()
    return None


def _pick_source(payload: WorkstreamTextApplyWebhookIn) -> str:
    nested = payload.applicant or payload.position_application or {}
    for candidate in (
        payload.referer_source,
        payload.source,
        payload.board,
        nested.get("referer_source"),
        nested.get("source"),
    ):
        if candidate:
            return str(candidate)
    return "Workstream"


def ingest_workstream_text_reply(
    db: Session,
    payload: WorkstreamTextApplyWebhookIn,
    *,
    client_ip: str | None = None,
) -> dict:
    phone = _pick_phone(payload)
    source = _pick_source(payload)
    name = _pick_name(payload)
    landing_slug = str(payload.landing_slug or LANDING_SLUG)

    result = queue_caregiver_text_intake(
        db,
        phone_number=phone,
        landing_slug=landing_slug,
        market="Baltimore",
        credential_type=payload.credential_type,
        full_name=name,
        consent_version=payload.consent_version,
        sms_consent=payload.consent_sms_dispatch,
        client_ip=client_ip,
        notes=f"workstream:text-reply:{source.lower()}",
        source_channel=source,
    )
    return {
        **result,
        "source_channel": source,
        "message": (
            f"Candidate from {source} queued in caregiver_intake_queue. "
            "Intake team will send Baltimore onboarding link."
        ),
    }


@router.post("/text-apply", response_model=WorkstreamTextApplyWebhookOut)
def workstream_text_apply_webhook(
    payload: WorkstreamTextApplyWebhookIn,
    request: Request,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_workstream_webhook_bearer),
):
    client_ip = request.client.host if request.client else None
    try:
        result = ingest_workstream_text_reply(db, payload, client_ip=client_ip)
    except ValueError as exc:
        token = str(exc)
        if token == "duplicate_application":
            raise HTTPException(status_code=409, detail="duplicate_application") from exc
        if token == "portal_account_exists":
            raise HTTPException(status_code=409, detail="portal_account_exists") from exc
        if token in {"phone_required", "invalid_phone_number", "consent_required", "consent_version_mismatch"}:
            raise HTTPException(status_code=422, detail=token) from exc
        raise
    db.commit()
    return WorkstreamTextApplyWebhookOut(**result)


def register_workstream_intake_webhook(app) -> None:
    app.include_router(router)
