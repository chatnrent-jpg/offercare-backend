from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.seed import seed_all_mid_atlantic_demos
from app.services.states import supported_states


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_seed_all_mid_atlantic_demos_loads_hospital_and_post_acute(db: Session) -> None:
    payload = seed_all_mid_atlantic_demos(db)
    assert payload["count"] == 10
    assert payload["hospital"]["count"] == 3
    assert payload["post_acute"]["count"] == 7
    assert set(payload["states"]) == set(supported_states())
    hospital_types = {row["facility_type"] for row in payload["hospital"]["demos"]}
    post_acute_types = {row["facility_type"] for row in payload["post_acute"]["demos"]}
    assert hospital_types == {"HOSPITAL"}
    assert post_acute_types == {"NURSING_HOME", "HOME_HEALTH"}
    snf_states = {
        row["state"] for row in payload["post_acute"]["demos"] if row["facility_type"] == "NURSING_HOME"
    }
    assert snf_states == set(supported_states())


def test_seed_all_mid_atlantic_demos_is_idempotent(db: Session) -> None:
    first = seed_all_mid_atlantic_demos(db)
    second = seed_all_mid_atlantic_demos(db)
    assert first["count"] == second["count"]
    first_ids = {row["offer_id"] for row in first["hospital"]["demos"]}
    first_ids |= {row["offer_id"] for row in first["post_acute"]["demos"]}
    second_ids = {row["offer_id"] for row in second["hospital"]["demos"]}
    second_ids |= {row["offer_id"] for row in second["post_acute"]["demos"]}
    assert first_ids == second_ids


def test_mid_atlantic_demos_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/mid-atlantic-demos")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 10
    assert body["hospital"]["count"] == 3
    assert body["post_acute"]["count"] == 7
    assert set(body["states"]) == set(supported_states())


def test_admin_dashboard_includes_mid_atlantic_demos_seed(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "seed-mid-atlantic-demos-btn" in html.text
    assert "Seed full demo environment" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/mid-atlantic-demos" in js.text


def test_deploy_checklist_mentions_full_demo_environment(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    body = response.json()
    hospital_steps = body["hospital_steps"]
    post_acute_steps = body["post_acute_steps"]
    assert any("Seed full demo environment" in step for step in hospital_steps)
    assert any("Seed full demo environment" in step for step in post_acute_steps)
