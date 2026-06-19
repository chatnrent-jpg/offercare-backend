"""Shared CMS Hospital General Information scraper helpers."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.schemas import FacilityScrapePreviewResponse, FacilityScrapeResponse
from app.services.maryland_facility_scraper import (
    ScrapedFacility,
    map_facility_type,
    normalize_county,
    preview_to_response_rows,
    upsert_scraped_facilities,
)

CMS_SCRAPE_SOURCE = "CMS_HOSPITAL_INFO"


def _county_condition(county: str | None) -> dict[str, str] | None:
    if not county:
        return None
    token = county.strip().upper().replace(" COUNTY", "")
    return {"property": "countyparish", "value": token, "operator": "contains"}


def fetch_cms_hospitals_by_state(
    state: str,
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
    timeout_seconds: float = 20.0,
) -> list[dict[str, Any]]:
    url = api_url or settings.CMS_HOSPITALS_API_URL
    conditions: list[dict[str, str]] = [
        {"property": "state", "value": state.upper(), "operator": "="},
    ]
    county_condition = _county_condition(county)
    if county_condition is not None:
        conditions.append(county_condition)
    body: dict[str, Any] = {"conditions": conditions}
    if limit is not None:
        body["limit"] = limit
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, json=body)
        response.raise_for_status()
        payload = response.json()
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("unexpected_api_payload")
    return results


def parse_cms_hospital_row(
    row: dict[str, Any],
    *,
    state: str,
    source: str = CMS_SCRAPE_SOURCE,
) -> ScrapedFacility | None:
    external_id = str(row.get("facility_id") or "").strip()
    name = str(row.get("facility_name") or "").strip()
    if not external_id or not name:
        return None
    return ScrapedFacility(
        external_source=source,
        external_id=external_id,
        name=name,
        facility_type=map_facility_type(str(row.get("hospital_type") or "")),
        county=normalize_county(str(row.get("countyparish") or state)),
        state=state.upper(),
        address=str(row.get("address") or "").strip() or None,
        city=str(row.get("citytown") or "").strip().title() or None,
        zip_code=str(row.get("zip_code") or "").strip() or None,
        phone=str(row.get("telephone_number") or "").strip() or None,
    )


def parse_cms_hospital_rows(
    rows: list[dict[str, Any]],
    *,
    state: str,
    source: str = CMS_SCRAPE_SOURCE,
) -> list[ScrapedFacility]:
    parsed: list[ScrapedFacility] = []
    for row in rows:
        facility = parse_cms_hospital_row(row, state=state, source=source)
        if facility is not None:
            parsed.append(facility)
    return parsed


def preview_cms_hospitals(
    state: str,
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
) -> FacilityScrapePreviewResponse:
    rows = fetch_cms_hospitals_by_state(state, limit=limit, county=county, api_url=api_url)
    facilities = parse_cms_hospital_rows(rows, state=state)
    return FacilityScrapePreviewResponse(
        source=CMS_SCRAPE_SOURCE,
        state=state.upper(),
        fetched=len(facilities),
        facilities=preview_to_response_rows(facilities),
    )


def scrape_and_ingest_cms_hospitals(
    db: Session,
    state: str,
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
) -> FacilityScrapeResponse:
    rows = fetch_cms_hospitals_by_state(state, limit=limit, county=county, api_url=api_url)
    facilities = parse_cms_hospital_rows(rows, state=state)
    created, updated, skipped, errors, _touched = upsert_scraped_facilities(db, facilities)
    return FacilityScrapeResponse(
        source=CMS_SCRAPE_SOURCE,
        state=state.upper(),
        fetched=len(facilities),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )
