"""Live scraper registry and compliance monitor scheduler (step 131)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.compliance_scheduler import (
    compliance_scheduler_status,
    run_compliance_monitor_tick,
)
from app.services.live_scrapers import (
    get_job_board_scraper_status,
    get_mbon_scraper_status,
    live_scraper_channels,
    live_scrapers_summary,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_live_scrapers_endpoint(client: TestClient) -> None:
    response = client.get("/api/integrations/live-scrapers")
    assert response.status_code == 200
    body = response.json()
    assert body["total_channels"] == 5
    assert body["live_ready_count"] == 0
    assert body["dry_run_count"] == 5
    assert body["all_live"] is False
    assert set(body["channels"]) == {"mbon", "oig", "judiciary", "job_board", "vms_ingest"}


def test_mbon_scraper_dry_run_by_default() -> None:
    channel = get_mbon_scraper_status()
    assert channel.dry_run is True
    assert channel.configured is True
    assert channel.live_ready is False


def test_job_board_scraper_live_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "JOB_BOARD_SCRAPE_DRY_RUN", False)
    monkeypatch.setattr(settings, "JOB_BOARD_SCRAPE_URL", "https://scraper.example.com/jobs")
    channel = get_job_board_scraper_status()
    assert channel.dry_run is False
    assert channel.live_ready is True


def test_compliance_scheduler_status_endpoint(client: TestClient) -> None:
    response = client.get("/api/ops/compliance-scheduler/status")
    assert response.status_code == 200
    body = response.json()
    assert body["interval_seconds"] == settings.COMPLIANCE_MONITOR_WORKER_INTERVAL_SECONDS
    assert body["enabled"] is False
    assert body["running"] is False


def test_compliance_scheduler_tick(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "COMPLIANCE_MONITOR_WORKER_ENABLED", True)
    response = client.post("/api/ops/compliance-scheduler/tick")
    assert response.status_code == 200
    body = response.json()
    assert body["documents_checked"] >= 0
    assert isinstance(body["expiring_alerts"], list)
    assert isinstance(body["suspended_provider_ids"], list)


def test_compliance_scheduler_tick_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
) -> None:
    monkeypatch.setattr(settings, "COMPLIANCE_MONITOR_WORKER_ENABLED", False)
    result = run_compliance_monitor_tick(db)
    assert result["skipped"] is True


def test_compliance_scheduler_status_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "COMPLIANCE_MONITOR_WORKER_ENABLED", True)
    status = compliance_scheduler_status()
    assert status.enabled is True
    assert status.interval_seconds == 3600


def test_health_includes_compliance_monitor_flag(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert "compliance_monitor_worker_enabled" in response.json()


def test_deploy_checklist_includes_step131_items(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    ids = {row["id"] for row in checklist["items"]}
    assert "compliance_scheduler" in ids
    assert "live_scrapers" in ids
    live_item = next(row for row in checklist["items"] if row["id"] == "live_scrapers")
    assert live_item["status"] in {"pending", "warning", "ready"}


def test_compliance_overview_includes_job_board_flag(client: TestClient) -> None:
    overview = client.get("/api/compliance/overview?limit=10").json()
    assert "job_board" in overview["dry_run_flags"]


def test_live_scraper_channels_count() -> None:
    assert len(live_scraper_channels()) == 5
    summary = live_scrapers_summary()
    assert summary["total_channels"] == 5
