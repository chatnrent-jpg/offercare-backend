from __future__ import annotations

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import DEMO_GATE_DEFINITIONS, run_full_demo_setup
from app.services.deploy_walkthrough import (
    DEPLOY_CHECKLIST_JSON_FILENAME,
    build_deploy_checklist,
    build_deploy_checklist_csv,
    build_deploy_checklist_json,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_deploy_checklist_includes_demo_gates_snapshot_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    checklist = build_deploy_checklist(db)
    demo_gates = checklist["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert demo_gates["health_status"] == "green"
    assert demo_gates["clipboard_text"]
    assert len(demo_gates["gates"]) == 9


def test_deploy_checklist_json_export_includes_demo_gates(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_checklist_json(db)
    assert payload["filename"] == DEPLOY_CHECKLIST_JSON_FILENAME
    body = json.loads(payload["content"])
    assert body["demo_gates"]["gate_count"] == 9
    assert "clipboard_text" in body["demo_gates"]


def test_deploy_checklist_csv_includes_demo_gate_matrix(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_checklist_csv(db)
    rows = list(csv.reader(io.StringIO(payload["content"])))
    assert ["DEMO GATES"] in rows
    assert ["DEMO GATE MATRIX"] in rows
    assert ["id", "action", "confirm_when", "active"] in rows
    assert any(row and row[0] == "reset_environment" for row in rows)


def test_deploy_checklist_endpoint_includes_demo_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/deploy/checklist").json()
    assert body["demo_gates"] is not None
    assert body["demo_gates"]["gate_count"] == 9
    assert body["summary"]["demo_gate_count"] == 9


def test_deploy_checklist_json_download_includes_demo_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/deploy/checklist.json")
    assert response.status_code == 200
    body = response.json()
    assert body["demo_gates"]["clipboard_text"]


def test_deploy_checklist_csv_download_includes_demo_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/deploy/checklist.csv")
    assert response.status_code == 200
    assert "DEMO GATES" in response.text
    assert "DEMO GATE MATRIX" in response.text


def test_deploy_checklist_export_steps_mention_demo_gates_snapshot(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any("demo_gates snapshot" in step.lower() for step in steps)
