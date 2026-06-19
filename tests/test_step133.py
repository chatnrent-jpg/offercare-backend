"""Live scraper gateway, mock adapters, and go-live probes (step 133)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import MarylandProvider
from app.runtime import register_asgi_app
from app.main import app
from app.services.job_board_crisis_scraper import fetch_job_board_listings
from app.services.live_scraper_go_live import build_live_scraper_go_live_profile
from app.services.live_scraper_probes import probe_all_live_scrapers, probe_live_scraper_channel
from app.services.live_scraper_urls import effective_live_scraper_url
from app.services.live_scrapers import live_scrapers_summary
from app.services.mbon_verification import verify_mbon_license
from app.services.vms_shift_ingestion import ingest_vms_shifts


@pytest.fixture(autouse=True)
def _register_asgi_app() -> None:
    register_asgi_app(app)


@pytest.fixture
def live_scraper_go_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LIVE_SCRAPER_GATEWAY_BASE_URL", "http://offercare.local/api/adapters")
    monkeypatch.setattr(settings, "LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED", True)
    monkeypatch.setattr(settings, "MBON_VERIFY_DRY_RUN", False)
    monkeypatch.setattr(settings, "OIG_SCREEN_DRY_RUN", False)
    monkeypatch.setattr(settings, "MD_JUDICIARY_DRY_RUN", False)
    monkeypatch.setattr(settings, "JOB_BOARD_SCRAPE_DRY_RUN", False)
    monkeypatch.setattr(settings, "VMS_INGEST_DRY_RUN", False)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_effective_live_scraper_urls_from_gateway(live_scraper_go_live: None) -> None:
    assert effective_live_scraper_url("mbon").endswith("/api/adapters/mbon/verify")
    assert effective_live_scraper_url("oig").endswith("/api/adapters/oig/leie/search")
    assert effective_live_scraper_url("judiciary").endswith("/api/adapters/md/judiciary/search")
    assert effective_live_scraper_url("job_board").endswith("/api/adapters/job-board/crisis")
    assert effective_live_scraper_url("vms_ingest").endswith("/api/adapters/vms/shifts")


def test_live_scrapers_all_live_when_gateway_configured(client: TestClient, live_scraper_go_live: None) -> None:
    response = client.get("/api/integrations/live-scrapers")
    assert response.status_code == 200
    body = response.json()
    assert body["all_live"] is True
    assert body["live_ready_count"] == 5
    assert body["dry_run_count"] == 0
    assert body["channels"]["mbon"]["endpoint"].endswith("/api/adapters/mbon/verify")


def test_mock_adapter_health_endpoint(client: TestClient, live_scraper_go_live: None) -> None:
    response = client.get("/api/adapters/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "mock_adapter"


def test_mock_adapter_health_hidden_when_disabled(client: TestClient) -> None:
    response = client.get("/api/adapters/health")
    assert response.status_code == 404


def test_live_scraper_probes_all_live_ok(client: TestClient, live_scraper_go_live: None) -> None:
    response = client.post("/api/integrations/live-scrapers/probe")
    assert response.status_code == 200
    probes = response.json()["probes"]
    assert len(probes) == 5
    assert all(row["status"] == "LIVE_OK" for row in probes)


def test_live_scraper_single_probe(client: TestClient, live_scraper_go_live: None) -> None:
    response = client.post("/api/integrations/live-scrapers/mbon/probe")
    assert response.status_code == 200
    body = response.json()
    assert body["channel_id"] == "mbon"
    assert body["status"] == "LIVE_OK"
    assert body["latency_ms"] is not None


def test_go_live_profile_endpoint(client: TestClient, live_scraper_go_live: None) -> None:
    response = client.get("/api/integrations/live-scrapers/go-live-profile")
    assert response.status_code == 200
    body = response.json()
    assert body["all_live"] is True
    assert "LIVE_SCRAPER_GATEWAY_BASE_URL=" in body["env_snippet"]
    assert "MBON_VERIFY_DRY_RUN=false" in body["env_snippet"]
    assert len(body["steps"]) >= 4


def test_mbon_live_verify_uses_mock_adapter(live_scraper_go_live: None) -> None:
    token = uuid4().hex[:8].upper()
    provider = MarylandProvider(
        full_name="Live Probe Nurse",
        email=f"live.{token.lower()}@example.com",
        phone_number=f"+1410559{token[:4]}",
        npi_number="1234567893",
        md_license_number=f"CNA{token}",
        state="MD",
        credential_type="CNA",
        license_status="UNVERIFIED",
    )
    result = verify_mbon_license(provider)
    assert result.status == "ACTIVE"
    assert result.source == "MBON_API"


def test_job_board_live_fetch_uses_mock_adapter(live_scraper_go_live: None) -> None:
    listings = fetch_job_board_listings()
    assert len(listings) >= 4
    assert all(row.state == "MD" for row in listings)


def test_vms_live_ingest_uses_mock_adapter(live_scraper_go_live: None) -> None:
    shifts = ingest_vms_shifts()
    assert len(shifts) >= 3


def test_probe_reports_dry_run_when_channel_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MBON_VERIFY_DRY_RUN", True)
    result = probe_live_scraper_channel("mbon")
    assert result.status == "DRY_RUN"


def test_go_live_profile_builder(live_scraper_go_live: None) -> None:
    profile = build_live_scraper_go_live_profile()
    assert profile["all_live"] is True
    assert profile["mock_adapters_enabled"] is True


def test_deploy_checklist_live_scrapers_ready_when_all_live(
    client: TestClient,
    live_scraper_go_live: None,
) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "live_scrapers")
    assert item["status"] == "ready"


def test_admin_live_scraper_go_live_controls(client: TestClient) -> None:
    js = client.get("/admin/app.js").text
    html = client.get("/admin").text
    assert "probe-live-scrapers-btn" in html
    assert "copy-live-scrapers-env-btn" in html
    assert "/api/integrations/live-scrapers/probe" in js
    assert "/api/integrations/live-scrapers/go-live-profile" in js
    assert "probeLiveScraperChannel" in js


def test_live_scrapers_summary_helper(live_scraper_go_live: None) -> None:
    summary = live_scrapers_summary()
    assert summary["all_live"] is True
    probes = probe_all_live_scrapers()
    assert len(probes) == 5
