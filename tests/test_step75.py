from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.deploy_walkthrough import (
    DEPLOY_CHECKLIST_JSON_FILENAME,
    build_deploy_checklist,
    build_deploy_export_bundle,
)
from app.services.demo_environment import run_full_demo_setup
from app.services.shift_lock import lock_shift_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_deploy_checklist_summary_includes_demo_facility_counts_after_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    checklist = build_deploy_checklist(db)
    summary = checklist["summary"]
    assert summary["demo_present_facility_count"] == 10
    assert summary["demo_broadcasting_count"] == 10
    assert summary["demo_expected_facility_count"] == 10


def test_deploy_checklist_summary_present_vs_broadcasting_when_one_locked(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    from app.services.demo_environment import build_demo_environment_status

    status = build_demo_environment_status(db)
    nj_offer = next(row for row in status["offers"] if row["facility_name"] == "Paramus SNF at Bergen")
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == nj_offer["demo_clinician_email"])
        .first()
    )
    lock_shift_for_provider(db, provider=provider, offer_id=UUID(nj_offer["offer_id"]))

    checklist = build_deploy_checklist(db)
    summary = checklist["summary"]
    assert summary["demo_present_facility_count"] == 10
    assert summary["demo_broadcasting_count"] == 9
    assert summary["demo_expected_facility_count"] == 10
    demo_item = next(row for row in checklist["items"] if row["id"] == "demo_environment")
    assert "10/10 present" in demo_item["detail"]
    assert "9/10 broadcasting" in demo_item["detail"]


def test_deploy_checklist_endpoint_includes_demo_facility_counts(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["demo_present_facility_count"] == 10
    assert summary["demo_broadcasting_count"] == 10
    assert summary["demo_expected_facility_count"] == 10


def test_deploy_checklist_json_export_includes_demo_facility_counts(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    from app.services.deploy_walkthrough import build_deploy_checklist_json
    import json

    payload = build_deploy_checklist_json(db)
    assert payload["filename"] == DEPLOY_CHECKLIST_JSON_FILENAME
    body = json.loads(payload["content"])
    assert body["summary"]["demo_present_facility_count"] == 10
    assert body["summary"]["demo_broadcasting_count"] == 10


def test_deploy_bundle_readme_mentions_demo_facility_counts(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    import io
    import zipfile

    payload = build_deploy_export_bundle(db)
    with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
        readme = archive.read("README.txt").decode("utf-8")
    assert "Demo facilities:" in readme
    assert "10/10 present" in readme
    assert "10/10 broadcasting" in readme


def test_admin_deploy_summary_renders_demo_facility_counts(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    text = js.text
    assert "demo_present_facility_count" in text
    assert "demo_broadcasting_count" in text
    assert "Demo present" in text
    assert "Demo broadcasting" in text


def test_deploy_checklist_mentions_present_vs_broadcasting_summary(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("present vs broadcasting" in step.lower() for step in steps)
