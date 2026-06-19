"""Indeed / ZipRecruiter crisis indicator scraper for Maryland nursing home hiring."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.services.live_scraper_http import request_live_scraper
from app.services.live_scraper_urls import effective_live_scraper_url

CRISIS_ROLES: tuple[str, ...] = ("CNA", "LPN", "GNA")
JOB_BOARD_SOURCES: tuple[str, ...] = ("INDEED", "ZIPRECRUITER")


@dataclass(frozen=True)
class ScrapedJobListing:
    source: str
    external_id: str
    facility_name: str
    city: str | None
    county: str | None
    state: str
    shift_role: str
    job_title: str
    job_url: str | None
    days_open: int


def _normalize_name(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    return re.sub(r"\s+", " ", token)


def infer_shift_role(title: str) -> str | None:
    token = str(title or "").upper()
    if "LPN" in token or "LICENSED PRACTICAL" in token:
        return "LPN"
    if "GNA" in token or "GERIATRIC NURSING ASSISTANT" in token:
        return "GNA"
    if "CNA" in token or "CERTIFIED NURSING ASSISTANT" in token or "NURSING ASSISTANT" in token:
        return "CNA"
    return None


def _dry_run_listings() -> list[ScrapedJobListing]:
    return [
        ScrapedJobListing(
            source="INDEED",
            external_id="indeed-futurecare-northpoint-cna",
            facility_name="FutureCare Northpoint",
            city="Baltimore",
            county="Baltimore",
            state="MD",
            shift_role="CNA",
            job_title="Certified Nursing Assistant (CNA) — Immediate Openings",
            job_url="https://www.indeed.com/viewjob?jk=futurecare-northpoint-cna",
            days_open=47,
        ),
        ScrapedJobListing(
            source="ZIPRECRUITER",
            external_id="zip-genesis-baltimore-lpn",
            facility_name="Genesis HealthCare Baltimore Center",
            city="Baltimore",
            county="Baltimore",
            state="MD",
            shift_role="LPN",
            job_title="Licensed Practical Nurse (LPN) — Full Time & Per Diem",
            job_url="https://www.ziprecruiter.com/jobs/genesis-baltimore-lpn",
            days_open=38,
        ),
        ScrapedJobListing(
            source="INDEED",
            external_id="indeed-communicare-silver-spring-cna",
            facility_name="CommuniCare Silver Spring",
            city="Silver Spring",
            county="Montgomery",
            state="MD",
            shift_role="CNA",
            job_title="CNA / Floor Aide — Sign-On Bonus",
            job_url="https://www.indeed.com/viewjob?jk=communicare-ss-cna",
            days_open=52,
        ),
        ScrapedJobListing(
            source="ZIPRECRUITER",
            external_id="zip-futurecare-landover-gna",
            facility_name="FutureCare Landover",
            city="Landover",
            county="Prince George's",
            state="MD",
            shift_role="GNA",
            job_title="Geriatric Nursing Assistant (GNA)",
            job_url="https://www.ziprecruiter.com/jobs/futurecare-landover-gna",
            days_open=19,
        ),
        ScrapedJobListing(
            source="INDEED",
            external_id="indeed-lifebridge-cna",
            facility_name="LifeBridge Health SNF",
            city="Towson",
            county="Baltimore",
            state="MD",
            shift_role="CNA",
            job_title="Nursing Assistant — Nights",
            job_url="https://www.indeed.com/viewjob?jk=lifebridge-cna",
            days_open=12,
        ),
    ]


def _parse_live_payload(source: str, payload: dict) -> list[ScrapedJobListing]:
    rows = payload.get("listings") or payload.get("jobs") or []
    listings: list[ScrapedJobListing] = []
    for index, row in enumerate(rows):
        title = str(row.get("title") or row.get("job_title") or "").strip()
        role = str(row.get("shift_role") or "").strip().upper() or infer_shift_role(title)
        if role not in CRISIS_ROLES:
            continue
        facility_name = str(row.get("facility_name") or row.get("company") or "").strip()
        if not facility_name:
            continue
        external_id = str(row.get("external_id") or row.get("id") or f"{source.lower()}-{index}")
        days_open = int(row.get("days_open") or row.get("days_listed") or 0)
        listings.append(
            ScrapedJobListing(
                source=source,
                external_id=external_id,
                facility_name=facility_name,
                city=str(row.get("city") or "").strip() or None,
                county=str(row.get("county") or "").strip() or None,
                state=str(row.get("state") or "MD").strip().upper()[:2],
                shift_role=role,
                job_title=title or f"{role} opening",
                job_url=str(row.get("url") or row.get("job_url") or "").strip() or None,
                days_open=max(days_open, 0),
            )
        )
    return listings


def fetch_job_board_listings() -> list[ScrapedJobListing]:
    if settings.JOB_BOARD_SCRAPE_DRY_RUN:
        return _dry_run_listings()

    url = effective_live_scraper_url("job_board")
    if not url:
        raise RuntimeError("JOB_BOARD_SCRAPE_URL is not configured")

    listings: list[ScrapedJobListing] = []
    response = request_live_scraper(
        method="GET",
        url=url,
        timeout=settings.JOB_BOARD_SCRAPE_TIMEOUT_SECONDS,
        params={
            "state": "MD",
            "roles": ",".join(CRISIS_ROLES),
            "sources": ",".join(JOB_BOARD_SOURCES),
        },
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        if "listings" in payload:
            listings.extend(_parse_live_payload("AGGREGATOR", payload))
        else:
            for source in JOB_BOARD_SOURCES:
                source_key = source.lower()
                if source_key in payload:
                    listings.extend(_parse_live_payload(source, payload[source_key]))
    return [row for row in listings if row.state == "MD"]


def match_facility_name(facility_name: str, candidates: list) -> object | None:
    target = _normalize_name(facility_name)
    if not target:
        return None
    target_tokens = {token for token in target.split() if len(token) > 2}
    best = None
    best_score = 0
    for facility in candidates:
        name = _normalize_name(getattr(facility, "name", ""))
        if not name:
            continue
        if target == name or target in name or name in target:
            score = min(len(target), len(name)) + 100
        else:
            name_tokens = {token for token in name.split() if len(token) > 2}
            overlap = len(target_tokens & name_tokens)
            if overlap < 2:
                continue
            score = overlap
        if score > best_score:
            best = facility
            best_score = score
    return best
