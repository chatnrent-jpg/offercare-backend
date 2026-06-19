from __future__ import annotations

import csv
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_ADMIN_ACTION_DEMO_GATES,
    run_full_demo_setup,
)
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


def test_demo_health_includes_admin_action_count_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    from app.services.demo_environment import build_demo_environment_status

    health = build_demo_environment_status(db)["health"]
    assert health["demo_admin_action_count"] == len(DEMO_ADMIN_ACTION_DEMO_GATES)
    assert health["demo_admin_action_count"] == 8


def test_deploy_checklist_summary_includes_demo_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    summary = build_deploy_checklist(db)["summary"]
    assert summary["demo_admin_action_count"] == 8


def test_deploy_checklist_demo_item_mentions_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    checklist = build_deploy_checklist(db)
    demo_item = next(row for row in checklist["items"] if row["id"] == "demo_environment")
    assert "admin actions: 8" in demo_item["detail"]


def test_deploy_checklist_json_export_includes_demo_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_checklist_json(db)
    body = json.loads(payload["content"])
    assert body["summary"]["demo_admin_action_count"] == 8


def test_demo_status_csv_includes_health_demo_admin_action_count(db: Session) -> None:
    from app.services.demo_environment import build_demo_status_csv

    run_full_demo_setup(db, notify_matched=False)
    rows = list(csv.reader(io.StringIO(build_demo_status_csv(db)["content"])))
    assert ["health_demo_admin_action_count", "8"] in rows


def test_deploy_checklist_endpoint_includes_demo_admin_action_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/deploy/checklist").json()
    assert body["summary"]["demo_admin_action_count"] == 8


def test_demo_status_endpoint_includes_health_demo_admin_action_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    health = client.get("/api/seed/demo-status").json()["health"]
    assert health["demo_admin_action_count"] == 8


def test_admin_app_js_renders_demo_admin_action_count(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "demo_admin_action_count" in text
    assert "Admin actions" in text
    assert "demo-health-admin-actions" in text


def test_deploy_bundle_readme_mentions_demo_admin_action_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        readme = archive.read("README.txt").decode("utf-8")
    assert "Demo admin actions catalog: 8 actions" in readme


def test_deploy_checklist_demo_steps_mention_admin_action_count(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any("demo admin action count" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_admin_action_count(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any("demo admin action count" in step.lower() for step in steps)
