"""Validate inbound Twilio webhook signatures."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from twilio.request_validator import RequestValidator

from app.config import settings


async def parse_twilio_form(request: Request) -> dict[str, str]:
    form = await request.form()
    return {key: str(value) for key, value in form.items()}


async def validate_twilio_inbound_request(request: Request) -> dict[str, str]:
    params = await parse_twilio_form(request)
    if not settings.TWILIO_VALIDATE_SIGNATURES:
        return params

    auth_token = str(settings.TWILIO_AUTH_TOKEN or "").strip()
    if not auth_token:
        raise HTTPException(status_code=503, detail="twilio_auth_token_not_configured")

    signature = request.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(auth_token)
    if not validator.validate(str(request.url), params, signature):
        raise HTTPException(status_code=403, detail="invalid_twilio_signature")
    return params


def compute_twilio_signature(url: str, params: dict[str, Any], auth_token: str) -> str:
    return RequestValidator(auth_token).compute_signature(url, params)
