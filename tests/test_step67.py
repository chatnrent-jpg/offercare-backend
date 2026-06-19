from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.deploy_walkthrough import build_deploy_checklist
from app.services.demo_environment import run_full_demo_setup


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_deploy_checklist_includes_demo_environment_item(db: Session) -> None:
    checklist = build_deploy_checklist(db)
    item_ids = [row["id"] for row in checklist["items"]]
    assert "demo_environment" in item_ids
    demo_item = next(row for row in checklist["items"] if row["id"] == "demo_environment")
    assert demo_item["title"] == "Demo environment health"
    assert demo_item["status"] in {"ready", "warning", "blocked", "pending"}
    assert checklist["summary"]["demo_health_status"] in {"green", "yellow", "red", "pending"}
    assert checklist["summary"]["demo_health_label"]


def test_deploy_checklist_demo_environment_ready_after_full_setup(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    checklist = build_deploy_checklist(db)
    demo_item = next(row for row in checklist["items"] if row["id"] == "demo_environment")
    assert demo_item["status"] == "ready"
    assert checklist["summary"]["demo_health_status"] == "green"
    assert checklist["summary"]["demo_health_label"] == "READY"


def test_deploy_checklist_endpoint_includes_demo_health_after_setup(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    body = response.json()
    demo_item = next(row for row in body["items"] if row["id"] == "demo_environment")
    assert demo_item["status"] == "ready"
    assert body["summary"]["demo_health_status"] == "green"
    assert body["summary"]["demo_health_label"] == "READY"


def test_admin_deploy_summary_renders_demo_health(client: TestClient) -> None:
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "demo_health_label" in js.text
    assert "Demo health" in js.text


def test_deploy_checklist_mentions_auto_check(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("auto-check" in step.lower() and "demo" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_deploy_auto_check(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("deploy checklist" in step.lower() for step in steps)
