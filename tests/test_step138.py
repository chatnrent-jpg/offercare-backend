"""Production perfection capstone (step 138)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.production_perfection_capstone import (
    PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME,
    build_production_perfection_capstone,
    run_production_perfection_check,
)


@pytest.fixture
def production_perfection_live(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_production_perfection_capstone_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/production-perfection-capstone")
    assert response.status_code == 200
    body = response.json()
    assert "production_perfection_ready" in body
    assert "production_ops_ready" in body
    assert "maryland_launch_ready" in body
    assert "checks" in body
    assert "steps" in body
    assert any(row["id"] == "production_perfection" for row in body["checks"])


def test_production_perfection_capstone_json_download(client: TestClient) -> None:
    response = client.get("/api/deploy/production-perfection-capstone.json")
    assert response.status_code == 200
    assert PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME in response.headers.get("content-disposition", "")
    assert "production_perfection_ready" in response.text


def test_production_perfection_ready_when_fully_configured(
    client: TestClient,
    production_perfection_live: None,
) -> None:
    body = client.get("/api/deploy/production-perfection-capstone").json()
    assert body["production_perfection_ready"] is True
    assert body["production_ops_ready"] is True
    assert body["maryland_launch_ready"] is True
    assert "SNIPER_CASCADE_WORKER_ENABLED=true" in body["env_snippet"]


def test_production_perfection_check_endpoint(client: TestClient, production_perfection_live: None) -> None:
    response = client.post(
        "/api/deploy/production-perfection-check",
        json={"probe_scrapers": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["launch_smoke_ok"] is True
    assert body["ops_refresh_ok"] is True
    assert body["launch_smoke"]["lock_reply_smoke"]["status"] == "locked"


def test_production_perfection_check_helper(db: Session, production_perfection_live: None) -> None:
    result = run_production_perfection_check(db, probe_scrapers=False)
    assert result["launch_smoke_ok"] is True
    assert result["ops_refresh_ok"] is True
    assert result["ok"] is True
    assert result["facility_name"]


def test_deploy_checklist_includes_production_perfection_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "production_perfection")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["production_perfection_steps"]
    assert checklist["production_perfection_capstone"] is not None


def test_deploy_checklist_summary_includes_production_perfection_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "production_perfection_ready" in summary
    assert "production_perfection_ready_count" in summary


def test_deploy_checklist_csv_includes_production_perfection_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "PRODUCTION PERFECTION STEPS" in csv_text
    assert "production perfection check" in csv_text.lower()


def test_health_includes_production_perfection_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "production_perfection_ready" in body


def test_admin_production_perfection_panel(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="production-perfection-summary"' in html
    assert "run-production-perfection-check-btn" in html
    assert "renderProductionPerfectionCapstone" in js
    assert "/api/deploy/production-perfection-check" in js
    assert "/api/deploy/production-perfection-capstone" in js
    assert "runProductionPerfectionCheck" in js


def test_production_perfection_blocked_without_launch(
    client: TestClient,
    production_perfection_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", True)
    body = client.get("/api/deploy/production-perfection-capstone").json()
    assert body["production_perfection_ready"] is False
    launch_check = next(row for row in body["checks"] if row["id"] == "maryland_launch_capstone")
    assert launch_check["status"] == "blocked"


def test_production_perfection_capstone_builder(db: Session, production_perfection_live: None) -> None:
    capstone = build_production_perfection_capstone(db)
    assert capstone["production_perfection_ready"] is True
    assert capstone["production_ops_dashboard"] is not None
    assert capstone["maryland_launch_capstone"] is not None


def test_deploy_bundle_includes_production_perfection_capstone(client: TestClient) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME.encode() in response.content
