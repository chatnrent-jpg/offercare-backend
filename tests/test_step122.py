from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_ADMIN_ACTION_DEMO_GATES,
    build_demo_walkthrough_script,
    run_full_demo_setup,
)

PER_ACTION_DOC_PHRASES = [
    "run full demo setup returns status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "reset demo environment returns status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "per-row reset returns status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "lock test returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "notify matched returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "ensure demo portal logins returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "ensure demo push subscriptions returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
]


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_demo_status_next_steps_document_full_embedded_demo_gates_per_action(client: TestClient) -> None:
    steps = client.get("/api/seed/demo-status").json()["next_steps"]
    lowered = [step.lower() for step in steps]
    for phrase in PER_ACTION_DOC_PHRASES:
        assert any(phrase in step for step in lowered), phrase


def test_deploy_checklist_demo_steps_document_full_embedded_demo_gates_per_action(client: TestClient) -> None:
    steps = client.get("/api/deploy/checklist").json()["demo_steps"]
    lowered = [step.lower() for step in steps]
    for phrase in PER_ACTION_DOC_PHRASES:
        assert any(phrase in step for step in lowered), phrase


def test_demo_walkthrough_admin_action_lines_mention_embedded_snapshot_fields(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    markdown = build_demo_walkthrough_script(db)["markdown"]
    assert markdown.count("gate matrix, demo_admin_action_count, demo_admin_actions catalog)") == len(
        DEMO_ADMIN_ACTION_DEMO_GATES
    )
    assert "POST /api/seed/demo-setup" in markdown
    assert "POST /api/seed/demo-push-subscriptions" in markdown


def test_demo_walkthrough_download_admin_action_lines_mention_embedded_snapshot_fields(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    markdown = client.get("/api/seed/demo-walkthrough.md").text
    assert "gate matrix, demo_admin_action_count, demo_admin_actions catalog)" in markdown


def test_per_action_doc_phrase_count_matches_admin_action_catalog() -> None:
    assert len(PER_ACTION_DOC_PHRASES) == 7
    assert len(DEMO_ADMIN_ACTION_DEMO_GATES) == 8
