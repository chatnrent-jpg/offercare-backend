from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility
from app.schemas import FacilityScrapeResponse
from app.services.cms_post_acute_scraper import (
    CMS_HOME_HEALTH_SOURCE,
    CMS_NURSING_HOME_SOURCE,
    parse_home_health_row,
    parse_nursing_home_row,
    preview_home_health_agencies,
    preview_nursing_homes,
    scrape_and_ingest_home_health_agencies,
    scrape_and_ingest_nursing_homes,
)
from app.services.post_acute_scrape_expansion import scrape_and_ingest_post_acute_mid_atlantic

NURSING_HOME_SAMPLE = {
    "cms_certification_number_ccn": "215001",
    "provider_name": "AUTUMN LAKE HEALTHCARE AT BALLENGER CREEK",
    "provider_address": "347 BALLENGER DRIVE",
    "citytown": "FREDERICK",
    "state": "MD",
    "zip_code": "21701",
    "telephone_number": "3016635181",
    "countyparish": "Frederick",
    "provider_type": "Medicare and Medicaid",
}

HOME_HEALTH_SAMPLE = {
    "state": "MD",
    "cms_certification_number_ccn": "217008",
    "provider_name": "VNA OF MARYLAND",
    "address": "400 RED BROOK BLVD SUITE 220",
    "citytown": "OWINGS MILLS",
    "zip_code": "21117",
    "telephone_number": "4105942600",
}


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_parse_nursing_home_row() -> None:
    parsed = parse_nursing_home_row(NURSING_HOME_SAMPLE, state="MD")
    assert parsed is not None
    assert parsed.facility_type == "NURSING_HOME"
    assert parsed.external_source == CMS_NURSING_HOME_SOURCE
    assert parsed.state == "MD"
    assert parsed.county == "Frederick County"


def test_parse_home_health_row() -> None:
    parsed = parse_home_health_row(HOME_HEALTH_SAMPLE, state="MD")
    assert parsed is not None
    assert parsed.facility_type == "HOME_HEALTH"
    assert parsed.external_source == CMS_HOME_HEALTH_SOURCE
    assert parsed.name == "VNA OF MARYLAND"


@patch("app.services.cms_post_acute_scraper.fetch_cms_post_acute_by_state")
def test_scrape_and_ingest_nursing_homes(mock_fetch, db: Session) -> None:
    token = uuid.uuid4().hex[:4]
    mock_fetch.return_value = [
        {**NURSING_HOME_SAMPLE, "cms_certification_number_ccn": f"21{token}"},
    ]
    result = scrape_and_ingest_nursing_homes(db, "MD", limit=1)
    assert result.state == "MD"
    assert result.fetched == 1
    assert result.created == 1
    row = (
        db.query(MarylandFacility)
        .filter(
            MarylandFacility.external_source == CMS_NURSING_HOME_SOURCE,
            MarylandFacility.external_id == f"21{token}",
        )
        .one()
    )
    assert row.facility_type == "NURSING_HOME"


@patch("app.services.cms_post_acute_scraper.fetch_cms_post_acute_by_state")
def test_scrape_and_ingest_home_health_agencies(mock_fetch, db: Session) -> None:
    token = uuid.uuid4().hex[:4]
    mock_fetch.return_value = [
        {**HOME_HEALTH_SAMPLE, "cms_certification_number_ccn": f"21{token}"},
    ]
    result = scrape_and_ingest_home_health_agencies(db, "MD", limit=1)
    assert result.state == "MD"
    assert result.fetched == 1
    assert result.created == 1
    row = (
        db.query(MarylandFacility)
        .filter(
            MarylandFacility.external_source == CMS_HOME_HEALTH_SOURCE,
            MarylandFacility.external_id == f"21{token}",
        )
        .one()
    )
    assert row.facility_type == "HOME_HEALTH"


@patch("app.services.cms_post_acute_scraper.fetch_cms_post_acute_by_state", return_value=[NURSING_HOME_SAMPLE])
def test_preview_nursing_homes(mock_fetch) -> None:
    preview = preview_nursing_homes("MD", limit=1)
    assert preview.state == "MD"
    assert preview.fetched == 1
    assert preview.facilities[0].facility_type == "NURSING_HOME"


