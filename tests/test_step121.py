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
    DEMO_STATUS_JSON_FILENAME,
    build_demo_environment_status,
    build_demo_export_bundle,
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


def test_build_demo_environment_status_includes_top_level_demo_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    assert status["demo_admin_action_count"] == len(DEMO_ADMIN_ACTION_DEMO_GATES)
    assert status["demo_admin_action_count"] == 8
    assert status["health"]["demo_admin_action_count"] == 8


def test_build_demo_status_json_includes_top_level_demo_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_status_json(db)
    assert payload["filename"] == DEMO_STATUS_JSON_FILENAME
    body = json.loads(payload["content"])
    assert body["demo_admin_action_count"] == 8
    assert len(body["demo_admin_actions"]) == 8


def test_demo_status_csv_includes_top_level_demo_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    rows = list(csv.reader(io.StringIO(build_demo_status_csv(db)["content"])))
    assert ["demo_admin_action_count", "8"] in rows
    assert ["health_demo_admin_action_count", "8"] in rows


def test_demo_status_endpoint_includes_top_level_demo_admin_action_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-status").json()
    assert body["demo_admin_action_count"] == 8
    assert body["health"]["demo_admin_action_count"] == 8


def test_demo_status_json_download_includes_top_level_demo_admin_action_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-status.json").json()
    assert body["demo_admin_action_count"] == 8


def test_demo_export_bundle_status_json_includes_top_level_demo_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    import io
    import zipfile

    payload = build_demo_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        status = json.loads(archive.read(DEMO_STATUS_JSON_FILENAME))
    assert status["demo_admin_action_count"] == 8


def test_admin_app_js_demo_summary_prefers_top_level_demo_admin_action_count(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "data.demo_admin_action_count" in js.text


def test_demo_status_next_steps_mention_top_level_demo_admin_action_count(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "demo status json includes top-level demo_admin_action_count" in step.lower()
        for step in steps
    )


def test_deploy_checklist_demo_steps_mention_top_level_demo_admin_action_count(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any(
        "demo status json includes top-level demo_admin_action_count" in step.lower()
        for step in steps
    )
