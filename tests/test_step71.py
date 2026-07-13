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
    DEMO_GATES_JSON_FILENAME,
    DEMO_GATES_TXT_FILENAME,
    DEMO_STATUS_CSV_FILENAME,
    DEMO_STATUS_JSON_FILENAME,
    run_full_demo_setup,
)
from app.services.deploy_walkthrough import (
    DEPLOY_CHECKLIST_CSV_FILENAME,
    DEPLOY_CHECKLIST_JSON_FILENAME,
    DEPLOY_EXPORT_ZIP_FILENAME,
    build_deploy_checklist_csv,
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


def test_build_deploy_checklist_json_includes_summary_and_items(db: Session) -> None:
    payload = build_deploy_checklist_json(db)
    assert payload["filename"] == DEPLOY_CHECKLIST_JSON_FILENAME
    body = json.loads(payload["content"])
    assert "summary" in body
    assert "items" in body
    assert "export_steps" in body
    assert any(row["id"] == "database" for row in body["items"])


def test_build_deploy_checklist_csv_includes_summary_items_and_steps(db: Session) -> None:
    payload = build_deploy_checklist_csv(db)
    assert payload["filename"] == DEPLOY_CHECKLIST_CSV_FILENAME
    rows = list(csv.reader(io.StringIO(payload["content"])))
    assert rows[0] == ["DEPLOY CHECKLIST SUMMARY"]
    assert ["metric", "value"] in rows
    assert ["DEPLOY ITEMS"] in rows
    assert ["id", "title", "status", "detail", "action"] in rows
    assert ["TWILIO CONSOLE STEPS"] in rows
    assert ["DEMO STEPS"] in rows


def test_build_deploy_export_bundle_includes_checklist_and_demo_files(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    assert payload["filename"] == DEPLOY_EXPORT_ZIP_FILENAME
    assert payload["file_count"] == 7
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        names = set(archive.namelist())
    assert DEPLOY_CHECKLIST_JSON_FILENAME in names
    assert DEPLOY_CHECKLIST_CSV_FILENAME in names
    assert "offercare-demo-walkthrough.md" in names
    assert DEMO_GATES_JSON_FILENAME in names
    assert DEMO_GATES_TXT_FILENAME in names
    assert DEMO_STATUS_JSON_FILENAME in names
    assert DEMO_STATUS_CSV_FILENAME in names
    assert "README.txt" in names


def test_build_deploy_export_bundle_json_matches_checklist_snapshot(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        checklist = json.loads(archive.read(DEPLOY_CHECKLIST_JSON_FILENAME))
        demo_status = json.loads(archive.read(DEMO_STATUS_JSON_FILENAME))
        readme = archive.read("README.txt").decode("utf-8")
    assert checklist["summary"]["demo_health_status"] == "green"
    assert demo_status["health"]["status"] == "green"
    assert "VettedMe Deploy Bundle" in readme
    assert DEPLOY_CHECKLIST_JSON_FILENAME in readme
    assert "Active gates:" in readme
    assert DEMO_GATES_JSON_FILENAME in readme
    assert DEMO_GATES_TXT_FILENAME in readme


def test_deploy_checklist_json_download_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist.json")
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    assert DEPLOY_CHECKLIST_JSON_FILENAME in response.headers.get("content-disposition", "")
    body = response.json()
    assert "summary" in body
    assert "export_steps" in body


def test_deploy_checklist_csv_download_endpoint(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert DEPLOY_CHECKLIST_CSV_FILENAME in response.headers.get("content-disposition", "")
    assert "DEPLOY CHECKLIST SUMMARY" in response.text


def test_deploy_bundle_download_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/deploy/deploy-bundle.zip")
    assert response.status_code == 200
    assert "application/zip" in response.headers.get("content-type", "")
    assert DEPLOY_EXPORT_ZIP_FILENAME in response.headers.get("content-disposition", "")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert DEPLOY_CHECKLIST_JSON_FILENAME in archive.namelist()


def test_deploy_exports_require_admin_key(client: TestClient) -> None:
    json_response = client.get("/api/deploy/checklist.json", headers={"X-Admin-Key": "wrong-key"})
    csv_response = client.get("/api/deploy/checklist.csv", headers={"X-Admin-Key": "wrong-key"})
    zip_response = client.get("/api/deploy/deploy-bundle.zip", headers={"X-Admin-Key": "wrong-key"})
    assert json_response.status_code == 401
    assert csv_response.status_code == 401
    assert zip_response.status_code == 401


def test_admin_dashboard_includes_deploy_export_buttons(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "download-deploy-checklist-json-btn" in html.text
    assert "download-deploy-checklist-csv-btn" in html.text
    assert "download-deploy-bundle-btn" in html.text
    assert "Export checklist (.json)" in html.text
    assert "Download deploy bundle (.zip)" in html.text
    js = client.get("/admin/app.js")
    assert "/api/deploy/checklist.json" in js.text
    assert "/api/deploy/checklist.csv" in js.text
    assert "/api/deploy/deploy-bundle.zip" in js.text
    assert "confirmDemoReadyExport" in js.text


def test_deploy_checklist_includes_export_steps(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["export_steps"]
    assert any("export deploy checklist" in step.lower() for step in steps)
    assert any("deploy bundle" in step.lower() and "zip" in step.lower() for step in steps)
