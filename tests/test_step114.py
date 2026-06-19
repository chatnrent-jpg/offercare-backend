from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_ADMIN_ACTION_DEMO_GATES,
    DEMO_STATUS_JSON_FILENAME,
    build_demo_environment_status,
    build_demo_export_bundle,
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


def test_build_demo_environment_status_includes_top_level_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    actions = status["demo_admin_actions"]
    assert len(actions) == len(DEMO_ADMIN_ACTION_DEMO_GATES)
    assert actions[0]["endpoint"] == "POST /api/seed/demo-setup"
    assert actions[0]["field"] == "status.demo_gates"
    assert any(row["endpoint"] == "POST /api/seed/demo-lock-smoke" for row in actions)


def test_build_demo_status_json_includes_top_level_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_status_json(db)
    assert payload["filename"] == DEMO_STATUS_JSON_FILENAME
    body = json.loads(payload["content"])
    assert len(body["demo_admin_actions"]) == 8
    assert body["demo_admin_actions"][7]["action"] == "Ensure demo push subscriptions"


def test_demo_status_endpoint_includes_top_level_demo_admin_actions_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-status").json()
    assert len(body["demo_admin_actions"]) == 8
    assert body["demo_admin_actions"][3]["field"] == "demo_status.demo_gates"


def test_demo_status_json_download_includes_top_level_demo_admin_actions_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-status.json").json()
    assert any(row["action"] == "Per-row Reset" for row in body["demo_admin_actions"])


def test_demo_export_bundle_status_json_includes_top_level_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        status = json.loads(archive.read(DEMO_STATUS_JSON_FILENAME))
    assert status["demo_admin_actions"][0]["field"] == "status.demo_gates"
    assert len(status["demo_admin_actions"]) == 8


def test_demo_status_next_steps_mention_json_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "demo status json includes the demo admin actions catalog" in step.lower()
        for step in steps
    )


def test_deploy_checklist_demo_steps_mention_demo_status_json_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "demo status json includes the demo admin actions catalog" in step.lower()
        for step in steps
    )


def test_deploy_checklist_export_steps_mention_demo_status_json_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any(
        "demo status json includes the demo admin actions catalog" in step.lower()
        for step in steps
    )
