"""Maryland deploy walkthrough UI and ops scheduler manual ticks (step 132)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings


def test_deploy_checklist_maryland_steps_include_scheduler_and_scrapers(client: TestClient) -> None:
    checklist = client.get("/api/deploy/checklist").json()
    steps = checklist["maryland_platform_steps"]
    assert any("/join" in step for step in steps)
    assert any("COMPLIANCE_MONITOR_WORKER_ENABLED" in step for step in steps)
    assert any("Live scrapers" in step for step in steps)
    assert any("scheduler ticks" in step for step in steps)
    assert any("Maryland platform steps after refresh" in step for step in steps)


def test_deploy_export_steps_mention_maryland_panel(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any("Maryland platform steps after refresh" in step for step in steps)


def test_admin_deploy_panel_renders_maryland_steps(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    assert 'id="deploy-maryland-steps"' in html
    assert "deployMarylandSteps" in js
    assert "maryland_platform_steps" in js


def test_admin_ops_scheduler_tick_buttons(client: TestClient) -> None:
    html = client.get("/admin").text
    js = client.get("/admin/app.js").text
    for button_id in (
        "cascade-worker-tick-btn",
        "staffing-vms-tick-btn",
        "staffing-job-board-tick-btn",
        "compliance-scheduler-tick-btn",
    ):
        assert button_id in html
    assert "/api/ops/cascade-worker/tick" in js
    assert "/api/ops/staffing-scheduler/vms-tick" in js
    assert "/api/ops/staffing-scheduler/job-board-tick" in js
    assert "/api/ops/compliance-scheduler/tick" in js
    assert "runCascadeWorkerTick" in js
    assert "runStaffingVmsTick" in js
    assert "runStaffingJobBoardTick" in js
    assert "runComplianceSchedulerTick" in js


def test_cascade_worker_tick_endpoint(client: TestClient) -> None:
    response = client.post("/api/ops/cascade-worker/tick")
    assert response.status_code == 200
    body = response.json()
    assert "advanced" in body
    assert "results" in body


def test_staffing_scheduler_ticks_when_enabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STAFFING_VMS_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "STAFFING_JOB_BOARD_WORKER_ENABLED", True)
    vms = client.post("/api/ops/staffing-scheduler/vms-tick").json()
    board = client.post("/api/ops/staffing-scheduler/job-board-tick").json()
    assert vms["shifts_fetched"] >= 3
    assert board["listings_scraped"] >= 4


def test_compliance_scheduler_tick_when_enabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "COMPLIANCE_MONITOR_WORKER_ENABLED", True)
    body = client.post("/api/ops/compliance-scheduler/tick").json()
    assert body["documents_checked"] >= 0
    assert isinstance(body["suspended_provider_ids"], list)


def test_deploy_checklist_csv_includes_maryland_platform_steps(client: TestClient) -> None:
    csv_text = client.get("/api/deploy/checklist.csv").text
    assert "MARYLAND PLATFORM STEPS" in csv_text
    assert "Live scrapers" in csv_text
    assert "scheduler ticks" in csv_text
