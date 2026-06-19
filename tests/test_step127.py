from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import FacilityCrisisSignal, MarylandFacility, OutreachEmailLog
from app.services.contact_enrichment import enrich_facility_contacts
from app.services.outreach_llm import generate_crisis_outreach_email
from app.services.outreach_pipeline import (
    enrich_contacts_for_facility,
    list_outreach_targets,
    run_outreach_campaign,
)


def test_contact_enrichment_dry_run() -> None:
    contacts = enrich_facility_contacts(facility_name="FutureCare Northpoint", city="Baltimore", state="MD")
    assert len(contacts) >= 2
    assert any("don" in contact.title.lower() or "nursing" in contact.title.lower() for contact in contacts)
    assert all(contact.email for contact in contacts)


def test_generate_crisis_outreach_email_template() -> None:
    draft = generate_crisis_outreach_email(
        administrator_name="Patricia Hughes",
        facility_name="FutureCare Northpoint",
        city="Baltimore",
        county="Baltimore",
        crisis_summary="CNA posting open 47 days on Indeed.",
    )
    assert "Emergency CNA/LPN backup coverage" in draft.subject
    assert "COMAR" in draft.body
    assert "Patricia Hughes" in draft.body
    assert draft.mode == "template"


def test_outreach_campaign_drafts_emails() -> None:
    db = SessionLocal()
    try:
        facility = MarylandFacility(
            name="FutureCare Northpoint",
            facility_type="NURSING_HOME",
            county="Baltimore",
            state="MD",
            city="Baltimore",
        )
        db.add(facility)
        db.flush()
        db.add(
            FacilityCrisisSignal(
                facility_id=facility.facility_id,
                signal_type="PERSISTENT_JOB_POSTING",
                severity="HIGH",
                score=47,
                summary="CNA posting open 47 days on Indeed.",
                source="INDEED",
            )
        )
        db.commit()
        result = run_outreach_campaign(db, limit=5, send=False)
        assert result["targets"] >= 1
        assert result["emails_drafted"] >= 1
        logs = db.query(OutreachEmailLog).all()
        assert logs
        assert logs[0].status == "DRAFT"
    finally:
        db.close()


def test_enrich_contacts_for_facility_api(client: TestClient) -> None:
    facility = client.post(
        "/api/facilities",
        json={
            "name": f"Genesis Outreach {uuid4().hex[:6]}",
            "facility_type": "NURSING_HOME",
            "county": "Baltimore",
            "state": "MD",
        },
    ).json()
    response = client.post(f"/api/outreach/facilities/{facility['facility_id']}/enrich")
    assert response.status_code == 200
    body = response.json()
    assert body["contacts_enriched"] >= 2


def test_outreach_campaign_api(client: TestClient) -> None:
    facility = client.post(
        "/api/facilities",
        json={
            "name": f"CommuniCare Outreach {uuid4().hex[:6]}",
            "facility_type": "NURSING_HOME",
            "county": "Montgomery",
            "state": "MD",
        },
    ).json()
    db = SessionLocal()
    try:
        db.add(
            FacilityCrisisSignal(
                facility_id=facility["facility_id"],
                signal_type="OPEN_SHIFT_SURGE",
                severity="MEDIUM",
                score=5,
                summary="Open shift surge detected.",
                source="INTERNAL_SHIFT_ENGINE",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post("/api/outreach/campaign/run?limit=5&send=false")
    assert response.status_code == 200
    body = response.json()
    assert body["emails_drafted"] >= 1
    logs = client.get("/api/outreach/emails/log?limit=5").json()
    assert isinstance(logs, list)


def test_admin_renders_outreach_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    assert "outreach-panel" in html
    assert "run-outreach-campaign-btn" in html
    js = client.get("/admin/app.js").text
    assert "renderOutreachTargets" in js
    assert "/api/outreach/campaign/run" in js
