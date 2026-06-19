"""Ingest New Jersey hospital facilities from CMS Hospital General Information."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.schemas import FacilityScrapePreviewResponse, FacilityScrapeResponse
from app.services.cms_hospital_scraper import (
    CMS_SCRAPE_SOURCE,
    fetch_cms_hospitals_by_state,
    parse_cms_hospital_row,
    parse_cms_hospital_rows,
    preview_cms_hospitals,
    scrape_and_ingest_cms_hospitals,
)

NJ_SCRAPE_SOURCE = CMS_SCRAPE_SOURCE
_NJ_STATE = "NJ"


def fetch_new_jersey_hospitals(
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
    timeout_seconds: float = 20.0,
) -> list[dict[str, Any]]:
    return fetch_cms_hospitals_by_state(
        _NJ_STATE,
        limit=limit,
        county=county,
        api_url=api_url,
        timeout_seconds=timeout_seconds,
    )


def parse_new_jersey_hospital_row(row: dict[str, Any], *, source: str = NJ_SCRAPE_SOURCE):
    return parse_cms_hospital_row(row, state=_NJ_STATE, source=source)


def parse_new_jersey_hospital_rows(
    rows: list[dict[str, Any]],
    *,
    source: str = NJ_SCRAPE_SOURCE,
):
    return parse_cms_hospital_rows(rows, state=_NJ_STATE, source=source)


def preview_new_jersey_hospitals(
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
) -> FacilityScrapePreviewResponse:
    return preview_cms_hospitals(_NJ_STATE, limit=limit, county=county, api_url=api_url)


def scrape_and_ingest_new_jersey_hospitals(
    db: Session,
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
) -> FacilityScrapeResponse:
    return scrape_and_ingest_cms_hospitals(
        db,
        _NJ_STATE,
        limit=limit,
        county=county,
        api_url=api_url,
    )
