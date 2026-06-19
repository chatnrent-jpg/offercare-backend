"""CMS Provider Data scrapers for nursing homes and home health agencies."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.schemas import FacilityScrapePreviewResponse, FacilityScrapeResponse
from app.services.maryland_facility_scraper import (
    ScrapedFacility,
    normalize_county,
    preview_to_response_rows,
    upsert_scraped_facilities,
)
from app.services.shift_offer_generator import auto_create_shifts_for_facilities

CMS_NURSING_HOME_SOURCE = "CMS_NURSING_HOME"
CMS_HOME_HEALTH_SOURCE = "CMS_HOME_HEALTH"


def _county_condition(county: str | None) -> dict[str, str] | None:
    if not county:
        return None
    token = county.strip().upper().replace(" COUNTY", "")
    return {"property": "countyparish", "value": token, "operator": "contains"}


def fetch_cms_post_acute_by_state(
    state: str,
    *,
    api_url: str,
    limit: int | None = None,
    county: str | None = None,
    timeout_seconds: float = 20.0,
) -> list[dict[str, Any]]:
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
        response = client.post(api_url, json=body)
        response.raise_for_status()
        payload = response.json()
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("unexpected_api_payload")
    return results


def parse_nursing_home_row(
    row: dict[str, Any],
    *,
    state: str,
    source: str = CMS_NURSING_HOME_SOURCE,
) -> ScrapedFacility | None:
    external_id = str(row.get("cms_certification_number_ccn") or row.get("facility_id") or "").strip()
    name = str(row.get("provider_name") or row.get("facility_name") or "").strip()
    if not external_id or not name:
        return None
    return ScrapedFacility(
        external_source=source,
        external_id=external_id,
        name=name,
        facility_type="NURSING_HOME",
        county=normalize_county(str(row.get("countyparish") or row.get("citytown") or state)),
        state=state.upper(),
        address=str(row.get("provider_address") or row.get("address") or "").strip() or None,
        city=str(row.get("citytown") or "").strip().title() or None,
        zip_code=str(row.get("zip_code") or "").strip() or None,
        phone=str(row.get("telephone_number") or "").strip() or None,
    )


def parse_home_health_row(
    row: dict[str, Any],
    *,
    state: str,
    source: str = CMS_HOME_HEALTH_SOURCE,
) -> ScrapedFacility | None:
    external_id = str(row.get("cms_certification_number_ccn") or "").strip()
    name = str(row.get("provider_name") or "").strip()
    if not external_id or not name:
        return None
    return ScrapedFacility(
        external_source=source,
        external_id=external_id,
        name=name,
        facility_type="HOME_HEALTH",
        county=normalize_county(str(row.get("countyparish") or row.get("citytown") or state)),
        state=state.upper(),
        address=str(row.get("address") or "").strip() or None,
        city=str(row.get("citytown") or "").strip().title() or None,
        zip_code=str(row.get("zip_code") or "").strip() or None,
        phone=str(row.get("telephone_number") or "").strip() or None,
    )


def _filter_by_county(facilities: list[ScrapedFacility], county: str | None) -> list[ScrapedFacility]:
    if not county:
        return facilities
    token = county.strip().lower().replace(" county", "")
    return [row for row in facilities if token in row.county.lower()]


def preview_nursing_homes(
    state: str,
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
) -> FacilityScrapePreviewResponse:
    rows = fetch_cms_post_acute_by_state(
        state,
        api_url=api_url or settings.CMS_NURSING_HOMES_API_URL,
        limit=limit,
        county=county,
    )
    facilities = _filter_by_county(
        [row for row in (parse_nursing_home_row(item, state=state) for item in rows) if row is not None],
        county,
    )
    return FacilityScrapePreviewResponse(
        source=CMS_NURSING_HOME_SOURCE,
        state=state.upper(),
        fetched=len(facilities),
        facilities=preview_to_response_rows(facilities),
    )


def _build_scrape_response(
    *,
    source: str,
    state: str,
    fetched: int,
    created: int,
    updated: int,
    skipped: int,
    errors: list[str],
    touched_facility_ids: list,
    auto_create_shifts: bool,
    db: Session,
) -> FacilityScrapeResponse:
    shifts_facilities_processed = 0
    shifts_created = 0
    matched_push_alerts_sent = 0
    if auto_create_shifts and touched_facility_ids:
        shifts_facilities_processed, shifts_created, matched_push_alerts_sent = auto_create_shifts_for_facilities(
            db,
            touched_facility_ids,
        )
    return FacilityScrapeResponse(
        source=source,
        state=state,
        fetched=fetched,
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        shifts_facilities_processed=shifts_facilities_processed,
        shifts_created=shifts_created,
        matched_push_alerts_sent=matched_push_alerts_sent,
    )


def scrape_and_ingest_nursing_homes(
    db: Session,
    state: str,
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
    auto_create_shifts: bool = False,
) -> FacilityScrapeResponse:
    rows = fetch_cms_post_acute_by_state(
        state,
        api_url=api_url or settings.CMS_NURSING_HOMES_API_URL,
        limit=limit,
        county=county,
    )
    facilities = _filter_by_county(
        [row for row in (parse_nursing_home_row(item, state=state) for item in rows) if row is not None],
        county,
    )
    created, updated, skipped, errors, touched_facility_ids = upsert_scraped_facilities(db, facilities)
    return _build_scrape_response(
        source=CMS_NURSING_HOME_SOURCE,
        state=state.upper(),
        fetched=len(facilities),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        touched_facility_ids=touched_facility_ids,
        auto_create_shifts=auto_create_shifts,
        db=db,
    )


def preview_home_health_agencies(
    state: str,
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
) -> FacilityScrapePreviewResponse:
    rows = fetch_cms_post_acute_by_state(
        state,
        api_url=api_url or settings.CMS_HOME_HEALTH_API_URL,
        limit=limit,
    )
    facilities = _filter_by_county(
        [row for row in (parse_home_health_row(item, state=state) for item in rows) if row is not None],
        county,
    )
    return FacilityScrapePreviewResponse(
        source=CMS_HOME_HEALTH_SOURCE,
        state=state.upper(),
        fetched=len(facilities),
        facilities=preview_to_response_rows(facilities),
    )


def scrape_and_ingest_home_health_agencies(
    db: Session,
    state: str,
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
    auto_create_shifts: bool = False,
) -> FacilityScrapeResponse:
    rows = fetch_cms_post_acute_by_state(
        state,
        api_url=api_url or settings.CMS_HOME_HEALTH_API_URL,
        limit=limit,
    )
    facilities = _filter_by_county(
        [row for row in (parse_home_health_row(item, state=state) for item in rows) if row is not None],
        county,
    )
    created, updated, skipped, errors, touched_facility_ids = upsert_scraped_facilities(db, facilities)
    return _build_scrape_response(
        source=CMS_HOME_HEALTH_SOURCE,
        state=state.upper(),
        fetched=len(facilities),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        touched_facility_ids=touched_facility_ids,
        auto_create_shifts=auto_create_shifts,
        db=db,
    )
