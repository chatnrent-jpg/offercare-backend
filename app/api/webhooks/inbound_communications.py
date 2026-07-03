"""Inbound communications webhook — ingest voice transcriptions and SMS payloads."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["inbound-communications"])

_TRACKING_PREFIX = "inbound_comm_"
_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
_NIGHT_SHIFT_TAG = "NIGHT_SHIFT"

class InboundCommunicationsHardStop(RuntimeError):
    """Hive halt — inbound communications dependency or compile failure."""


@dataclass(frozen=True, slots=True)
class InboundCommunicationPayload:
    from_phone: str
    body: str
    transcription_text: str | None
    raw: dict[str, Any]


def _communication_settings() -> dict[str, Any]:
    """Lazy settings touch — keeps import graph shallow for COMPILE_OK."""
    try:
        from app.config import settings
    except Exception as exc:  # noqa: BLE001
        raise InboundCommunicationsHardStop("settings_import_failed") from exc

    return {
        "public_base_url": str(getattr(settings, "PUBLIC_BASE_URL", "") or "").strip(),
        "twilio_validate": bool(getattr(settings, "TWILIO_VALIDATE_SIGNATURES", False)),
    }


def _new_tracking_token() -> str:
    return f"{_TRACKING_PREFIX}{uuid.uuid4().hex}"


def _coerce_payload_dict(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("payload_not_object")
    return data


def _payload_from_mapping(data: dict[str, Any]) -> InboundCommunicationPayload:
    from_phone = str(data.get("From") or data.get("from") or "").strip()
    body_text = str(data.get("Body") or data.get("body") or "").strip()
    transcription_raw = data.get("TranscriptionText") or data.get("transcription_text")
    transcription_text = str(transcription_raw).strip() if transcription_raw else None
    return InboundCommunicationPayload(
        from_phone=from_phone,
        body=body_text,
        transcription_text=transcription_text,
        raw=data,
    )


async def _parse_inbound_payload(request: Request) -> InboundCommunicationPayload:
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        return _payload_from_mapping(_coerce_payload_dict(await request.json()))

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        return _payload_from_mapping({str(key): str(value) for key, value in form.items()})

    raw_bytes = await request.body()
    if not raw_bytes.strip():
        return _payload_from_mapping({})

    stripped = raw_bytes.lstrip()
    if stripped.startswith(b"{"):
        parsed = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        return _payload_from_mapping(_coerce_payload_dict(parsed))

    parsed_qs = parse_qs(raw_bytes.decode("utf-8", errors="replace"), keep_blank_values=True)
    flat = {key: (values[0] if values else "") for key, values in parsed_qs.items()}
    return _payload_from_mapping(flat)


def _effective_message_text(payload: InboundCommunicationPayload) -> str:
    if payload.body:
        return payload.body
    return payload.transcription_text or ""


def _build_shift_context_from_extraction(
    *,
    tracking_token: str,
    payload: InboundCommunicationPayload,
    message_text: str,
    facility: Any,
    extraction: Any,
) -> dict[str, Any]:
    shift_start_time = "23:00:00+00:00" if extraction.shift_tag == _NIGHT_SHIFT_TAG else "07:00:00+00:00"
    care_tags = list(extraction.specialized_care_tags)
    context: dict[str, Any] = {
        "required_role": extraction.role_type,
        "shift_role": " ".join(part for part in (extraction.role_type, extraction.shift_tag) if part),
        "facility_type": "SNF",
        "care_tags": care_tags,
        "specialty_tags": care_tags,
        "qualifiers": " ".join(care_tags) if care_tags else message_text,
        "query_text": message_text,
        "shift_starts_at": f"{extraction.shift_date_iso}T{shift_start_time}",
        "inbound_tracking_token": tracking_token,
        "inbound_from_phone": payload.from_phone,
        "inbound_channel": "voice" if payload.transcription_text and not payload.body else "sms",
    }
    if getattr(facility, "facility_id", None):
        context["facility_id"] = facility.facility_id
    if getattr(facility, "facility_name", None):
        context["facility_name"] = facility.facility_name
    if getattr(facility, "latitude", None) is not None and getattr(facility, "longitude", None) is not None:
        context["latitude"] = float(facility.latitude)
        context["longitude"] = float(facility.longitude)
    return context


def _run_inbound_speech_to_match_pipeline(
    *,
    tracking_token: str,
    payload: InboundCommunicationPayload,
    message_text: str,
) -> None:
    from strategy.semantic_dispatch_extractor import SemanticDispatchExtractor
    from strategy.unified_match_matrix_broker import UnifiedMatchMatrixBroker

    extractor = SemanticDispatchExtractor()
    broker = UnifiedMatchMatrixBroker()
    try:
        facility = extractor.resolve_incoming_facility(payload.from_phone)
        extraction = extractor.extract_shift_parameters(message_text, facility=facility)
        shift_context = _build_shift_context_from_extraction(
            tracking_token=tracking_token,
            payload=payload,
            message_text=message_text,
            facility=facility,
            extraction=extraction,
        )
        match_result = broker.resolve_canonical_shift_matches(tracking_token, shift_context)
        logger.info(
            "inbound comm match dispatch token=%s facility=%s shift_date=%s ok=%s match_count=%s engine=%s",
            tracking_token,
            getattr(facility, "facility_token", "unknown"),
            extraction.shift_date_iso,
            match_result.get("ok"),
            match_result.get("match_count"),
            match_result.get("routing_engine"),
        )
    finally:
        try:
            extractor.close()
        except Exception:  # noqa: BLE001
            logger.debug("inbound comm extractor close skipped token=%s", tracking_token, exc_info=True)
        try:
            broker.close()
        except Exception:  # noqa: BLE001
            logger.debug("inbound comm broker close skipped token=%s", tracking_token, exc_info=True)


def _resolve_inbound_payload(
    *,
    payload: InboundCommunicationPayload | None = None,
    from_phone: str = "",
    body: str = "",
    transcription_text: str | None = None,
    raw: dict[str, Any] | None = None,
    **form_fields: Any,
) -> InboundCommunicationPayload:
    """Normalize webhook kwargs — accepts dataclass payload or Twilio-style string fields."""
    if payload is not None:
        return payload

    merged: dict[str, Any] = dict(raw or {})
    for key, value in form_fields.items():
        if value is not None:
            merged[key] = value

    phone = str(from_phone or merged.get("From") or merged.get("from") or "").strip()
    message_body = str(body or merged.get("Body") or merged.get("body") or "").strip()
    transcription_raw = (
        transcription_text
        if transcription_text is not None
        else merged.get("TranscriptionText") or merged.get("transcription_text")
    )
    transcription = str(transcription_raw).strip() if transcription_raw else None

    return InboundCommunicationPayload(
        from_phone=phone,
        body=message_body,
        transcription_text=transcription,
        raw=merged,
    )


def _process_inbound_communication_async(
    *,
    tracking_token: str,
    payload: InboundCommunicationPayload | None = None,
    from_phone: str = "",
    body: str = "",
    transcription_text: str | None = None,
    raw: dict[str, Any] | None = None,
    **form_fields: Any,
) -> None:
    """Speech-to-match pipeline — executed asynchronously after carrier handshake."""
    try:
        _communication_settings()
        resolved_payload = _resolve_inbound_payload(
            payload=payload,
            from_phone=from_phone,
            body=body,
            transcription_text=transcription_text,
            raw=raw,
            **form_fields,
        )
        message_text = _effective_message_text(resolved_payload)
        from_tail = resolved_payload.from_phone[-4:] if len(resolved_payload.from_phone) >= 4 else "????"

        logger.info(
            "inbound comm processing token=%s from_tail=%s body_len=%s has_transcription=%s",
            tracking_token,
            from_tail,
            len(message_text),
            bool(resolved_payload.transcription_text),
        )

        if not message_text.strip():
            logger.info("inbound comm skipped empty payload token=%s", tracking_token)
            return

        _run_inbound_speech_to_match_pipeline(
            tracking_token=tracking_token,
            payload=resolved_payload,
            message_text=message_text,
        )
    except Exception:  # noqa: BLE001
        logger.exception("HIVE_COMM_ALERT inbound comm background failed token=%s", tracking_token)


def _handshake_response(*, tracking_token: str, request: Request) -> Response:
    content_type = (request.headers.get("content-type") or "").lower()
    accept = (request.headers.get("accept") or "").lower()

    if "application/x-www-form-urlencoded" in content_type or "xml" in accept:
        return Response(content=_EMPTY_TWIML, media_type="application/xml", status_code=200)

    return JSONResponse(
        status_code=200,
        content={"ok": True, "received": True, "tracking_token": tracking_token},
    )


@router.post("/inbound-communications")
async def inbound_communications_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """Accept carrier payloads, queue shift parsing, return immediate handshake."""
    tracking_token = _new_tracking_token()
    try:
        payload = await _parse_inbound_payload(request)
        background_tasks.add_task(
            _process_inbound_communication_async,
            tracking_token=tracking_token,
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "HIVE_COMM_ALERT inbound comm webhook fail-open token=%s err=%s",
            tracking_token,
            exc,
            exc_info=True,
        )

    return _handshake_response(tracking_token=tracking_token, request=request)


def register_inbound_communications_webhook(app) -> None:
    app.include_router(router)


if __name__ == "__main__":
    sample = _payload_from_mapping(
        {
            "From": "+15551234567",
            "Body": "YES lock night shift",
            "TranscriptionText": "yes lock night shift",
        }
    )
    token = _new_tracking_token()
    assert token.startswith(_TRACKING_PREFIX)
    assert sample.from_phone.startswith("+")

    resolved = _resolve_inbound_payload(
        from_phone="+15559876543",
        body="CNA tomorrow night dementia",
        transcription_text=None,
    )
    assert resolved.from_phone == "+15559876543"
    assert resolved.body.startswith("CNA")

    print("COMPILE_OK inbound_communications_webhook")
