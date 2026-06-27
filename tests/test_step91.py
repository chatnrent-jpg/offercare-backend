from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_GATE_DEFINITIONS,
    build_demo_gates_clipboard_text,
    build_demo_gates_json,
    build_demo_gates_summary,
    run_full_demo_setup,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_demo_gates_clipboard_text_includes_matrix(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    summary = build_demo_gates_summary(db)
    text = build_demo_gates_clipboard_text(summary)
    assert "VettedCare Demo Confirmation Gates" in text
    assert "Health: READY (green)" in text
    assert "Walkthrough intact: yes" in text
    assert "Active gates:" in text
    assert "Total gates: 9" in text
    assert "Gate matrix:" in text
    assert "reset_environment" in text
    assert "active now" in text
    assert "inactive" in text


def test_build_demo_gates_summary_includes_clipboard_text(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    summary = build_demo_gates_summary(db)
    assert summary["clipboard_text"]
    assert summary["clipboard_text"] == build_demo_gates_clipboard_text(summary)


def test_build_demo_gates_json_includes_clipboard_text(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_gates_json(db)
    body = json.loads(payload["content"])
    assert body["clipboard_text"]
    assert "Gate matrix:" in body["clipboard_text"]


def test_demo_gates_endpoint_includes_clipboard_text(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-gates").json()
    assert body["clipboard_text"]
    assert body["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert "reset_environment" in body["clipboard_text"]


def test_admin_dashboard_includes_copy_active_gates_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "copy-demo-gates-btn" in html.text
    assert "Copy active gates" in html.text
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "copyDemoGatesBtn" in js.text
    assert "clipboard_text" in js.text
    assert "Copied gate matrix" in js.text


def test_copy_active_gates_button_does_not_use_export_ready_gate(client: TestClient) -> None:
    js = client.get("/admin/app.js").text
    handler = js.split("copyDemoGatesBtn?.addEventListener")[1].split("downloadDemoBundleBtn?.addEventListener")[0]
    assert "confirmDemoReadyExport" not in handler


def test_deploy_checklist_mentions_copy_active_gates(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any("copy active gates" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_copy_active_gates(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any("copy active gates" in step.lower() for step in steps)
