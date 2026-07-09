"""
Twilio SMS Webhooks — Conversational Dispatch + Wave Responses

Sprint: VCAI-TIER1-SPRINT-2026-07-07
Purpose: Handle inbound SMS messages from Twilio for conversational dispatch.

Webhook URLs:
- POST /api/webhooks/twilio/sms-inbound → Facility and nurse SMS messages
"""

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import PlainTextResponse

from app.services.conversational_dispatch_agent import ConversationalDispatchAgent
from app.services.wave_match_dispatcher import process_nurse_sms_response

router = APIRouter(prefix="/api/webhooks/twilio", tags=["twilio-webhooks"])


@router.post("/sms-inbound")
async def handle_inbound_sms(
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(None)
):
    """
    Twilio webhook for inbound SMS messages.
    
    Handles both facility shift requests and nurse responses.
    
    Flow:
    1. Check if sender is a registered facility
    2. If facility → route to conversational dispatch agent
    3. If nurse → route to wave match dispatcher
    
    Twilio POST parameters:
    - From: E.164 phone number sending the message
    - To: Your Twilio phone number
    - Body: SMS message text
    - MessageSid: Unique Twilio message identifier
    
    Returns:
    - 200 OK with empty TwiML response (no auto-reply needed)
    """
    # Determine if this is from a facility or nurse
    async with ConversationalDispatchAgent() as agent:
        is_facility = await agent.is_facility_phone(From)
    
    if is_facility:
        # Route to conversational dispatch agent (Feature #1)
        async with ConversationalDispatchAgent() as agent:
            result = await agent.process_inbound_facility_sms(
                from_phone=From,
                to_phone=To,
                message_body=Body,
                twilio_message_sid=MessageSid
            )
    else:
        # Route to wave match dispatcher (Feature #2)
        result = await process_nurse_sms_response(
            provider_phone=From,
            message_body=Body
        )
    
    # Return empty TwiML response (we handle replies in the agents)
    return PlainTextResponse(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        status_code=200,
        media_type="application/xml"
    )


@router.get("/sms-inbound")
async def handle_inbound_sms_get():
    """
    GET endpoint for Twilio webhook validation.
    
    Twilio sometimes hits webhook URLs with GET to verify they exist.
    """
    return {"status": "ok", "webhook": "twilio-sms-inbound"}
