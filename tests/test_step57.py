from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    build_demo_environment_status,
    get_demo_hint_for_offer,
    run_full_demo_setup,
)
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_demo_status_includes_matched_clinician_per_offer(db: Session) -> None:
    run_full_demo_setup(db)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    saint_jude = next(row for row in status["offers"] if row["facility_name"] == "Saint Jude's ICU")
    assert nj_offer["demo_clinician_email"] == "nj.snf.cna.a@offercare.demo"
    assert nj_offer["demo_clinician_name"]
    assert saint_jude["demo_clinician_email"] == "nurse.a@offercare.demo"


def test_get_demo_hint_for_offer_returns_login_details(db: Session) -> None:
    run_full_demo_setup(db)
    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    hint = get_demo_hint_for_offer(db, UUID(nj_offer["offer_id"]))
    assert hint is not None
    assert hint["clinician_email"] == "nj.snf.cna.a@offercare.demo"
    assert hint["portal_password_hint"] == DEMO_PORTAL_PASSWORD
    assert hint["facility_name"] == "Paramus SNF at Bergen"


def test_get_demo_hint_for_offer_rejects_non_demo_facility(db: Session) -> None:
    from app.models import MarylandFacility, OfferCareJobOffer

    facility = MarylandFacility(
        name="Non Demo Hospital",
        facility_type="HOSPITAL",
        county="Test",
        state="MD",
        vms_integration_type="SCRAPE",
    )
    db.add(facility)
    db.flush()
    offer = OfferCareJobOffer(
        facility_id=facility.facility_id,
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
        compliance_lock_status="BROADCASTING",
    )
    db.add(offer)
    db.commit()
    assert get_demo_hint_for_offer(db, offer.offer_id) is None


def test_portal_demo_hint_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup")
    status = client.get("/api/seed/demo-status").json()
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    response = client.get(f"/api/portal/demo-hint?offer_id={nj_offer['offer_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["clinician_email"] == "nj.snf.cna.a@offercare.demo"
    assert body["portal_password_hint"] == DEMO_PORTAL_PASSWORD


def test_portal_page_includes_demo_hint_banner(client: TestClient) -> None:
    html = client.get("/portal/")
    assert html.status_code == 200
    assert "demo-hint-banner" in html.text
    js = client.get("/portal/app.js")
    assert "/api/portal/demo-hint" in js.text
    assert "loadDemoHint" in js.text


def test_demo_links_include_matched_clinician_email(client: TestClient) -> None:
    client.post("/api/seed/demo-setup")
    response = client.get("/api/seed/demo-links")
    assert response.status_code == 200
    nj_link = next(row for row in response.json()["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    assert nj_link["demo_clinician_email"] == "nj.snf.cna.a@offercare.demo"


def test_admin_dashboard_renders_demo_as_column(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert "demo_clinician_email" in js.text
    assert "Demo as" in js.text


def test_deploy_checklist_mentions_demo_clinician_prefill(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("pre-fills" in step.lower() or "matched" in step.lower() for step in steps)
