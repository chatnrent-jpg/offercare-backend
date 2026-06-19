from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    SAMPLE_DEMO_CLINICIAN_EMAIL,
    build_demo_environment_status,
    build_demo_links,
    demo_portal_deep_link,
)
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_demo_portal_deep_link_formats_offer_query(client: TestClient) -> None:
    client.post("/api/seed/demo-setup")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    offers = [row for row in response.json()["offers"] if row["loaded"]]
    assert offers
    for row in offers:
        assert row["portal_deep_link"] == demo_portal_deep_link(row["offer_id"])
        assert "/portal/?offer=" in row["portal_deep_link"]


def test_build_demo_links_lists_all_loaded_offers(db: Session) -> None:
    from app.services.demo_environment import run_full_demo_setup

    run_full_demo_setup(db)
    payload = build_demo_links(db)
    assert payload["portal_login_url"] == "/portal/"
    assert payload["portal_password_hint"] == DEMO_PORTAL_PASSWORD
    assert payload["sample_clinician_email"] == SAMPLE_DEMO_CLINICIAN_EMAIL
    assert len(payload["offers"]) == 10
    assert all(row["portal_url"].startswith("/portal/?offer=") for row in payload["offers"])


def test_demo_links_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup")
    response = client.get("/api/seed/demo-links")
    assert response.status_code == 200
    body = response.json()
    assert body["portal_login_url"] == "/portal/"
    assert body["sample_clinician_email"] == SAMPLE_DEMO_CLINICIAN_EMAIL
    assert len(body["offers"]) == 10


def test_admin_dashboard_includes_copy_demo_links_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "copy-demo-links-btn" in html.text
    assert "Copy demo portal links" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-links" in js.text
    assert "portal_deep_link" in js.text


def test_deploy_checklist_mentions_demo_portal_deep_links(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("portal deep links" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_portal_deep_links(client: TestClient) -> None:
    client.post("/api/seed/demo-setup")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("portal deep links" in step.lower() for step in steps)
