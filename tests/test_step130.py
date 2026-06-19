"""Scheduled VMS poll and daily job board crisis scan workers (step 130)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.staffing_scheduler import (
    run_job_board_worker_tick,
    run_vms_worker_tick,
    staffing_scheduler_status,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_staffing_scheduler_status_endpoint(client: TestClient) -> None:
    response = client.get("/api/ops/staffing-scheduler/status")
    assert response.status_code == 200
    body = response.json()
    assert body["vms_interval_seconds"] == settings.STAFFING_VMS_WORKER_INTERVAL_SECONDS
    assert body["job_board_interval_seconds"] == settings.STAFFING_JOB_BOARD_WORKER_INTERVAL_SECONDS
    assert body["vms_enabled"] is False
    assert body["job_board_enabled"] is False


def test_vms_worker_tick_ingests_shifts(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STAFFING_VMS_WORKER_ENABLED", True)
    response = client.post("/api/ops/staffing-scheduler/vms-tick")
    assert response.status_code == 200
    body = response.json()
    assert body["shifts_fetched"] >= 3
    assert isinstance(body["shifts"], list)


def test_job_board_worker_tick_scans_listings(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STAFFING_JOB_BOARD_WORKER_ENABLED", True)
    response = client.post("/api/ops/staffing-scheduler/job-board-tick")
    assert response.status_code == 200
    body = response.json()
    assert body["listings_scraped"] >= 4
    assert body["crisis_listings"] >= 2


def test_vms_worker_tick_skips_when_disabled(monkeypatch: pytest.MonkeyPatch, db: Session) -> None:
    monkeypatch.setattr(settings, "STAFFING_VMS_WORKER_ENABLED", False)
    result = run_vms_worker_tick(db)
    assert result["skipped"] is True


def test_job_board_worker_tick_skips_when_disabled(monkeypatch: pytest.MonkeyPatch, db: Session) -> None:
    monkeypatch.setattr(settings, "STAFFING_JOB_BOARD_WORKER_ENABLED", False)
    result = run_job_board_worker_tick(db)
    assert result["skipped"] is True


def test_staffing_scheduler_status_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STAFFING_VMS_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "STAFFING_JOB_BOARD_WORKER_ENABLED", True)
    status = staffing_scheduler_status()
    assert status.vms_enabled is True
    assert status.job_board_enabled is True
    assert status.vms_interval_seconds == 900
    assert status.job_board_interval_seconds == 86400


def test_health_includes_staffing_scheduler_flags(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "staffing_vms_worker_enabled" in body
    assert "staffing_job_board_worker_enabled" in body


def test_deploy_checklist_includes_staffing_scheduler(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    item = next(row for row in checklist["items"] if row["id"] == "staffing_scheduler")
    assert item["status"] in {"ready", "warning"}
