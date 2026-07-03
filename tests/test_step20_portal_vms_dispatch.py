"""Portal step 20 — VMS dispatch status and demo auto-submit."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import PORTAL_BUILD_ID
from app.models import MarylandProvider
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, SAMPLE_DEMO_PORTAL_EMAIL
from app.services.demo_portal_lockable import repair_demo_portal_placements
from app.services.vms_submission import (
    list_clinician_placements,
    submit_demo_clinician_placements_to_vms,
    vms_status_label,
)


def test_vms_status_label_maps_pending_and_submitted() -> None:
    assert vms_status_label("PENDING") == "Queued for VMS dispatch"
    assert vms_status_label("SUBMITTED") == "Confirmed with facility"


def test_portal_step20_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert "placements-vms-summary" in html
    assert "vmsStatusBadge" in js
    assert "Dispatch" in js


def test_demo_placements_auto_dispatch(client: TestClient) -> None:
    login = client.post(
        "/api/clinicians/login",
        json={"email": SAMPLE_DEMO_PORTAL_EMAIL, "password": DEMO_PORTAL_PASSWORD},
    )
    if login.status_code == 401:
        pytest.skip("demo login unavailable in this database")
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/clinicians/me/placements", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    if not rows:
        pytest.skip("no demo placements to dispatch")
    row = rows[0]
    assert "vms_status_label" in row
    assert row["vms_submission_status"] in {"PENDING", "SUBMITTED", "FAILED"}


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_submit_demo_clinician_placements_to_vms(db: Session) -> None:
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == SAMPLE_DEMO_PORTAL_EMAIL)
        .first()
    )
    if provider is None:
        pytest.skip("demo CNA unavailable")
    repair_demo_portal_placements(db, provider)
    before = list_clinician_placements(db, provider.provider_id)
    if not before:
        pytest.skip("no demo placements")
    dispatched = submit_demo_clinician_placements_to_vms(db, provider)
    after = list_clinician_placements(db, provider.provider_id)
    assert dispatched >= 0
    if before and str(before[0]["vms_submission_status"]).upper() == "PENDING":
        assert after[0]["vms_submission_status"] == "SUBMITTED"
        assert after[0]["vms_external_ref"]
