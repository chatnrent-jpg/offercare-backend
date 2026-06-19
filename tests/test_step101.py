from __future__ import annotations

import csv
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import run_full_demo_setup
from app.services.deploy_walkthrough import (
    DEPLOY_CHECKLIST_CSV_FILENAME,
    DEPLOY_CHECKLIST_JSON_FILENAME,
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


def test_deploy_export_bundle_checklist_json_includes_demo_gates(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        checklist = json.loads(archive.read(DEPLOY_CHECKLIST_JSON_FILENAME))
    assert checklist["demo_gates"]["gate_count"] == 9
    assert "clipboard_text" in checklist["demo_gates"]


def test_deploy_export_bundle_checklist_csv_includes_demo_gate_matrix(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        csv_text = archive.read(DEPLOY_CHECKLIST_CSV_FILENAME).decode("utf-8")
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert ["DEMO GATES"] in rows
    assert ["DEMO GATE MATRIX"] in rows


def test_deploy_export_bundle_readme_mentions_embedded_demo_gates_in_checklist(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        readme = archive.read("README.txt").decode("utf-8")
    assert "embedded demo_gates" in readme
    assert "demo gate matrix" in readme
    assert DEPLOY_CHECKLIST_JSON_FILENAME in readme


def test_deploy_checklist_export_steps_mention_bundle_checklist_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any(
        "deploy bundle checklist" in step.lower() and "demo_gates" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_bundle_checklist_demo_gates(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "deploy bundle checklist" in step.lower() and "demo_gates" in step.lower()
        for step in steps
    )


def test_deploy_bundle_download_includes_demo_gates_in_checklist_json(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert DEPLOY_EXPORT_ZIP_FILENAME in response.headers.get("content-disposition", "")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        checklist = json.loads(archive.read(DEPLOY_CHECKLIST_JSON_FILENAME))
    assert checklist["demo_gates"]["gate_count"] == 9


def test_deploy_bundle_download_includes_demo_gate_matrix_in_checklist_csv(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        csv_text = archive.read(DEPLOY_CHECKLIST_CSV_FILENAME).decode("utf-8")
    assert "DEMO GATE MATRIX" in csv_text
