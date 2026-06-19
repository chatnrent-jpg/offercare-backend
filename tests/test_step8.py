from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility
from app.services.maryland_facility_scraper import (
    normalize_county,
    parse_hospital_row,
    parse_hospital_rows,
    preview_maryland_hospitals,
    scrape_and_ingest_maryland_hospitals,
    upsert_scraped_facilities,
)

SAMPLE_ROWS = [
    {
        "objectid": "114",
        "county": "PRINCE GEORGE'S COUNTY",
        "facility_name": "FORT WASHINGTON HOSPITAL",
        "facility_address": "11711 LIVINGSTON ROAD",
        "facility_city": "FORT WASHINGTON",
        "facility_zip": "20744",
        "facility_phone": "(301) 292-7000",
        "ccn": "210060",
        "type": "Acute, General and Special Hospitals",
    },
    {
        "objectid": "106",
        "county": "MONTGOMERY COUNTY",
        "facility_name": "ADVENTIST HEALTHCARE SHADY GROVE MEDICAL CENTER",
        "facility_address": "9901 MEDICAL CENTER DRIVE",
        "facility_city": "ROCKVILLE",
        "facility_zip": "20850",
        "facility_phone": "(240) 826-6517",
        "ccn": "210057",
        "type": "Acute, General and Special Hospitals",
    },
]


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_normalize_county() -> None:
    assert normalize_county("PRINCE GEORGE'S COUNTY") == "Prince George's County"


def test_parse_hospital_row() -> None:
    parsed = parse_hospital_row(SAMPLE_ROWS[0], source="MD_OPENDATA")
    assert parsed is not None
    assert parsed.external_id == "210060"
    assert parsed.name == "FORT WASHINGTON HOSPITAL"
    assert parsed.facility_type == "HOSPITAL"
    assert parsed.county == "Prince George's County"
    assert parsed.city == "Fort Washington"


def test_upsert_creates_and_updates(db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    rows = [
        {**SAMPLE_ROWS[0], "ccn": f"88{token}1", "objectid": f"88{token}1"},
        {**SAMPLE_ROWS[1], "ccn": f"88{token}2", "objectid": f"88{token}2"},
    ]
    facilities = parse_hospital_rows(rows)
    created, updated, skipped, errors, _touched = upsert_scraped_facilities(db, facilities)
    assert created == 2
    assert updated == 0
    assert skipped == 0
    assert not errors

    row = (
        db.query(MarylandFacility)
        .filter(
            MarylandFacility.external_source == "MD_OPENDATA",
            MarylandFacility.external_id == f"88{token}1",
        )
        .first()
    )
    assert row is not None
    assert row.name == "FORT WASHINGTON HOSPITAL"

    updated_facility = parse_hospital_row(
        {**rows[0], "facility_name": "FORT WASHINGTON MEDICAL CENTER"},
        source="MD_OPENDATA",
    )
    assert updated_facility is not None
    created, updated, skipped, errors, _touched = upsert_scraped_facilities(db, [updated_facility])
    assert created == 0
    assert updated == 1
    assert row.name == "FORT WASHINGTON MEDICAL CENTER"


@patch("app.services.maryland_facility_scraper.fetch_maryland_hospitals")
def test_scrape_and_ingest_service(mock_fetch, db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    mock_fetch.return_value = [
        {**SAMPLE_ROWS[0], "ccn": f"99{token}1", "objectid": f"99{token}1"},
        {**SAMPLE_ROWS[1], "ccn": f"99{token}2", "objectid": f"99{token}2"},
    ]
    result = scrape_and_ingest_maryland_hospitals(db, limit=2)
    assert result.fetched == 2
    assert result.created == 2
    mock_fetch.assert_called_once()


@patch("app.services.maryland_facility_scraper.fetch_maryland_hospitals", return_value=SAMPLE_ROWS)
def test_preview_service(mock_fetch) -> None:
    preview = preview_maryland_hospitals(limit=2)
    assert preview.fetched == 2
    assert preview.facilities[0].external_id == "210060"
    mock_fetch.assert_called_once()


@patch("app.routers.scraper.preview_maryland_hospitals")
def test_preview_endpoint(mock_preview, client: TestClient) -> None:
    from app.schemas import FacilityScrapePreviewResponse, FacilityScrapePreviewRow

    mock_preview.return_value = FacilityScrapePreviewResponse(
        source="MD_OPENDATA",
        fetched=1,
        facilities=[
            FacilityScrapePreviewRow(
                external_id="210060",
                name="FORT WASHINGTON HOSPITAL",
                facility_type="HOSPITAL",
                county="Prince George's County",
            )
        ],
    )
    response = client.get("/api/scrape/maryland-hospitals/preview?limit=1")
    assert response.status_code == 200
    assert response.json()["fetched"] == 1


@patch("app.routers.scraper.scrape_and_ingest_maryland_hospitals")
def test_ingest_endpoint(mock_ingest, client: TestClient) -> None:
    from app.schemas import FacilityScrapeResponse

    mock_ingest.return_value = FacilityScrapeResponse(
        source="MD_OPENDATA",
        fetched=2,
        created=2,
        updated=0,
        skipped=0,
    )
    response = client.post("/api/scrape/maryland-hospitals", json={"limit": 2})
    assert response.status_code == 200
    assert response.json()["created"] == 2
