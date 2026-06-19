from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.seed import seed_pa_nursing_home_demo
from app.services.care_taxonomy import credential_options_for_state, credential_types_for_state
from app.services.shift_ranking import rank_offer_from_db


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_credential_types_for_state_excludes_gna_outside_md_dc() -> None:
    pa_types = credential_types_for_state("PA")
    md_types = credential_types_for_state("MD")
    assert "GNA" not in pa_types
    assert "GNA" in md_types
    assert "CNA" in pa_types


def test_credentials_endpoint_for_pennsylvania(client: TestClient) -> None:
    response = client.get("/api/care/credentials", params={"state": "PA"})
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "PA"
    assert body["gna_available"] is False
    codes = {row["code"] for row in body["credentials"]}
    assert "CNA" in codes
    assert "GNA" not in codes


def test_credentials_endpoint_for_maryland(client: TestClient) -> None:
    response = client.get("/api/care/credentials", params={"state": "MD"})
    assert response.status_code == 200
    body = response.json()
    assert body["gna_available"] is True
    codes = {row["code"] for row in body["credentials"]}
    assert "GNA" in codes


def test_credential_options_for_state_labels() -> None:
    options = credential_options_for_state("VA")
    assert all("code" in row and "label" in row for row in options)
    assert "GNA" not in {row["code"] for row in options}


def test_pa_nursing_home_seed_ranks_cna_for_gna_shift(db: Session) -> None:
    payload = seed_pa_nursing_home_demo(db)
    assert payload["state"] == "PA"
    ranking = rank_offer_from_db(db, UUID(payload["offer_id"]))
    assert ranking.ranked
    assert all(row.credential_type == "CNA" for row in ranking.ranked if row.credential_type != "LPN")
    assert any(row.credential_type == "CNA" for row in ranking.ranked)


def test_pa_nursing_home_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/pa-nursing-home")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "PA"
    assert body["facility_type"] == "NURSING_HOME"


def test_portal_apply_form_state_aware_credentials(client: TestClient) -> None:
    html = client.get("/portal/")
    assert html.status_code == 200
    assert "apply-credential-hint" in html.text
    js = client.get("/portal/app.js")
    assert js.status_code == 200
    text = js.text
    assert "loadCareTaxonomy" in text
    assert "refreshApplyCredentialOptions" in text
    assert "gna_license_states" in text
    assert "apply-state" in text


def test_admin_dashboard_includes_pa_nursing_home_seed(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "seed-pa-nursing-home-btn" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/pa-nursing-home" in js.text
