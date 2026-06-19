from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.seed import seed_all_post_acute_demos
from app.services.states import supported_states


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_seed_all_post_acute_demos_loads_six_state_snfs_and_md_home_health(db: Session) -> None:
    payload = seed_all_post_acute_demos(db)
    assert payload["count"] == 7
    states = set(payload["states"])
    assert states == {"MD", "VA", "DC", "PA", "DE", "NJ"}
    facility_types = {row["facility_type"] for row in payload["demos"]}
    assert facility_types == {"NURSING_HOME", "HOME_HEALTH"}
    snf_states = {row["state"] for row in payload["demos"] if row["facility_type"] == "NURSING_HOME"}
    assert snf_states == set(supported_states())


def test_seed_all_post_acute_demos_is_idempotent(db: Session) -> None:
    first = seed_all_post_acute_demos(db)
    second = seed_all_post_acute_demos(db)
    assert first["count"] == second["count"]
    assert {row["offer_id"] for row in first["demos"]} == {row["offer_id"] for row in second["demos"]}


def test_post_acute_demos_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/post-acute-demos")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 7
    assert len(body["demos"]) == 7
    assert set(body["states"]) == {"MD", "VA", "DC", "PA", "DE", "NJ"}


def test_admin_dashboard_includes_post_acute_demos_seed(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "seed-post-acute-demos-btn" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/post-acute-demos" in js.text


def test_deploy_checklist_mentions_post_acute_demos_seed(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["post_acute_steps"]
    assert any("Seed all post-acute demos" in step for step in steps)
