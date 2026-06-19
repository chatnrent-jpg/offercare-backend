"""Federal OIG LEIE exclusion screening."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.models import MarylandProvider
from app.services.live_scraper_http import request_live_scraper
from app.services.live_scraper_urls import effective_live_scraper_url


@dataclass(frozen=True)
class OigScreeningResult:
    status: str  # CLEAR, EXCLUDED, REVIEW
    source: str
    match_count: int
    raw: dict


def screen_oig_exclusion(provider: MarylandProvider) -> OigScreeningResult:
    if settings.OIG_SCREEN_DRY_RUN:
        token = str(provider.full_name or "").strip().upper()
        status = "EXCLUDED" if "EXCLUDED" in token else "CLEAR"
        return OigScreeningResult(
            status=status,
            source="OIG_DRY_RUN",
            match_count=0 if status == "CLEAR" else 1,
            raw={"full_name": provider.full_name, "npi": provider.npi_number, "dry_run": True},
        )

    url = effective_live_scraper_url("oig")
    if not url:
        raise RuntimeError("OIG_LEIE_SEARCH_URL is not configured")

    response = request_live_scraper(
        method="POST",
        url=url,
        timeout=settings.OIG_SCREEN_TIMEOUT_SECONDS,
        json={
            "name": provider.full_name,
            "npi": provider.npi_number,
        },
    )
    response.raise_for_status()
    payload = response.json()

    matches = payload.get("matches") or []
    status = "CLEAR" if not matches else "EXCLUDED"
    return OigScreeningResult(
        status=status,
        source="OIG_LEIE",
        match_count=len(matches),
        raw=payload if isinstance(payload, dict) else {"body": payload},
    )


def oig_result_to_json(result: OigScreeningResult) -> str:
    return json.dumps(
        {
            "status": result.status,
            "source": result.source,
            "match_count": result.match_count,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "raw": result.raw,
        }
    )
