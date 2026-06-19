from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.seed import seed_all_hospital_demos


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_seed_all_hospital_demos_loads_md_va_nj_icus(db: Session) -> None:
    payload = seed_all_hospital_demos(db)
    assert payload["count"] == 3
    assert set(payload["states"]) == {"MD", "VA", "NJ"}
    assert all(row["facility_type"] == "HOSPITAL" for row in payload["demos"])


def test_seed_all_hospital_demos_is_idempotent(db: Session) -> None:
    first = seed_all_hospital_demos(db)
    second = seed_all_hospital_demos(db)
    assert first["count"] == second["count"]
    assert {row["offer_id"] for row in first["demos"]} == {row["offer_id"] for row in second["demos"]}


def test_hospital_demos_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/hospital-demos")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert set(body["states"]) == {"MD", "VA", "NJ"}


def test_admin_dashboard_includes_hospital_demos_seed(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "seed-hospital-demos-btn" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/hospital-demos" in js.text


def test_deploy_checklist_mentions_hospital_demos_seed(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["hospital_steps"]
    assert any("Seed all hospital demos" in step for step in steps)
