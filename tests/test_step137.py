"""Production ops dashboard (step 137)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.production_ops_dashboard import (
    PRODUCTION_OPS_DASHBOARD_JSON_FILENAME,
    build_production_ops_dashboard,
    refresh_production_ops_dashboard,
)


@pytest.fixture
def production_ops_live(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(settings, "SNIPER_CASCADE_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "SNIPER_CASCADE_ENABLED", True)
    monkeypatch.setattr(settings, "SMS_DRY_RUN", False)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15551234567")
    monkeypatch.setattr(settings, "TWILIO_VALIDATE_SIGNATURES", True)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_production_ops_dashboard_endpoint(client: TestClient) -> None:
    response = client.get("/api/ops/production-dashboard")
    assert response.status_code == 200
    body = response.json()
    assert "production_ops_ready" in body
    assert "summary" in body
    assert "checks" in body
    assert "metrics" in body
    assert "workers" in body
    assert "integrations" in body
    assert "live_scrapers" in body
    assert "launch" in body
    assert "audit_events" in body
    assert any(row["id"] == "cascade_worker" for row in body["checks"])


def test_production_ops_dashboard_json_download(client: TestClient) -> None:
    response = client.get("/api/ops/production-dashboard.json")
    assert response.status_code == 200
    assert PRODUCTION_OPS_DASHBOARD_JSON_FILENAME in response.headers.get("content-disposition", "")
    assert "production_ops_ready" in response.text


def test_production_ops_ready_when_fully_configured(
    client: TestClient,
    production_ops_live: None,
) -> None:
    body = client.get("/api/ops/production-dashboard").json()
    assert body["production_ops_ready"] is True
    assert body["launch"]["launch_ready"] is True
    assert body["live_scrapers"]["summary"]["all_live"] is True
    assert body["summary"]["workers_enabled_count"] == 4


def test_production_ops_dashboard_refresh_endpoint(client: TestClient) -> None:
    response = client.post("/api/ops/production-dashboard/refresh", json={"probe_scrapers": False})
    assert response.status_code == 200
    body = response.json()
    assert "production_ops_ready" in body
    assert "summary" in body
    assert body["scraper_probes"] == []


def test_production_ops_dashboard_refresh_helper(db: Session) -> None:
    result = refresh_production_ops_dashboard(db, probe_scrapers=False)
    assert "workers" in result
    assert "metrics" in result
    assert isinstance(result["audit_events"], list)


def test_deploy_checklist_includes_production_ops_dashboard_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "production_ops_dashboard")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["production_ops_dashboard_steps"]
    assert checklist["production_ops_dashboard"] is not None


def test_deploy_checklist_summary_includes_production_ops_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "production_ops_ready" in summary
    assert "production_ops_ready_count" in summary


def test_deploy_checklist_csv_includes_production_ops_dashboard_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "PRODUCTION OPS DASHBOARD STEPS" in csv_text
    assert "Refresh all production signals" in csv_text


def test_health_includes_production_ops_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "production_ops_ready" in body


def test_admin_production_ops_dashboard_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="production-ops-summary"' in html
    assert "refresh-production-ops-btn" in html
    assert "renderProductionOpsDashboard" in js
    assert "/api/ops/production-dashboard" in js
    assert "/api/ops/production-dashboard/refresh" in js
    assert "refreshProductionOpsDashboard" in js


def test_production_ops_blocked_when_workers_disabled(
    client: TestClient,
    production_ops_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "COMPLIANCE_MONITOR_WORKER_ENABLED", False)
    body = client.get("/api/ops/production-dashboard").json()
    assert body["production_ops_ready"] is False
    worker_check = next(row for row in body["checks"] if row["id"] == "compliance_monitor_worker")
    assert worker_check["status"] == "blocked"


def test_production_ops_dashboard_builder(db: Session, production_ops_live: None) -> None:
    dashboard = build_production_ops_dashboard(db)
    assert dashboard["production_ops_ready"] is True
    assert dashboard["workers"]["cascade"]["enabled"] is True
    assert len(dashboard["checks"]) >= 7


def test_deploy_bundle_includes_production_ops_dashboard(client: TestClient) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert PRODUCTION_OPS_DASHBOARD_JSON_FILENAME.encode() in response.content
