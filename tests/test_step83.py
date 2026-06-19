from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_EXPORT_ZIP_FILENAME,
    DEMO_GATES_JSON_FILENAME,
    DEMO_GATES_TXT_FILENAME,
    build_demo_export_bundle,
    build_demo_gates_json,
    build_demo_gates_txt,
    run_full_demo_setup,
)
from app.services.deploy_walkthrough import (
    DEPLOY_EXPORT_ZIP_FILENAME,
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


def test_build_demo_gates_json_matches_summary(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_gates_json(db)
    assert payload["filename"] == DEMO_GATES_JSON_FILENAME
    body = json.loads(payload["content"])
    assert body["walkthrough_intact"] is True
    assert body["health_status"] == "green"
    assert "reset_environment" in body["active_gates"]
    assert len(body["gates"]) == 9


def test_demo_export_bundle_includes_gates_json(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_export_bundle(db)
    assert payload["filename"] == DEMO_EXPORT_ZIP_FILENAME
    assert payload["file_count"] == 6
    assert "reset_environment" in payload["active_gates"]
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        gates = json.loads(archive.read(DEMO_GATES_JSON_FILENAME))
        readme = archive.read("README.txt").decode("utf-8")
    assert gates["health_status"] == "green"
    assert DEMO_GATES_JSON_FILENAME in readme
    assert "Active gates:" in readme


def test_deploy_export_bundle_includes_gates_json(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    assert payload["filename"] == DEPLOY_EXPORT_ZIP_FILENAME
    assert payload["file_count"] == 7
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        names = set(archive.namelist())
        gates = json.loads(archive.read(DEMO_GATES_JSON_FILENAME))
        readme = archive.read("README.txt").decode("utf-8")
    assert DEMO_GATES_JSON_FILENAME in names
    assert DEMO_GATES_TXT_FILENAME in names
    assert gates["walkthrough_intact"] is True
    assert "Active gates:" in readme
    assert DEMO_GATES_JSON_FILENAME in readme
    assert DEMO_GATES_TXT_FILENAME in readme


def test_demo_gates_json_download_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-gates.json")
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    assert DEMO_GATES_JSON_FILENAME in response.headers.get("content-disposition", "")
    body = response.json()
    assert body["health_status"] == "green"
    assert body["active_gates"]


def test_demo_gates_json_download_requires_admin_key(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-gates.json", headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 401


def test_demo_bundle_download_includes_gates_json(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-bundle.zip")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert DEMO_GATES_JSON_FILENAME in archive.namelist()


def test_deploy_checklist_mentions_demo_gates_json_export(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["export_steps"]
    assert any("demo-gates.json" in step for step in steps)


def test_demo_status_next_steps_mention_gates_in_bundle(client: TestClient) -> None:
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("gates json" in step.lower() for step in steps)
