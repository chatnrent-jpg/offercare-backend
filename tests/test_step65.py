from __future__ import annotations

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.demo_environment import (
    DEMO_STATUS_CSV_FILENAME,
    DEMO_STATUS_JSON_FILENAME,
    build_demo_status_csv,
    build_demo_status_json,
    run_full_demo_setup,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_demo_status_json_includes_health_and_offers(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_status_json(db)
    assert payload["filename"] == DEMO_STATUS_JSON_FILENAME
    body = json.loads(payload["content"])
    assert body["health"]["status"] == "green"
    assert len(body["offers"]) == 10
    assert len(body["clinicians"]) >= 10


def test_build_demo_status_csv_includes_summary_offers_and_clinicians(db: Session) -> None:
    run_full_demo_setup(db, notify_matched=False)
    payload = build_demo_status_csv(db)
    assert payload["filename"] == DEMO_STATUS_CSV_FILENAME
    rows = list(csv.reader(io.StringIO(payload["content"])))
    assert rows[0] == ["DEMO STATUS SUMMARY"]
    assert ["metric", "value"] in rows
    assert ["health_status", "green"] in rows
    assert ["DEMO OFFERS"] in rows
    assert ["DEMO CLINICIANS"] in rows
    offer_header = next(row for row in rows if row and row[0] == "facility_name")
    assert "demo_clinician_email" in offer_header
    paramus = next(row for row in rows if row and row[0] == "Paramus SNF at Bergen")
    assert paramus[1] == "NJ"


def test_demo_status_json_download_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status.json")
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    assert DEMO_STATUS_JSON_FILENAME in response.headers.get("content-disposition", "")
    body = response.json()
    assert body["health"]["status"] == "green"
    assert len(body["offers"]) == 10


def test_demo_status_csv_download_endpoint(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert DEMO_STATUS_CSV_FILENAME in response.headers.get("content-disposition", "")
    assert "Paramus SNF at Bergen" in response.text
    assert "health_status,green" in response.text.replace(" ", "")


def test_demo_status_exports_require_admin_key(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    json_response = client.get("/api/seed/demo-status.json", headers={"X-Admin-Key": "wrong-key"})
    csv_response = client.get("/api/seed/demo-status.csv", headers={"X-Admin-Key": "wrong-key"})
    assert json_response.status_code == 401
    assert csv_response.status_code == 401


def test_admin_dashboard_includes_status_export_buttons(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "download-demo-status-json-btn" in html.text
    assert "download-demo-status-csv-btn" in html.text
    assert "Export status (.json)" in html.text
    assert "Export status (.csv)" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/demo-status.json" in js.text
    assert "/api/seed/demo-status.csv" in js.text


def test_deploy_checklist_mentions_status_export(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    steps = response.json()["demo_steps"]
    assert any("export demo status" in step.lower() for step in steps)


def test_demo_status_next_steps_mention_status_export(client: TestClient) -> None:
    client.post("/api/seed/demo-setup?notify_matched=false")
    response = client.get("/api/seed/demo-status")
    assert response.status_code == 200
    steps = response.json()["next_steps"]
    assert any("export demo status" in step.lower() for step in steps)
