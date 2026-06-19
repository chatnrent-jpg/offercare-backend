from __future__ import annotations

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_ADMIN_ACTION_DEMO_GATES,
    build_demo_environment_status,
    build_demo_gates_json,
    build_demo_gates_summary,
    build_demo_status_csv,
    build_demo_walkthrough_script,
    run_full_demo_setup,
)
from app.services.deploy_walkthrough import build_deploy_checklist_csv


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_demo_gates_summary_includes_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    summary = build_demo_gates_summary(db)
    assert summary["demo_admin_action_count"] == len(DEMO_ADMIN_ACTION_DEMO_GATES)
    assert summary["demo_admin_action_count"] == 8
    assert summary["gate_count"] == 9


def test_build_demo_gates_json_includes_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    body = json.loads(build_demo_gates_json(db)["content"])
    assert body["demo_admin_action_count"] == 8


def test_demo_gates_clipboard_text_includes_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    text = build_demo_gates_summary(db)["clipboard_text"]
    assert "Demo admin actions: 8" in text


def test_demo_health_gate_hints_mention_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    hints = build_demo_environment_status(db)["health"]["gate_hints"]
    assert any("8 cataloged" in hint for hint in hints)
    assert any("embedded demo_gates" in hint for hint in hints)


def test_demo_walkthrough_status_snapshot_includes_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    markdown = build_demo_walkthrough_script(db)["markdown"]
    assert "Demo admin actions: 8 cataloged" in markdown


def test_demo_status_csv_demo_gates_section_includes_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    rows = list(csv.reader(io.StringIO(build_demo_status_csv(db)["content"])))
    assert ["demo_admin_action_count", "8"] in rows


def test_deploy_checklist_csv_demo_gates_section_includes_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    rows = list(csv.reader(io.StringIO(build_deploy_checklist_csv(db)["content"])))
    assert ["demo_admin_action_count", "8"] in rows


def test_demo_gates_endpoint_includes_admin_action_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-gates").json()
    assert body["demo_admin_action_count"] == 8


def test_admin_app_js_download_gate_exports_mention_admin_action_count(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "Downloaded gates (.txt) + admin actions" in text
    assert "Exported gates (.json) + admin actions" in text
    assert "demo_admin_action_count" in text


def test_demo_status_next_steps_mention_gates_json_admin_action_count(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any("demo gates json includes demo admin action count" in step.lower() for step in steps)
    assert any("download gates (.txt) toasts show demo admin action count" in step.lower() for step in steps)


def test_deploy_checklist_export_steps_mention_gates_json_admin_action_count(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any("demo gates json includes demo admin action count" in step.lower() for step in steps)
    assert any("download gates (.txt) toasts show demo admin action count" in step.lower() for step in steps)
