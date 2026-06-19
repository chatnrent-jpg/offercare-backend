from __future__ import annotations

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_GATE_DEFINITIONS,
    DEMO_STATUS_JSON_FILENAME,
    build_demo_environment_status,
    build_demo_status_csv,
    build_demo_status_json,
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


def test_demo_status_includes_demo_gates_snapshot_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    demo_gates = status["demo_gates"]
    assert demo_gates is not None
    assert demo_gates["gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert demo_gates["health_status"] == "green"
    assert demo_gates["clipboard_text"]
    assert len(demo_gates["gates"]) == 9


def test_demo_status_json_export_includes_demo_gates(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_status_json(db)
    assert payload["filename"] == DEMO_STATUS_JSON_FILENAME
    body = json.loads(payload["content"])
    assert body["demo_gates"]["gate_count"] == 9
    assert "clipboard_text" in body["demo_gates"]


def test_demo_status_csv_includes_demo_gate_matrix(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_status_csv(db)
    rows = list(csv.reader(io.StringIO(payload["content"])))
    assert ["DEMO GATES"] in rows
    assert ["DEMO GATE MATRIX"] in rows
    assert ["id", "action", "confirm_when", "active"] in rows
    assert any(row and row[0] == "reset_environment" for row in rows)


def test_demo_status_json_download_includes_demo_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status.json")
    assert response.status_code == 200
    body = response.json()
    assert body["demo_gates"]["clipboard_text"]


def test_demo_status_csv_download_includes_demo_gates(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status.csv")
    assert response.status_code == 200
    assert "DEMO GATES" in response.text
    assert "DEMO GATE MATRIX" in response.text


def test_deploy_checklist_demo_steps_mention_demo_status_demo_gates_snapshot(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any("demo status json embeds the full demo_gates snapshot" in step.lower() for step in steps)
    assert any("demo status csv includes demo gate" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_demo_status_demo_gates_snapshot(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any("demo status json embeds the full demo_gates snapshot" in step.lower() for step in steps)
    assert any("demo status csv includes demo gate" in step.lower() for step in steps)
