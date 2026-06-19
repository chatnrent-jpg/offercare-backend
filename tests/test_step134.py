"""Maryland production deploy runbook (step 134)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.maryland_production_runbook import MARYLAND_PRODUCTION_RUNBOOK_JSON_FILENAME


@pytest.fixture
def maryland_production_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LIVE_SCRAPER_GATEWAY_BASE_URL", "https://adapters.example.com")
    monkeypatch.setattr(settings, "LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED", False)
    monkeypatch.setattr(settings, "MBON_VERIFY_DRY_RUN", False)
    monkeypatch.setattr(settings, "OIG_SCREEN_DRY_RUN", False)
    monkeypatch.setattr(settings, "MD_JUDICIARY_DRY_RUN", False)
    monkeypatch.setattr(settings, "JOB_BOARD_SCRAPE_DRY_RUN", False)
    monkeypatch.setattr(settings, "VMS_INGEST_DRY_RUN", False)
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.offercare.example.com")
    monkeypatch.setattr(settings, "STAFFING_VMS_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "STAFFING_JOB_BOARD_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "COMPLIANCE_MONITOR_WORKER_ENABLED", True)


def test_maryland_production_runbook_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/maryland-production-runbook")
    assert response.status_code == 200
    body = response.json()
    assert "production_ready" in body
    assert "checks" in body
    assert "steps" in body
    assert "env_snippet" in body
    assert "launch_urls" in body
    assert any(row["id"] == "live_scrapers" for row in body["checks"])


def test_maryland_production_runbook_json_download(client: TestClient) -> None:
    response = client.get("/api/deploy/maryland-production-runbook.json")
    assert response.status_code == 200
    assert MARYLAND_PRODUCTION_RUNBOOK_JSON_FILENAME in response.headers.get("content-disposition", "")
    assert "production_ready" in response.text


def test_maryland_production_ready_when_fully_configured(
    client: TestClient,
    maryland_production_live: None,
) -> None:
    body = client.get("/api/deploy/maryland-production-runbook").json()
    assert body["production_ready"] is True
    assert body["summary"]["live_scrapers_all_live"] is True
    assert "LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED=false" in body["env_snippet"]


def test_deploy_checklist_includes_maryland_production_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "maryland_production")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["maryland_production_steps"]
    assert checklist["maryland_production_runbook"] is not None


def test_deploy_checklist_summary_includes_maryland_production_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "maryland_production_ready" in summary
    assert "live_scrapers_all_live" in summary


def test_deploy_checklist_csv_includes_maryland_production_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "MARYLAND PRODUCTION STEPS" in csv_text
    assert "Probe live scrapers" in csv_text


def test_health_includes_maryland_production_flags(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "live_scrapers_all_live" in body
    assert "live_scraper_gateway_configured" in body
    assert "maryland_production_ready" in body


def test_admin_deploy_panel_renders_maryland_production_runbook(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="deploy-maryland-production-steps"' in html
    assert "deployMarylandProductionSteps" in js
    assert "/api/deploy/maryland-production-runbook" in js
    assert "copy-maryland-production-env-btn" in html


def test_maryland_production_blocked_without_https(
    client: TestClient,
    maryland_production_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "")
    body = client.get("/api/deploy/maryland-production-runbook").json()
    assert body["production_ready"] is False
    public_check = next(row for row in body["checks"] if row["id"] == "public_https")
    assert public_check["status"] == "blocked"


def test_maryland_production_warns_when_mock_adapters_enabled(
    client: TestClient,
    maryland_production_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED", True)
    body = client.get("/api/deploy/maryland-production-runbook").json()
    assert body["production_ready"] is False
    mock_check = next(row for row in body["checks"] if row["id"] == "mock_adapters_off")
    assert mock_check["status"] == "warning"
