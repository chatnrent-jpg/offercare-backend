"""Maryland Judiciary Case Search screening (healthcare worker exclusions)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.models import MarylandProvider
from app.services.live_scraper_http import request_live_scraper
from app.services.live_scraper_urls import effective_live_scraper_url


@dataclass(frozen=True)
class JudiciaryScreenResult:
    status: str  # CLEAR, REVIEW, FLAGGED
    source: str
    case_count: int
    raw: dict


def screen_md_judiciary(provider: MarylandProvider) -> JudiciaryScreenResult:
    if settings.MD_JUDICIARY_DRY_RUN:
        token = str(provider.full_name or "").strip().upper()
        status = "FLAGGED" if "FLAGGED" in token else "CLEAR"
        return JudiciaryScreenResult(
            status=status,
            source="MD_JUDICIARY_DRY_RUN",
            case_count=0 if status == "CLEAR" else 1,
            raw={"full_name": provider.full_name, "dry_run": True},
        )

    url = effective_live_scraper_url("judiciary")
    if not url:
        raise RuntimeError("MD_JUDICIARY_SEARCH_URL is not configured")

    response = request_live_scraper(
        method="GET",
        url=url,
        timeout=settings.MD_JUDICIARY_TIMEOUT_SECONDS,
        params={"name": provider.full_name},
    )
    response.raise_for_status()
    payload = response.json()

    cases = payload.get("cases") or []
    status = "CLEAR" if not cases else "REVIEW"
    return JudiciaryScreenResult(
        status=status,
        source="MD_JUDICIARY",
        case_count=len(cases),
        raw=payload if isinstance(payload, dict) else {"body": payload},
    )


def judiciary_result_to_json(result: JudiciaryScreenResult) -> str:
    return json.dumps(
        {
            "status": result.status,
            "source": result.source,
            "case_count": result.case_count,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "raw": result.raw,
        }
    )
