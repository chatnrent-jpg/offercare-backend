"""Maryland Board of Nursing (MBON) license verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.models import MarylandProvider
from app.services.live_scraper_http import request_live_scraper
from app.services.live_scraper_urls import effective_live_scraper_url


@dataclass(frozen=True)
class MbonVerificationResult:
    status: str  # ACTIVE, EXPIRED, DISCIPLINE, NOT_FOUND
    license_number: str
    expires_on: datetime | None
    disciplinary_action: bool
    source: str
    raw: dict


def verify_mbon_license(provider: MarylandProvider) -> MbonVerificationResult:
    license_number = str(provider.md_license_number or "").strip().upper()
    if settings.MBON_VERIFY_DRY_RUN:
        expires = datetime.now(timezone.utc) + timedelta(days=365)
        status = "EXPIRED" if license_number.endswith("X") else "ACTIVE"
        token = license_number
        gna_endorsement = token.startswith("GNA") or (
            token.startswith("CNA") and not token.endswith("NOGNA")
        )
        return MbonVerificationResult(
            status=status,
            license_number=license_number,
            expires_on=None if status == "EXPIRED" else expires,
            disciplinary_action=license_number.endswith("D"),
            source="MBON_DRY_RUN",
            raw={
                "license_number": license_number,
                "credential_type": provider.credential_type,
                "status": status,
                "gna_endorsement": gna_endorsement,
                "dry_run": True,
            },
        )

    url = effective_live_scraper_url("mbon")
    if not url:
        raise RuntimeError("MBON_VERIFY_URL is not configured")

    response = request_live_scraper(
        method="GET",
        url=url,
        timeout=settings.MBON_VERIFY_TIMEOUT_SECONDS,
        params={
            "license": license_number,
            "name": provider.full_name,
        },
    )
    response.raise_for_status()
    payload = response.json()

    expires_raw = payload.get("expires_on")
    expires_on = datetime.fromisoformat(expires_raw) if expires_raw else None
    return MbonVerificationResult(
        status=str(payload.get("status") or "NOT_FOUND").upper(),
        license_number=license_number,
        expires_on=expires_on,
        disciplinary_action=bool(payload.get("disciplinary_action")),
        source="MBON_API",
        raw=payload if isinstance(payload, dict) else {"body": payload},
    )


def mbon_result_to_json(result: MbonVerificationResult) -> str:
    return json.dumps(
        {
            "status": result.status,
            "license_number": result.license_number,
            "expires_on": result.expires_on.isoformat() if result.expires_on else None,
            "disciplinary_action": result.disciplinary_action,
            "source": result.source,
            "raw": result.raw,
        }
    )
