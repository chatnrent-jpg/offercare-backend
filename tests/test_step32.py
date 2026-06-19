from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility
from app.services.cms_hospital_scraper import CMS_SCRAPE_SOURCE, parse_cms_hospital_row
from app.services.nj_facility_scraper import (
    NJ_SCRAPE_SOURCE,
    parse_new_jersey_hospital_row,
    preview_new_jersey_hospitals,
    scrape_and_ingest_new_jersey_hospitals,
)
from app.services.states import supported_states

NJ_SAMPLE = {
    "facility_id": "310001",
    "facility_name": "HACKENSACK UNIVERSITY MEDICAL CENTER",
    "address": "30 PROSPECT AVENUE",
    "citytown": "HACKENSACK",
    "state": "NJ",
    "zip_code": "07601",
    "countyparish": "BERGEN",
    "telephone_number": "(551) 996-2000",
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


def test_supported_states_include_new_jersey() -> None:
    assert "NJ" in supported_states()


def test_parse_cms_hospital_row_for_new_jersey() -> None:
    parsed = parse_cms_hospital_row(NJ_SAMPLE, state="NJ")
    assert parsed is not None
    assert parsed.state == "NJ"
    assert parsed.external_source == CMS_SCRAPE_SOURCE
    assert parsed.county == "Bergen County"


def test_parse_new_jersey_hospital_row_wrapper() -> None:
    parsed = parse_new_jersey_hospital_row(NJ_SAMPLE)
    assert parsed is not None
    assert parsed.external_source == NJ_SCRAPE_SOURCE
    assert parsed.name == "HACKENSACK UNIVERSITY MEDICAL CENTER"


@patch("app.services.cms_hospital_scraper.fetch_cms_hospitals_by_state")
def test_scrape_and_ingest_new_jersey(mock_fetch, db: Session) -> None:
    token = uuid.uuid4().hex[:4]
    mock_fetch.return_value = [{**NJ_SAMPLE, "facility_id": f"31{token}"}]
    result = scrape_and_ingest_new_jersey_hospitals(db, limit=1)
    assert result.state == "NJ"
    assert result.fetched == 1
    assert result.created == 1
    row = (
        db.query(MarylandFacility)
        .filter(
            MarylandFacility.external_source == NJ_SCRAPE_SOURCE,
            MarylandFacility.external_id == f"31{token}",
        )
        .one()
    )
    assert row.state == "NJ"


@patch("app.routers.scraper.scrape_and_ingest_new_jersey_hospitals")
def test_new_jersey_ingest_endpoint(mock_ingest, client: TestClient) -> None:
    from app.schemas import FacilityScrapeResponse

    mock_ingest.return_value = FacilityScrapeResponse(
        source=NJ_SCRAPE_SOURCE,
        state="NJ",
        fetched=2,
        created=2,
        updated=0,
        skipped=0,
    )
    response = client.post("/api/scrape/new-jersey-hospitals", json={"limit": 2})
    assert response.status_code == 200
    assert response.json()["state"] == "NJ"


@patch("app.services.cms_hospital_scraper.fetch_cms_hospitals_by_state", return_value=[NJ_SAMPLE])
def test_new_jersey_preview_service(mock_fetch) -> None:
    preview = preview_new_jersey_hospitals(limit=1)
    assert preview.state == "NJ"
    assert preview.fetched == 1
    assert preview.facilities[0].state == "NJ"


def test_admin_dashboard_includes_nj_scrape_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "scrape-nj-btn" in html.text
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "new-jersey-hospitals" in js.text


def test_env_example_documents_nj_scrape() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "NJ_HOSPITALS_API_URL" in text
    assert "CMS_HOSPITALS_API_URL" in text
    assert "NJ" in text
