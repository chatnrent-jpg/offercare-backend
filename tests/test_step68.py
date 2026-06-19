from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_EXPORT_README_FILENAME,
    DEMO_EXPORT_ZIP_FILENAME,
    DEMO_STATUS_CSV_FILENAME,
    DEMO_STATUS_JSON_FILENAME,
    build_demo_export_bundle,
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


def test_build_demo_export_bundle_includes_walkthrough_and_status_files(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_export_bundle(db)
    assert payload["filename"] == DEMO_EXPORT_ZIP_FILENAME
    assert payload["file_count"] == 6
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        names = set(archive.namelist())
    assert "offercare-demo-walkthrough.md" in names
    assert "offercare-demo-gates.json" in names
    assert "offercare-demo-gates.txt" in names
    assert DEMO_STATUS_JSON_FILENAME in names
    assert DEMO_STATUS_CSV_FILENAME in names
    assert DEMO_EXPORT_README_FILENAME in names


def test_build_demo_export_bundle_json_matches_status_snapshot(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        status = json.loads(archive.read(DEMO_STATUS_JSON_FILENAME))
        markdown = archive.read("offercare-demo-walkthrough.md").decode("utf-8")
        readme = archive.read(DEMO_EXPORT_README_FILENAME).decode("utf-8")
    assert status["health"]["status"] == "green"
    assert len(status["offers"]) == 10
    assert "# OfferCare Mid-Atlantic Demo Walkthrough" in markdown
    assert "Health: READY (green)" in readme
    assert "Active gates:" in readme


def test_demo_bundle_download_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-bundle.zip")
    assert response.status_code == 200
    assert "application/zip" in response.headers.get("content-type", "")
    assert DEMO_EXPORT_ZIP_FILENAME in response.headers.get("content-disposition", "")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert DEMO_STATUS_CSV_FILENAME in archive.namelist()


def test_demo_bundle_download_requires_admin_key(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-bundle.zip", headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 401


def test_admin_dashboard_includes_download_bundle_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "download-demo-bundle-btn" in html.text
    assert "Download demo bundle (.zip)" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-bundle.zip" in js.text


def test_deploy_checklist_mentions_demo_bundle(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("bundle" in step.lower() and "zip" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_demo_bundle(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("bundle" in step.lower() for step in steps)
