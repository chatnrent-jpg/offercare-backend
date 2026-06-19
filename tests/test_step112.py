from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_ADMIN_ACTION_DEMO_GATES,
    DEMO_GATES_TXT_FILENAME,
    build_demo_export_bundle,
    build_demo_gates_txt,
    run_full_demo_setup,
)
from app.services.deploy_walkthrough import build_deploy_export_bundle


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_demo_gates_txt_includes_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_gates_txt(db)
    assert payload["filename"] == DEMO_GATES_TXT_FILENAME
    text = payload["content"]
    assert "Gate matrix:" in text
    assert "Demo admin actions:" in text
    assert "POST /api/seed/demo-setup" in text
    assert "status.demo_gates" in text
    assert "POST /api/seed/demo-lock-smoke" in text
    assert text.count("demo_status.demo_gates") == 5
    assert len(DEMO_ADMIN_ACTION_DEMO_GATES) == 8


def test_demo_gates_endpoint_clipboard_text_includes_demo_admin_actions_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    text = client.get("/api/seed/demo-gates").json()["clipboard_text"]
    assert "Demo admin actions:" in text
    assert "POST /api/seed/demo-push-subscriptions" in text


def test_demo_gates_txt_download_includes_demo_admin_actions_catalog(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-gates.txt")
    assert response.status_code == 200
    assert "Demo admin actions:" in response.text
    assert "Per-row Reset" in response.text


def test_demo_export_bundle_gates_txt_includes_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        txt = archive.read(DEMO_GATES_TXT_FILENAME).decode("utf-8")
    assert "Demo admin actions:" in txt
    assert "POST /api/seed/demo-reset-offer" in txt


def test_deploy_export_bundle_gates_txt_includes_demo_admin_actions_catalog(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        txt = archive.read(DEMO_GATES_TXT_FILENAME).decode("utf-8")
    assert "Demo admin actions:" in txt


def test_deploy_checklist_export_steps_mention_gates_txt_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["export_steps"]
    assert any(
        "demo gates (.txt) includes the demo admin actions catalog" in step.lower()
        for step in steps
    )


def test_demo_status_next_steps_mention_gates_txt_demo_admin_actions_catalog(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    assert any(
        "download demo gates (.txt) includes the demo admin actions catalog" in step.lower()
        for step in steps
    )
