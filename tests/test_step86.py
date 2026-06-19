from __future__ import annotations

import io
import json
import zipfile
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.deploy_walkthrough import (
    DEPLOY_CHECKLIST_JSON_FILENAME,
    build_deploy_checklist,
    build_deploy_checklist_json,
    build_deploy_export_bundle,
)
from app.services.demo_environment import build_demo_environment_status, run_full_demo_setup
from app.services.shift_lock import lock_shift_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_deploy_checklist_summary_includes_walkthrough_intact_and_active_gates(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    summary = build_deploy_checklist(db)["summary"]
    assert summary["demo_walkthrough_intact"] is True
    assert "reset_environment" in summary["demo_active_gates"]
    assert "notify_matched" in summary["demo_active_gates"]
    assert "ensure_portal" in summary["demo_active_gates"]
    assert "ensure_push" in summary["demo_active_gates"]


def test_deploy_checklist_summary_when_one_locked_shift(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    status = build_demo_environment_status(db)
    offer = status["offers"][0]
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(offer["offer_id"]))

    checklist = build_deploy_checklist(db)
    summary = checklist["summary"]
    assert summary["demo_walkthrough_intact"] is True
    assert "export_walkthrough" in summary["demo_active_gates"]
    assert "copy_demo_links" in summary["demo_active_gates"]
    assert "reset_offer" in summary["demo_active_gates"]
    demo_item = next(row for row in checklist["items"] if row["id"] == "demo_environment")
    assert "active gates:" in demo_item["detail"].lower()


def test_deploy_checklist_endpoint_includes_gate_summary(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    summary = client.get("/api/deploy/checklist").json()["summary"]
    assert summary["demo_walkthrough_intact"] is True
    assert summary["demo_active_gates"]


def test_deploy_checklist_json_export_includes_gate_summary(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_checklist_json(db)
    assert payload["filename"] == DEPLOY_CHECKLIST_JSON_FILENAME
    body = json.loads(payload["content"])
    assert body["summary"]["demo_walkthrough_intact"] is True
    assert body["summary"]["demo_active_gates"]


def test_deploy_bundle_readme_mentions_walkthrough_intact(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        readme = archive.read("README.txt").decode("utf-8")
    assert "Walkthrough intact: yes" in readme
    assert "Active gates:" in readme


def test_admin_deploy_summary_renders_gate_summary(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "demo_walkthrough_intact" in text
    assert "demo_active_gates" in text
    assert "Walkthrough intact" in text
    assert "Active gates" in text


def test_deploy_checklist_mentions_gate_summary_in_demo_steps(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any(
        "walkthrough intact" in step.lower() and "active confirmation gates" in step.lower()
        for step in steps
    )
