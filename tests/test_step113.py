from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import DEMO_ADMIN_ACTION_DEMO_GATES, run_full_demo_setup
from app.services.deploy_walkthrough import (
    DEPLOY_CHECKLIST_JSON_FILENAME,
    build_deploy_checklist,
    build_deploy_checklist_json,
    build_deploy_export_bundle,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_deploy_checklist_includes_top_level_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    snapshot = build_deploy_checklist(db)
    actions = snapshot["demo_admin_actions"]
    assert len(actions) == len(DEMO_ADMIN_ACTION_DEMO_GATES)
    assert actions[0]["endpoint"] == "POST /api/seed/demo-setup"
    assert actions[0]["field"] == "status.demo_gates"
    assert any(row["endpoint"] == "POST /api/seed/demo-lock-smoke" for row in actions)


def test_build_deploy_checklist_json_includes_top_level_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_checklist_json(db)
    assert payload["filename"] == DEPLOY_CHECKLIST_JSON_FILENAME
    body = json.loads(payload["content"])
    assert len(body["demo_admin_actions"]) == 8
    assert body["demo_admin_actions"][7]["action"] == "Ensure demo push subscriptions"


def test_deploy_checklist_endpoint_includes_top_level_demo_admin_actions_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/deploy/checklist").json()
    assert len(body["demo_admin_actions"]) == 8
    assert body["demo_admin_actions"][3]["field"] == "demo_status.demo_gates"


def test_deploy_checklist_json_download_includes_top_level_demo_admin_actions_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/deploy/checklist.json").json()
    assert any(row["action"] == "Per-row Reset" for row in body["demo_admin_actions"])


def test_deploy_export_bundle_checklist_json_includes_top_level_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        checklist = json.loads(archive.read(DEPLOY_CHECKLIST_JSON_FILENAME))
    assert checklist["demo_admin_actions"][0]["field"] == "status.demo_gates"
    assert len(checklist["demo_admin_actions"]) == 8


def test_deploy_checklist_export_steps_mention_json_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any(
        "deploy checklist json includes the demo admin actions catalog" in step.lower()
        for step in steps
    )


def test_deploy_checklist_demo_steps_mention_json_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "deploy checklist json includes the demo admin actions catalog" in step.lower()
        for step in steps
    )
