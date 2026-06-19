"""LLM-generated B2B outreach email copy for Maryland nursing home crisis targets."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import settings


@dataclass(frozen=True)
class OutreachEmailDraft:
    subject: str
    body: str
    mode: str


def _template_email(
    *,
    administrator_name: str,
    facility_name: str,
    city_county_line: str,
    crisis_line: str,
    sender_name: str,
    agency_name: str,
) -> OutreachEmailDraft:
    subject = f"Emergency CNA/LPN backup coverage for {facility_name}"
    body = (
        f"Hi {administrator_name},\n\n"
        f"I noticed your team has been aggressively recruiting floor staff in the "
        f"{city_county_line} area. {crisis_line} "
        f"With Maryland COMAR's strict 1:15 staffing ratio rules, a single last-minute call-out "
        f"can put your facility out of compliance immediately.\n\n"
        f"Our agency specializes exclusively in local, fully credentialed, W-2 backup aides. "
        f"Our platform automatically dispatches certified staff who live within a short driving "
        f"radius to fill empty shifts within minutes.\n\n"
        f"Can I send over our standard, no-obligation shift-rate sheet so your scheduling team "
        f"has us on standby?\n\n"
        f"Best regards,\n"
        f"{sender_name}\n"
        f"{agency_name}"
    )
    return OutreachEmailDraft(subject=subject, body=body, mode="template")


def generate_crisis_outreach_email(
    *,
    administrator_name: str,
    facility_name: str,
    city: str | None,
    county: str | None,
    crisis_summary: str,
) -> OutreachEmailDraft:
    city_county_line = ", ".join(part for part in [city, county] if part) or "Maryland"
    crisis_line = crisis_summary.strip()
    if crisis_line and not crisis_line.endswith("."):
        crisis_line = f"{crisis_line}."
    sender_name = settings.OUTREACH_SENDER_NAME
    agency_name = settings.OUTREACH_AGENCY_NAME

    if settings.OUTREACH_LLM_DRY_RUN:
        return _template_email(
            administrator_name=administrator_name,
            facility_name=facility_name,
            city_county_line=city_county_line,
            crisis_line=crisis_line or "Continuous CNA/LPN postings suggest ongoing staffing pressure.",
            sender_name=sender_name,
            agency_name=agency_name,
        )

    url = str(settings.OUTREACH_LLM_URL or "").strip()
    api_key = str(settings.OUTREACH_LLM_API_KEY or "").strip()
    if not url:
        raise RuntimeError("OUTREACH_LLM_URL is not configured")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    prompt = (
        "Write a concise B2B email to a Maryland nursing home administrator. "
        "Tone: operational relief, not salesy. Mention COMAR 1:15 ratio risk, W-2 credentialed "
        "CNA/LPN backup, and 15-minute local dispatch. End with asking to send a shift-rate sheet.\n"
        f"Administrator: {administrator_name}\n"
        f"Facility: {facility_name}\n"
        f"Location: {city_county_line}\n"
        f"Crisis context: {crisis_line}\n"
        f"Sender: {sender_name}, {agency_name}"
    )
    with httpx.Client(timeout=settings.OUTREACH_LLM_TIMEOUT_SECONDS) as client:
        response = client.post(
            url,
            headers=headers,
            json={
                "model": settings.OUTREACH_LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "You write short, professional healthcare staffing outreach emails."},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()

    content = ""
    if isinstance(payload, dict):
        choices = payload.get("choices") or []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            content = str(message.get("content") or "").strip()
        content = content or str(payload.get("body") or payload.get("text") or "").strip()
    if not content:
        raise RuntimeError("LLM returned empty outreach email body")

    subject = f"Emergency CNA/LPN backup coverage for {facility_name}"
    if content.lower().startswith("subject:"):
        lines = content.splitlines()
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).strip()
    else:
        body = content
    return OutreachEmailDraft(subject=subject, body=body, mode="llm")
