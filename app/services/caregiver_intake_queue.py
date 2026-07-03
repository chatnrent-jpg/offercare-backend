"""Caregiver text-to-apply intake queue — shared by landing pages and Workstream webhooks."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import CaregiverIntakeQueue, MarylandProvider
from app.services.care_taxonomy import normalize_credential_type
from app.services.maryland_landing import MARYLAND_LANDING_CREDENTIALS
from app.services.worker_consent import WORKER_CONSENT_VERSION


def normalize_us_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("invalid_phone_number")
    return digits


def queue_caregiver_text_intake(
    db: Session,
    *,
    phone_number: str,
    landing_slug: str,
    market: str,
    credential_type: str = "CNA",
    full_name: str | None = None,
    home_zip: str | None = None,
    consent_version: str = WORKER_CONSENT_VERSION,
    sms_consent: bool = True,
    client_ip: str | None = None,
    notes: str | None = None,
    source_channel: str | None = None,
    region_metadata: dict[str, Any] | None = None,
) -> dict:
    phone = normalize_us_phone(phone_number)
    credential = normalize_credential_type(credential_type)
    if credential not in MARYLAND_LANDING_CREDENTIALS:
        raise ValueError("unsupported_credential")
    if consent_version != WORKER_CONSENT_VERSION:
        raise ValueError("consent_version_mismatch")
    if not sms_consent:
        raise ValueError("consent_required")

    existing_provider = (
        db.query(MarylandProvider).filter(MarylandProvider.phone_number == phone).one_or_none()
    )
    if existing_provider is not None:
        raise ValueError("portal_account_exists")

    open_intake = (
        db.query(CaregiverIntakeQueue)
        .filter(
            CaregiverIntakeQueue.phone_number == phone,
            CaregiverIntakeQueue.landing_slug == landing_slug,
            CaregiverIntakeQueue.queue_status == "QUEUED",
        )
        .one_or_none()
    )
    if open_intake is not None:
        raise ValueError("duplicate_application")

    note_parts = [notes or f"text-to-apply:{landing_slug}"]
    if source_channel:
        note_parts.append(f"channel:{source_channel}")
    if region_metadata:
        note_parts.append(f"region_metadata={json.dumps(region_metadata, separators=(',', ':'))}")

    row = CaregiverIntakeQueue(
        phone_number=phone,
        full_name=(full_name or "").strip() or None,
        credential_type=credential,
        home_zip=(home_zip or "").strip() or None,
        landing_slug=landing_slug,
        market=market,
        queue_status="QUEUED",
        sms_consent="true" if sms_consent else "false",
        consent_version=consent_version,
        client_ip=client_ip,
        notes=" · ".join(note_parts),
    )
    db.add(row)
    db.flush()

    return {
        "intake_id": str(row.intake_id),
        "queue_status": row.queue_status,
        "phone_number_masked": f"***-***-{phone[-4:]}",
        "market": row.market,
        "credential_type": row.credential_type,
        "landing_slug": row.landing_slug,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "region_metadata": region_metadata or {},
    }