@patch("app.services.cms_post_acute_scraper.fetch_cms_post_acute_by_state", return_value=[HOME_HEALTH_SAMPLE])
def test_preview_home_health_agencies(mock_fetch) -> None:
    preview = preview_home_health_agencies("MD", limit=1)
    assert preview.state == "MD"
    assert preview.fetched == 1
    assert preview.facilities[0].facility_type == "HOME_HEALTH"


@patch("app.routers.scraper.scrape_and_ingest_nursing_homes")
def test_nursing_home_ingest_endpoint(mock_ingest, client: TestClient) -> None:
    mock_ingest.return_value = FacilityScrapeResponse(
        source=CMS_NURSING_HOME_SOURCE,
        state="MD",
        fetched=2,
        created=2,
        updated=0,
        skipped=0,
    )
    response = client.post("/api/scrape/nursing-homes", json={"limit": 2, "state": "MD"})
    assert response.status_code == 200
    assert response.json()["state"] == "MD"


@patch("app.routers.scraper.scrape_and_ingest_home_health_agencies")
def test_home_health_ingest_endpoint(mock_ingest, client: TestClient) -> None:
    mock_ingest.return_value = FacilityScrapeResponse(
        source=CMS_HOME_HEALTH_SOURCE,
        state="MD",
        fetched=2,
        created=2,
        updated=0,
        skipped=0,
    )
    response = client.post("/api/scrape/home-health-agencies", json={"limit": 2, "state": "MD"})
    assert response.status_code == 200
    assert response.json()["state"] == "MD"


@patch("app.services.post_acute_scrape_expansion.scrape_and_ingest_nursing_homes")
@patch("app.services.post_acute_scrape_expansion.scrape_and_ingest_home_health_agencies")
def test_post_acute_mid_atlantic_expansion(mock_home_health, mock_nursing, db: Session) -> None:
    mock_nursing.return_value = FacilityScrapeResponse(
        source=CMS_NURSING_HOME_SOURCE,
        state="MD",
        fetched=1,
        created=1,
        updated=0,
        skipped=0,
    )
    mock_home_health.return_value = FacilityScrapeResponse(
        source=CMS_HOME_HEALTH_SOURCE,
        state="MD",
        fetched=1,
        created=1,
        updated=0,
        skipped=0,
    )
    result = scrape_and_ingest_post_acute_mid_atlantic(db, limit=1)
    assert result.fetched == 12
    assert mock_nursing.call_count == 6
    assert mock_home_health.call_count == 6


@patch("app.routers.scraper.scrape_and_ingest_post_acute_mid_atlantic")
def test_post_acute_mid_atlantic_endpoint(mock_ingest, client: TestClient) -> None:
    from app.services.post_acute_scrape_expansion import PostAcuteExpansionResult

    mock_ingest.return_value = PostAcuteExpansionResult(
        nursing_homes=FacilityScrapeResponse(
            source=CMS_NURSING_HOME_SOURCE,
            state="MID_ATLANTIC",
            fetched=5,
            created=5,
            updated=0,
            skipped=0,
        ),
        home_health=FacilityScrapeResponse(
            source=CMS_HOME_HEALTH_SOURCE,
            state="MID_ATLANTIC",
            fetched=5,
            created=5,
            updated=0,
            skipped=0,
        ),
    )
    response = client.post("/api/scrape/post-acute-mid-atlantic", json={"limit": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["nursing_homes"]["fetched"] == 5
    assert body["home_health"]["fetched"] == 5


def test_admin_dashboard_includes_post_acute_scrape_buttons(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "scrape-nursing-homes-btn" in html.text
    assert "scrape-home-health-btn" in html.text
    assert "scrape-post-acute-btn" in html.text
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "/api/scrape/nursing-homes" in js.text
    assert "/api/scrape/home-health-agencies" in js.text


def test_env_example_documents_post_acute_scrape() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "CMS_NURSING_HOMES_API_URL" in text
    assert "CMS_HOME_HEALTH_API_URL" in text
