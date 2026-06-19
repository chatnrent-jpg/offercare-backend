from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility, OfferCareJobOffer
from app.schemas import FacilityScrapeResponse
from app.services.care_taxonomy import shift_templates_for_facility_type
from app.services.cms_post_acute_scraper import CMS_NURSING_HOME_SOURCE, scrape_and_ingest_nursing_homes
from app.services.deploy_walkthrough import build_deploy_checklist
from app.services.shift_offer_generator import auto_create_shifts_for_facilities
from app.seed import seed_va_nursing_home_demo
from tests.test_step37 import NURSING_HOME_SAMPLE


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@patch("app.services.cms_post_acute_scraper.fetch_cms_post_acute_by_state")
def test_post_acute_scrape_auto_creates_shifts(mock_fetch, db: Session) -> None:
    token = uuid.uuid4().hex[:4]
    mock_fetch.return_value = [
        {**NURSING_HOME_SAMPLE, "cms_certification_number_ccn": f"38{token}"},
    ]
    result = scrape_and_ingest_nursing_homes(db, "MD", limit=1, auto_create_shifts=True)
    assert result.created == 1
    assert result.shifts_facilities_processed == 1
    expected_roles = {role for role, _rate in shift_templates_for_facility_type("NURSING_HOME")}
    row = (
        db.query(MarylandFacility)
        .filter(
            MarylandFacility.external_source == CMS_NURSING_HOME_SOURCE,
            MarylandFacility.external_id == f"38{token}",
        )
        .one()
    )
    offers = (
        db.query(OfferCareJobOffer)
        .filter(
            OfferCareJobOffer.facility_id == row.facility_id,
            OfferCareJobOffer.compliance_lock_status == "BROADCASTING",
        )
        .all()
    )
    assert result.shifts_created == len(offers)
    assert {offer.shift_role for offer in offers} == expected_roles


def test_auto_create_shifts_for_facilities_skips_existing_roles(db: Session) -> None:
    facility = MarylandFacility(
        name=f"Step38 SNF {uuid.uuid4().hex[:6]}",
        facility_type="NURSING_HOME",
        county="Howard County",
        state="MD",
        vms_integration_type="SCRAPE",
    )
    db.add(facility)
    db.flush()
    first_pass_facilities, first_pass_offers, _first_push = auto_create_shifts_for_facilities(db, [facility.facility_id])
    second_pass_facilities, second_pass_offers, _second_push = auto_create_shifts_for_facilities(db, [facility.facility_id])
    assert first_pass_facilities == 1
    assert first_pass_offers > 0
    assert second_pass_facilities == 1
    assert second_pass_offers == 0


def test_va_nursing_home_seed_creates_post_acute_demo(db: Session) -> None:
    payload = seed_va_nursing_home_demo(db)
    assert payload["state"] == "VA"
    assert payload["facility_type"] == "NURSING_HOME"
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.name == "Virginia SNF at Arlington")
        .one()
    )
    assert facility.state == "VA"
    assert facility.facility_type == "NURSING_HOME"


def test_va_nursing_home_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/va-nursing-home")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "VA"
    assert body["facility_type"] == "NURSING_HOME"


def test_deploy_checklist_includes_post_acute_scrape(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    body = response.json()
    ids = {row["id"] for row in body["items"]}
    assert "cms_post_acute_scrape" in ids
    assert body["post_acute_steps"]


def test_deploy_checklist_cms_post_acute_ready(db: Session) -> None:
    snapshot = build_deploy_checklist(db)
    cms_item = next(row for row in snapshot["items"] if row["id"] == "cms_post_acute_scrape")
    assert cms_item["status"] == "ready"


@patch("app.routers.scraper.scrape_and_ingest_nursing_homes")
def test_nursing_home_scrape_passes_auto_create_flag(mock_ingest, client: TestClient) -> None:
    mock_ingest.return_value = FacilityScrapeResponse(
        source=CMS_NURSING_HOME_SOURCE,
        state="MD",
        fetched=1,
        created=1,
        updated=0,
        skipped=0,
        shifts_facilities_processed=1,
        shifts_created=3,
    )
    response = client.post(
        "/api/scrape/nursing-homes",
        json={"limit": 1, "state": "MD", "auto_create_shifts": True},
    )
    assert response.status_code == 200
    assert response.json()["shifts_created"] == 3
    mock_ingest.assert_called_once()
    assert mock_ingest.call_args.kwargs["auto_create_shifts"] is True


def test_admin_dashboard_includes_va_nursing_home_seed(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "seed-va-nursing-home-btn" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/va-nursing-home" in js.text
    assert "auto_create_shifts" in js.text
