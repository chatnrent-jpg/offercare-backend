from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import DEMO_GATES_JSON_FILENAME, run_full_demo_setup


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_admin_dashboard_includes_export_gates_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "download-demo-gates-json-btn" in html.text
    assert "Export gates (.json)" in html.text
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "/api/seed/demo-gates.json" in js.text
    assert DEMO_GATES_JSON_FILENAME in js.text
    assert "Exported demo gates (.json)" in js.text


def test_export_gates_button_does_not_use_export_ready_gate(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    text = js.text
    gatesHandler = text.split("downloadDemoGatesJsonBtn?.addEventListener")[1].split(
        "downloadDemoBundleBtn?.addEventListener"
    )[0]
    assert "confirmDemoReadyExport" not in gatesHandler


def test_demo_gates_json_download_works_after_setup(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-gates.json")
    assert response.status_code == 200
    body = response.json()
    assert body["health_status"] == "green"
    assert body["active_gates"]
    assert len(body["gates"]) == 9


def test_demo_status_next_steps_mention_export_gates_button(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("export demo gates" in step.lower() for step in steps)


def test_deploy_checklist_mentions_export_gates_button(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("export gates" in step.lower() for step in steps)


def test_export_gates_json_includes_notify_matched_gate_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    from app.services.demo_environment import build_demo_gates_json

    payload = build_demo_gates_json(db)
    assert payload["filename"] == DEMO_GATES_JSON_FILENAME
    import json

    body = json.loads(payload["content"])
    notify_gate = next(row for row in body["gates"] if row["id"] == "notify_matched")
    assert notify_gate["active"] is True
