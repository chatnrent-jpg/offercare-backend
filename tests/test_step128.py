"""Capstone integration test for the Maryland staffing platform arc (steps 123–127)."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.services.deploy_walkthrough import _maryland_platform_present
from app.services.worker_consent import WORKER_CONSENT_VERSION


def _seed_maryland_snfs(client: TestClient) -> None:
    for name, county in (
        ("FutureCare Northpoint", "Baltimore"),
        ("Genesis HealthCare Baltimore Center", "Baltimore"),
        ("CommuniCare Silver Spring", "Montgomery"),
    ):
        client.post(
            "/api/facilities",
            json={
                "name": name,
                "facility_type": "NURSING_HOME",
                "county": county,
                "state": "MD",
            },
        )


def test_maryland_platform_end_to_end_capstone(client: TestClient) -> None:
    """Worker inflow → credentialing → crisis intel → VMS offers → outreach."""
    _seed_maryland_snfs(client)

    job_board = client.post("/api/compliance/crisis/job-boards/scan").json()
    assert job_board["listings_scraped"] >= 4
    assert job_board["crisis_listings"] >= 2

    vms = client.post("/api/vms/shifts/ingest?persist=true").json()
    assert vms["shifts_fetched"] >= 3
    assert vms["offers_created"] + vms["offers_skipped"] >= 3

    token = uuid4().hex[:10]
    email = f"capstone.cna.{token}@example.com"
    worker = client.post(
        "/api/landing/maryland/apply",
        json={
            "full_name": "Capstone Test CNA",
            "email": email,
            "phone_number": f"410559{token[:4]}",
            "md_license_number": f"CNA-MD-CAP{token[:6].upper()}",
            "credential_type": "CNA",
            "min_hourly_rate": 28.0,
            "password": "testpass123",
            "home_zip": "21201",
            "consent_version": WORKER_CONSENT_VERSION,
            "consent_credential_screening": True,
            "consent_sms_dispatch": True,
            "consent_privacy_policy": True,
            "consent_terms_of_service": True,
            "consent_aedt_30_day": True,
        },
    ).json()
    assert worker["license_status"] == "VERIFIED"
    assert worker["dispatch_status"] == "ACTIVE"
    provider_id = worker["provider_id"]

    screen = client.post(f"/api/compliance/providers/{provider_id}/screen").json()
    assert screen["mbon_status"] == "ACTIVE"
    assert screen["blocked"] is False

    monitor = client.post("/api/compliance/monitor/run").json()
    assert monitor["documents_checked"] >= 4

    audit = client.get(f"/api/compliance/providers/{provider_id}/audit-packet")
    assert audit.status_code == 200
    assert audit.content[:2] == b"PK"

    outreach = client.post("/api/outreach/campaign/run?limit=5&send=false").json()
    assert outreach["targets"] >= 1
    assert outreach["emails_drafted"] >= 1

    offers = client.get("/api/shifts/open?limit=50&state=MD").json()
    assert offers
    offer_id = offers[0]["offer_id"]
    ranking = client.get(f"/shift-sniper/offers/{offer_id}/rank").json()
    assert "ranked" in ranking
    assert "eliminated" in ranking

    compliance_overview = client.get("/api/compliance/overview?limit=25").json()
    assert compliance_overview["total_providers"] >= 1
    assert "dry_run_flags" in compliance_overview

    assert client.get("/join").status_code == 200
    assert client.get("/api/landing/maryland").json()["apply_defaults"]["state"] == "MD"


def test_deploy_checklist_includes_maryland_platform_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "maryland_platform")
    assert item["status"] == "ready"
    assert checklist["maryland_platform_steps"]
    assert any("/join" in step for step in checklist["maryland_platform_steps"])


def test_maryland_platform_files_present() -> None:
    assert _maryland_platform_present() is True


def test_deploy_checklist_csv_includes_maryland_platform_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "MARYLAND PLATFORM STEPS" in csv_text
    assert "/join" in csv_text
