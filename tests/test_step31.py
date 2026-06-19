from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility
from app.services.de_facility_scraper import (
    DE_SCRAPE_SOURCE,
    parse_delaware_hospital_row,
    parse_delaware_hospital_rows,
    preview_delaware_hospitals,
    scrape_and_ingest_delaware_hospitals,
)
from app.services.facility_scrape_expansion import scrape_and_ingest_expansion_states
from app.services.maryland_facility_scraper import normalize_county, upsert_scraped_facilities
from app.services.pa_facility_scraper import (
    PA_SCRAPE_SOURCE,
    parse_pennsylvania_hospital_row,
    parse_pennsylvania_hospital_rows,
    preview_pennsylvania_hospitals,
    scrape_and_ingest_pennsylvania_hospitals,
)
from app.services.states import supported_states

PA_SAMPLE = {
    "ID_NUMBER": "29530100",
    "NAME": "Canonsburg Hospital",
    "STREET": "100 Medical Boulevard",
    "CITY": "Canonsburg",
    "COUNTY": "Washington",
    "ZIP_CODE": "15317",
    "TELEPHONE": "724-745-6100",
    "OBJECTID": 1,
}

DE_SAMPLE = {
    "facility_id": "080001",
    "facility_name": "CHRISTIANA HOSPITAL",
    "address": "4755 OGLETOWN-STANTON ROAD",
    "citytown": "NEWARK",
    "state": "DE",
    "zip_code": "19718",
    "countyparish": "NEW CASTLE",
    "telephone_number": "(302) 733-3609",
    "hospital_type": "Acute Care Hospitals",
}


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_supported_states_include_pa_and_de() -> None:
    states = supported_states()
    assert "PA" in states
    assert "DE" in states


def test_normalize_county_adds_suffix_when_missing() -> None:
    assert normalize_county("WASHINGTON") == "Washington County"
    assert normalize_county("Prince George's County") == "Prince George's County"


def test_parse_pennsylvania_hospital_row() -> None:
    parsed = parse_pennsylvania_hospital_row(PA_SAMPLE)
    assert parsed is not None
    assert parsed.external_id == "29530100"
    assert parsed.state == "PA"
    assert parsed.external_source == PA_SCRAPE_SOURCE
    assert parsed.county == "Washington County"
    assert parsed.city == "Canonsburg"


def test_parse_delaware_hospital_row() -> None:
    parsed = parse_delaware_hospital_row(DE_SAMPLE)
    assert parsed is not None
    assert parsed.external_id == "080001"
    assert parsed.state == "DE"
    assert parsed.external_source == DE_SCRAPE_SOURCE
    assert parsed.county == "New Castle County"
    assert parsed.facility_type == "HOSPITAL"


