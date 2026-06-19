"""Ingest Pennsylvania hospital facilities from PA Department of Health open data."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.schemas import FacilityScrapePreviewResponse, FacilityScrapePreviewRow, FacilityScrapeResponse
from app.services.maryland_facility_scraper import (
    ScrapedFacility,
    normalize_county,
    preview_to_response_rows,
    upsert_scraped_facilities,
)

PA_SCRAPE_SOURCE = "PA_DOH_ARCGIS"


def build_pa_api_url(
    *,
    base_url: str | None = None,
    limit: int | None = None,
    county: str | None = None,
) -> str:
    base = base_url or settings.PA_HOSPITALS_API_URL
    where = "1=1"
    if county:
        token = county.strip().upper().replace(" COUNTY", "")
        where = f"upper(COUNTY) like '%{token}%'"
    params: dict[str, str] = {
        "where": where,
        "outFields": "*",
        "f": "json",
    }
    if limit is not None:
        params["resultRecordCount"] = str(limit)
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{urlencode(params)}"


def fetch_pennsylvania_hospitals(
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
    timeout_seconds: float = 20.0,
) -> list[dict[str, Any]]:
    url = build_pa_api_url(base_url=api_url, limit=limit, county=county)
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("unexpected_api_payload")
    rows: list[dict[str, Any]] = []
    for feature in features:
        attributes = feature.get("attributes") if isinstance(feature, dict) else None
        if isinstance(attributes, dict):
            rows.append(attributes)
    return rows


def parse_pennsylvania_hospital_row(row: dict[str, Any], *, source: str = PA_SCRAPE_SOURCE) -> ScrapedFacility | None:
    external_id = str(row.get("ID_NUMBER") or row.get("OBJECTID") or "").strip()
    name = str(row.get("NAME") or "").strip()
    if not external_id or not name:
        return None
    phone = str(row.get("TELEPHONE") or row.get("PHONE") or "").strip() or None
    zip_code = str(row.get("ZIP_CODE") or "").strip() or None
    return ScrapedFacility(
        external_source=source,
        external_id=external_id,
        name=name,
        facility_type="HOSPITAL",
        county=normalize_county(str(row.get("COUNTY") or "Pennsylvania")),
        state="PA",
        address=str(row.get("STREET") or "").strip() or None,
        city=str(row.get("CITY") or "").strip().title() or None,
        zip_code=zip_code,
        phone=phone,
    )


def parse_pennsylvania_hospital_rows(
    rows: list[dict[str, Any]],
    *,
    source: str = PA_SCRAPE_SOURCE,
) -> list[ScrapedFacility]:
    parsed: list[ScrapedFacility] = []
    for row in rows:
        facility = parse_pennsylvania_hospital_row(row, source=source)
        if facility is not None:
            parsed.append(facility)
    return parsed


def preview_pennsylvania_hospitals(
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
) -> FacilityScrapePreviewResponse:
    rows = fetch_pennsylvania_hospitals(limit=limit, county=county, api_url=api_url)
    facilities = parse_pennsylvania_hospital_rows(rows)
    return FacilityScrapePreviewResponse(
        source=PA_SCRAPE_SOURCE,
        state="PA",
        fetched=len(facilities),
        facilities=preview_to_response_rows(facilities),
    )


def scrape_and_ingest_pennsylvania_hospitals(
    db: Session,
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
) -> FacilityScrapeResponse:
    rows = fetch_pennsylvania_hospitals(limit=limit, county=county, api_url=api_url)
    facilities = parse_pennsylvania_hospital_rows(rows)
    created, updated, skipped, errors, _touched = upsert_scraped_facilities(db, facilities)
    return FacilityScrapeResponse(
        source=PA_SCRAPE_SOURCE,
        state="PA",
        fetched=len(facilities),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )
