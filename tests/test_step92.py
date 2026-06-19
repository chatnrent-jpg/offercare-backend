from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import DEMO_GATE_DEFINITIONS, run_full_demo_setup
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


def test_deploy_checklist_summary_includes_demo_gate_count_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    summary = build_deploy_checklist(db)["summary"]
    assert summary["demo_gate_count"] == len(DEMO_GATE_DEFINITIONS)
    assert summary["demo_gate_count"] == 9


def test_deploy_checklist_demo_item_mentions_gate_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    checklist = build_deploy_checklist(db)
    demo_item = next(row for row in checklist["items"] if row["id"] == "demo_environment")
    assert "confirmation gates: 9" in demo_item["detail"]


def test_deploy_checklist_endpoint_includes_demo_gate_count(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert summary["demo_gate_count"] == 9


def test_deploy_checklist_json_export_includes_demo_gate_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_checklist_json(db)
    assert payload["filename"] == DEPLOY_CHECKLIST_JSON_FILENAME
    body = json.loads(payload["content"])
    assert body["summary"]["demo_gate_count"] == 9


def test_deploy_bundle_readme_mentions_confirmation_gate_count(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        readme = archive.read("README.txt").decode("utf-8")
    assert "Confirmation gates configured: 9" in readme


def test_admin_deploy_summary_renders_demo_gate_count(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "demo_gate_count" in text
    assert "Demo gates" in text


def test_deploy_checklist_mentions_gate_count_in_demo_steps(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    assert any("confirmation gate count" in step.lower() for step in steps)
