from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_ADMIN_ACTION_DEMO_GATES,
    build_demo_status_csv,
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


def test_demo_status_csv_includes_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_status_csv(db)
    rows = list(csv.reader(io.StringIO(payload["content"])))
    assert ["DEMO ADMIN ACTIONS"] in rows
    assert ["action", "endpoint", "demo_gates_field"] in rows
    assert any(row and row[0] == "Run full demo setup" for row in rows)
    assert any(len(row) >= 2 and row[1] == "POST /api/seed/demo-lock-smoke" for row in rows)
    assert len(DEMO_ADMIN_ACTION_DEMO_GATES) == 8


def test_deploy_checklist_csv_includes_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_checklist_csv(db)
    rows = list(csv.reader(io.StringIO(payload["content"])))
    assert ["DEMO ADMIN ACTIONS"] in rows
    assert ["action", "endpoint", "demo_gates_field"] in rows
    assert any(len(row) >= 3 and row[2] == "status.demo_gates" for row in rows)
    assert any(len(row) >= 3 and row[2] == "demo_status.demo_gates" for row in rows)


def test_demo_status_csv_download_includes_demo_admin_actions(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status.csv")
    assert response.status_code == 200
    assert "DEMO ADMIN ACTIONS" in response.text
    assert "POST /api/seed/demo-push-subscriptions" in response.text


def test_deploy_checklist_csv_download_includes_demo_admin_actions(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/deploy/checklist.csv")
    assert response.status_code == 200
    assert "DEMO ADMIN ACTIONS" in response.text
    assert "POST /api/seed/demo-reset-offer" in response.text


def test_deploy_checklist_export_steps_mention_csv_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any(
        "deploy checklist csv includes the demo admin actions catalog" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_csv_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "demo status csv includes the demo admin actions catalog" in step.lower()
        for step in steps
    )


def test_deploy_checklist_demo_steps_mention_csv_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "deploy checklist csv includes the demo admin actions catalog" in step.lower()
        for step in steps
    )
