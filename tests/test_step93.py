from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_EXPORT_ZIP_FILENAME,
    DEMO_GATES_TXT_FILENAME,
    build_demo_export_bundle,
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


def test_build_demo_gates_txt_matches_clipboard_text(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_gates_txt(db)
    assert payload["filename"] == DEMO_GATES_TXT_FILENAME
    assert "VettedMe Demo Confirmation Gates" in payload["content"]
    assert "Gate matrix:" in payload["content"]


def test_demo_export_bundle_includes_gates_txt(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_export_bundle(db)
    assert payload["filename"] == DEMO_EXPORT_ZIP_FILENAME
    assert payload["file_count"] == 6
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        names = set(archive.namelist())
        txt = archive.read(DEMO_GATES_TXT_FILENAME).decode("utf-8")
        readme = archive.read("README.txt").decode("utf-8")
    assert DEMO_GATES_TXT_FILENAME in names
    assert "Gate matrix:" in txt
    assert DEMO_GATES_TXT_FILENAME in readme


def test_deploy_export_bundle_includes_gates_txt(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    assert payload["filename"] == DEPLOY_EXPORT_ZIP_FILENAME
    assert payload["file_count"] == 7
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        assert DEMO_GATES_TXT_FILENAME in archive.namelist()


def test_demo_gates_txt_download_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-gates.txt")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert DEMO_GATES_TXT_FILENAME in response.headers.get("content-disposition", "")
    assert "VettedMe Demo Confirmation Gates" in response.text
    assert "Gate matrix:" in response.text


def test_demo_gates_txt_download_requires_admin_key(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-gates.txt", headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 401


def test_admin_dashboard_includes_download_gates_txt_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "download-demo-gates-txt-btn" in html.text
    assert "Download gates (.txt)" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-gates.txt" in js.text
    assert DEMO_GATES_TXT_FILENAME in js.text


def test_deploy_checklist_mentions_demo_gates_txt_export(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any("demo-gates.txt" in step for step in steps)


def test_demo_status_next_steps_mention_gates_txt_in_bundle(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any("offercare-demo-gates.txt" in step for step in steps)