@patch("app.services.pa_facility_scraper.fetch_pennsylvania_hospitals")
def test_scrape_and_ingest_pennsylvania(mock_fetch, db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    mock_fetch.return_value = [{**PA_SAMPLE, "ID_NUMBER": f"PA{token}"}]
    result = scrape_and_ingest_pennsylvania_hospitals(db, limit=1)
    assert result.state == "PA"
    assert result.fetched == 1
    assert result.created == 1
    row = (
        db.query(MarylandFacility)
        .filter(
            MarylandFacility.external_source == PA_SCRAPE_SOURCE,
            MarylandFacility.external_id == f"PA{token}",
        )
        .one()
    )
    assert row.state == "PA"


@patch("app.services.cms_hospital_scraper.fetch_cms_hospitals_by_state")
def test_scrape_and_ingest_delaware(mock_fetch, db: Session) -> None:
    token = uuid.uuid4().hex[:4]
    mock_fetch.return_value = [{**DE_SAMPLE, "facility_id": f"08{token}"}]
    result = scrape_and_ingest_delaware_hospitals(db, limit=1)
    assert result.state == "DE"
    assert result.fetched == 1
    assert result.created == 1
    row = (
        db.query(MarylandFacility)
        .filter(
            MarylandFacility.external_source == DE_SCRAPE_SOURCE,
            MarylandFacility.external_id == f"08{token}",
        )
        .one()
    )
    assert row.state == "DE"


@patch("app.services.facility_scrape_expansion.scrape_and_ingest_pennsylvania_hospitals")
@patch("app.services.facility_scrape_expansion.scrape_and_ingest_delaware_hospitals")
@patch("app.services.facility_scrape_expansion.scrape_and_ingest_new_jersey_hospitals")
def test_expansion_scrape_service(mock_nj, mock_de, mock_pa, db: Session) -> None:
    from app.schemas import FacilityScrapeResponse

    mock_pa.return_value = FacilityScrapeResponse(
        source=PA_SCRAPE_SOURCE,
        state="PA",
        fetched=2,
        created=2,
        updated=0,
        skipped=0,
    )
    mock_de.return_value = FacilityScrapeResponse(
        source=DE_SCRAPE_SOURCE,
        state="DE",
        fetched=1,
        created=1,
        updated=0,
        skipped=0,
    )
    mock_nj.return_value = FacilityScrapeResponse(
        source="CMS_HOSPITAL_INFO",
        state="NJ",
        fetched=3,
        created=3,
        updated=0,
        skipped=0,
    )
    result = scrape_and_ingest_expansion_states(db, limit=25)
    assert result.fetched == 6
    assert result.created == 6


@patch("app.routers.scraper.scrape_and_ingest_pennsylvania_hospitals")
def test_pennsylvania_ingest_endpoint(mock_ingest, client: TestClient) -> None:
    from app.schemas import FacilityScrapeResponse

    mock_ingest.return_value = FacilityScrapeResponse(
        source=PA_SCRAPE_SOURCE,
        state="PA",
        fetched=2,
        created=2,
        updated=0,
        skipped=0,
    )
    response = client.post("/api/scrape/pennsylvania-hospitals", json={"limit": 2})
    assert response.status_code == 200
    assert response.json()["state"] == "PA"


@patch("app.routers.scraper.scrape_and_ingest_delaware_hospitals")
def test_delaware_ingest_endpoint(mock_ingest, client: TestClient) -> None:
    from app.schemas import FacilityScrapeResponse

    mock_ingest.return_value = FacilityScrapeResponse(
        source=DE_SCRAPE_SOURCE,
        state="DE",
        fetched=1,
        created=1,
        updated=0,
        skipped=0,
    )
    response = client.post("/api/scrape/delaware-hospitals", json={"limit": 1})
    assert response.status_code == 200
    assert response.json()["state"] == "DE"


@patch("app.services.pa_facility_scraper.fetch_pennsylvania_hospitals", return_value=[PA_SAMPLE])
def test_pennsylvania_preview_service(mock_fetch) -> None:
    preview = preview_pennsylvania_hospitals(limit=1)
    assert preview.state == "PA"
    assert preview.fetched == 1
    assert preview.facilities[0].state == "PA"


@patch("app.services.cms_hospital_scraper.fetch_cms_hospitals_by_state", return_value=[DE_SAMPLE])
def test_delaware_preview_service(mock_fetch) -> None:
    preview = preview_delaware_hospitals(limit=1)
    assert preview.state == "DE"
    assert preview.fetched == 1
    assert preview.facilities[0].state == "DE"


def test_admin_dashboard_includes_pa_de_scrape_buttons(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "scrape-pa-btn" in html.text
    assert "scrape-de-btn" in html.text
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "pennsylvania-hospitals" in js.text
    assert "delaware-hospitals" in js.text


def test_env_example_documents_pa_de_scrape() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "PA_HOSPITALS_API_URL" in text
    assert "DE_HOSPITALS_API_URL" in text
    assert "PA,DE,NJ" in text
