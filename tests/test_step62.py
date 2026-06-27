from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import build_demo_walkthrough_script, run_full_demo_setup


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_demo_walkthrough_script_includes_filename(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    script = build_demo_walkthrough_script(db)
    assert script["filename"] == "offercare-demo-walkthrough.md"
    assert script["offer_count"] == 10


def test_demo_walkthrough_download_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-walkthrough.md")
    assert response.status_code == 200
    assert "text/markdown" in response.headers.get("content-type", "")
    assert "offercare-demo-walkthrough.md" in response.headers.get("content-disposition", "")
    body = response.text
    assert "# VettedCare Mid-Atlantic Demo Walkthrough" in body
    assert "Paramus SNF at Bergen" in body
    assert "/portal/?offer=" in body


def test_demo_walkthrough_download_requires_admin_key(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-walkthrough.md", headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 401


def test_admin_dashboard_includes_download_walkthrough_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "download-demo-walkthrough-btn" in html.text
    assert "Download walkthrough (.md)" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-walkthrough.md" in js.text
    assert "downloadAdminFile" in js.text


def test_deploy_checklist_mentions_download_walkthrough(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("download" in step.lower() and "walkthrough" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_download_walkthrough(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("download" in step.lower() for step in steps)
