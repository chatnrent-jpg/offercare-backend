"""Maryland production launch capstone (step 136)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.maryland_launch_capstone import (
    MARYLAND_LAUNCH_CAPSTONE_JSON_FILENAME,
    build_maryland_launch_capstone,
    run_maryland_launch_smoke,
)


@pytest.fixture
def maryland_launch_live(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_maryland_launch_capstone_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/maryland-launch-capstone")
    assert response.status_code == 200
    body = response.json()
    assert "launch_ready" in body
    assert "maryland_production_ready" in body
    assert "twilio_sms_production_ready" in body
    assert "checks" in body
    assert "steps" in body
    assert "env_snippet" in body
    assert any(row["id"] == "maryland_launch_capstone" for row in body["checks"])


def test_maryland_launch_capstone_json_download(client: TestClient) -> None:
    response = client.get("/api/deploy/maryland-launch-capstone.json")
    assert response.status_code == 200
    assert MARYLAND_LAUNCH_CAPSTONE_JSON_FILENAME in response.headers.get("content-disposition", "")
    assert "launch_ready" in response.text


def test_maryland_launch_ready_when_fully_configured(
    client: TestClient,
    maryland_launch_live: None,
) -> None:
    body = client.get("/api/deploy/maryland-launch-capstone").json()
    assert body["launch_ready"] is True
    assert body["maryland_production_ready"] is True
    assert body["twilio_sms_production_ready"] is True
    assert body["live_scrapers_all_live"] is True
    assert "SMS_DRY_RUN=false" in body["env_snippet"]
    assert "LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED=false" in body["env_snippet"]


def test_maryland_launch_smoke_endpoint(client: TestClient) -> None:
    response = client.post("/api/deploy/maryland-launch-smoke", json={})
    assert response.status_code == 200
    body = response.json()
    assert "ok" in body
    assert "lock_reply_smoke" in body
    assert body["lock_reply_smoke"]["status"] == "locked"
    assert body["lock_reply_smoke_ok"] is True


def test_maryland_launch_smoke_helper(db: Session) -> None:
    result = run_maryland_launch_smoke(db, probe_scrapers=False)
    assert result["lock_reply_smoke_ok"] is True
    assert result["lock_reply_smoke"]["status"] == "locked"
    assert result["facility_name"]


def test_deploy_checklist_includes_maryland_launch_capstone_item(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "maryland_launch_capstone")
    assert item["status"] in {"ready", "warning", "blocked"}
    assert checklist["maryland_launch_capstone_steps"]
    assert checklist["maryland_launch_capstone"] is not None


def test_deploy_checklist_summary_includes_maryland_launch_flags(client: TestClient) -> None:
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert "maryland_launch_ready" in summary
    assert "maryland_launch_ready_count" in summary


def test_deploy_checklist_csv_includes_maryland_launch_capstone_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "MARYLAND LAUNCH CAPSTONE STEPS" in csv_text
    assert "launch smoke" in csv_text.lower()


def test_health_includes_maryland_launch_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "maryland_launch_ready" in body


def test_admin_deploy_panel_renders_maryland_launch_capstone(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="deploy-maryland-launch-steps"' in html
    assert "run-maryland-launch-smoke-btn" in html
    assert "deployMarylandLaunchSteps" in js
    assert "/api/deploy/maryland-launch-smoke" in js
    assert "/api/deploy/maryland-launch-capstone" in js
    assert "runMarylandLaunchSmoke" in js


def test_maryland_launch_blocked_without_twilio(
    client: TestClient,
    maryland_launch_live: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SMS_DRY_RUN", True)
    body = client.get("/api/deploy/maryland-launch-capstone").json()
    assert body["launch_ready"] is False
    sms_check = next(row for row in body["checks"] if row["id"] == "live_sms_production")
    assert sms_check["status"] == "blocked"


def test_maryland_launch_capstone_builder(db: Session, maryland_launch_live: None) -> None:
    capstone = build_maryland_launch_capstone(db)
    assert capstone["launch_ready"] is True
    assert capstone["maryland_production_runbook"] is not None
    assert capstone["twilio_sms_production_runbook"] is not None


def test_deploy_bundle_includes_maryland_launch_capstone(client: TestClient) -> None:
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert MARYLAND_LAUNCH_CAPSTONE_JSON_FILENAME.encode() in response.content
