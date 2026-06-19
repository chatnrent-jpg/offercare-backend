"""Ingest Maryland hospital facilities from the state open data API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandFacility
from app.schemas import FacilityScrapePreviewRow, FacilityScrapePreviewResponse, FacilityScrapeResponse


@dataclass(frozen=True)
class ScrapedFacility:
    external_source: str
    external_id: str
    name: str
    facility_type: str
    county: str
    state: str
    address: str | None
    city: str | None
    zip_code: str | None
    phone: str | None


def preview_to_response_rows(facilities: list[ScrapedFacility]) -> list[FacilityScrapePreviewRow]:
    return [
        FacilityScrapePreviewRow(
            external_id=row.external_id,
            name=row.name,
            facility_type=row.facility_type,
            county=row.county,
            state=row.state,
            city=row.city,
            address=row.address,
            phone=row.phone,
        )
        for row in facilities
    ]


def normalize_county(raw: str) -> str:
    text = str(raw or "").strip().title()
    text = text.replace("'S", "'s")
    if text and "county" not in text.lower():
        text = f"{text} County"
    return text


def map_facility_type(raw: str) -> str:
    from app.services.care_taxonomy import map_scraped_facility_type

    return map_scraped_facility_type(raw)


def parse_hospital_row(row: dict[str, Any], *, source: str) -> ScrapedFacility | None:
    external_id = str(row.get("ccn") or row.get("objectid") or "").strip()
    name = str(row.get("facility_name") or "").strip()
    if not external_id or not name:
        return None

    return ScrapedFacility(
        external_source=source,
        external_id=external_id,
        name=name,
        facility_type=map_facility_type(str(row.get("type") or "")),
        county=normalize_county(str(row.get("county") or "Maryland")),
        state="MD",
        address=str(row.get("facility_address") or "").strip() or None,
        city=str(row.get("facility_city") or "").strip().title() or None,
        zip_code=str(row.get("facility_zip") or "").strip() or None,
        phone=str(row.get("facility_phone") or "").strip() or None,
    )


def build_api_url(
    *,
    base_url: str | None = None,
    limit: int | None = None,
    county: str | None = None,
) -> str:
    params: dict[str, str] = {}
    if limit is not None:
        params["$limit"] = str(limit)
    if county:
        params["$where"] = f"upper(county) like '%{county.strip().upper()}%'"
    url = base_url or settings.MARYLAND_HOSPITALS_API_URL
    if not params:
        return url
    return f"{url}?{urlencode(params)}"


def fetch_maryland_hospitals(
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
    timeout_seconds: float = 20.0,
) -> list[dict[str, Any]]:
    url = build_api_url(base_url=api_url, limit=limit, county=county)
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("unexpected_api_payload")
    return payload


def parse_hospital_rows(
    rows: list[dict[str, Any]],
    *,
    source: str | None = None,
) -> list[ScrapedFacility]:
    source_name = source or settings.FACILITY_SCRAPE_SOURCE
    parsed: list[ScrapedFacility] = []
    for row in rows:
        facility = parse_hospital_row(row, source=source_name)
        if facility is not None:
            parsed.append(facility)
    return parsed


def preview_maryland_hospitals(
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
) -> FacilityScrapePreviewResponse:
    rows = fetch_maryland_hospitals(limit=limit, county=county, api_url=api_url)
    facilities = parse_hospital_rows(rows)
    return FacilityScrapePreviewResponse(
        source=settings.FACILITY_SCRAPE_SOURCE,
        state="MD",
        fetched=len(facilities),
        facilities=preview_to_response_rows(facilities),
    )


def upsert_scraped_facilities(
    db: Session,
    facilities: list[ScrapedFacility],
) -> tuple[int, int, int, list[str], list[UUID]]:
    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    touched_facility_ids: list[UUID] = []

    for row in facilities:
        try:
            existing = (
                db.query(MarylandFacility)
                .filter(
                    MarylandFacility.external_source == row.external_source,
                    MarylandFacility.external_id == row.external_id,
                )
                .first()
            )
            if existing is None:
                facility = MarylandFacility(
                    name=row.name,
                    facility_type=row.facility_type,
                    county=row.county,
                    state=row.state,
                    vms_integration_type="SCRAPE",
                    external_source=row.external_source,
                    external_id=row.external_id,
                    address=row.address,
                    city=row.city,
                    zip_code=row.zip_code,
                    phone=row.phone,
                )
                db.add(facility)
                db.flush()
                touched_facility_ids.append(facility.facility_id)
                created += 1
                continue

            changed = False
            for field, value in (
                ("name", row.name),
                ("facility_type", row.facility_type),
                ("county", row.county),
                ("state", row.state),
                ("address", row.address),
                ("city", row.city),
                ("zip_code", row.zip_code),
                ("phone", row.phone),
            ):
                if getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed = True
            if changed:
                updated += 1
                touched_facility_ids.append(existing.facility_id)
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001 - collect row-level ingest failures
            errors.append(f"{row.external_id}:{row.name} -> {exc}")
            skipped += 1

    if created or updated:
        db.commit()
    return created, updated, skipped, errors, touched_facility_ids


def scrape_and_ingest_maryland_hospitals(
    db: Session,
    *,
    limit: int | None = None,
    county: str | None = None,
    api_url: str | None = None,
) -> FacilityScrapeResponse:
    rows = fetch_maryland_hospitals(limit=limit, county=county, api_url=api_url)
    facilities = parse_hospital_rows(rows)
    created, updated, skipped, errors, _touched = upsert_scraped_facilities(db, facilities)
    return FacilityScrapeResponse(
        source=settings.FACILITY_SCRAPE_SOURCE,
        state="MD",
        fetched=len(facilities),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )
