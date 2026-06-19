from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_ADMIN_ACTION_DEMO_GATES,
    DEMO_GATES_JSON_FILENAME,
    build_demo_export_bundle,
    build_demo_gates_json,
    run_full_demo_setup,
)
from app.services.deploy_walkthrough import build_deploy_checklist, build_deploy_export_bundle


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_demo_gates_json_includes_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_gates_json(db)
    assert payload["filename"] == DEMO_GATES_JSON_FILENAME
    body = json.loads(payload["content"])
    actions = body["demo_admin_actions"]
    assert len(actions) == len(DEMO_ADMIN_ACTION_DEMO_GATES)
    assert actions[0]["endpoint"] == "POST /api/seed/demo-setup"
    assert actions[0]["field"] == "status.demo_gates"
    assert any(row["endpoint"] == "POST /api/seed/demo-lock-smoke" for row in actions)


def test_deploy_checklist_demo_gates_includes_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    demo_gates = build_deploy_checklist(db)["demo_gates"]
    assert demo_gates is not None
    assert len(demo_gates["demo_admin_actions"]) == 8
    assert demo_gates["demo_admin_actions"][3]["field"] == "demo_status.demo_gates"


def test_demo_gates_endpoint_includes_demo_admin_actions_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-gates").json()
    assert len(body["demo_admin_actions"]) == 8
    assert body["demo_admin_actions"][7]["endpoint"] == "POST /api/seed/demo-push-subscriptions"


def test_demo_gates_json_download_includes_demo_admin_actions_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    body = client.get("/api/seed/demo-gates.json").json()
    assert any(row["action"] == "Per-row Reset" for row in body["demo_admin_actions"])


def test_demo_export_bundle_gates_json_includes_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    import io
    import zipfile

    payload = build_demo_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        gates = json.loads(archive.read(DEMO_GATES_JSON_FILENAME))
    assert len(gates["demo_admin_actions"]) == 8


def test_deploy_export_bundle_gates_json_includes_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    import io
    import zipfile

    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        gates = json.loads(archive.read(DEMO_GATES_JSON_FILENAME))
    assert gates["demo_admin_actions"][0]["field"] == "status.demo_gates"


def test_deploy_checklist_export_steps_mention_gates_json_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any(
        "demo gates json includes the demo admin actions catalog" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_gates_json_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "export demo gates json includes the demo admin actions catalog" in step.lower()
        for step in steps
    )
