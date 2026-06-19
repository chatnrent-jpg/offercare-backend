from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import JobBoardCrisisListing, MarylandFacility
from app.services.crisis_indicator import list_job_board_crisis_listings, scan_job_board_crisis_leads
from app.services.job_board_crisis_scraper import fetch_job_board_listings, infer_shift_role, match_facility_name


def test_job_board_dry_run_returns_maryland_cna_lpn_listings() -> None:
    rows = fetch_job_board_listings()
    assert len(rows) >= 4
    assert all(row.state == "MD" for row in rows)
    assert any(row.shift_role == "CNA" for row in rows)
    assert any(row.days_open >= 30 for row in rows)


def test_infer_shift_role_from_title() -> None:
    assert infer_shift_role("Licensed Practical Nurse (LPN)") == "LPN"
    assert infer_shift_role("CNA Night Shift") == "CNA"
    assert infer_shift_role("Hospital Receptionist") is None


def test_match_facility_name_fuzzy() -> None:
    class Stub:
        def __init__(self, name: str):
            self.name = name

    matched = match_facility_name(
        "FutureCare Northpoint",
        [Stub("FutureCare at Northpoint"), Stub("Other SNF")],
    )
    assert matched is not None
    assert "Northpoint" in matched.name


def test_scan_job_board_crisis_persists_listings_and_flags_crisis() -> None:
    db = SessionLocal()
    try:
        facility = MarylandFacility(
            name="FutureCare Northpoint",
            facility_type="NURSING_HOME",
            county="Baltimore",
            state="MD",
        )
        db.add(facility)
        db.commit()
        result = scan_job_board_crisis_leads(db)
        assert result["listings_scraped"] >= 4
        assert result["crisis_listings"] >= 2
        listings = list_job_board_crisis_listings(db, limit=20)
        assert any(row["is_crisis"] for row in listings)
        assert any(row["days_open"] >= 30 for row in listings)
        crisis_rows = db.query(JobBoardCrisisListing).filter(JobBoardCrisisListing.is_crisis == "true").all()
        assert crisis_rows
    finally:
        db.close()


def test_job_board_scan_api(client: TestClient) -> None:
    response = client.post("/api/compliance/crisis/job-boards/scan")
    assert response.status_code == 200
    body = response.json()
    assert body["listings_scraped"] >= 4
    assert body["min_days_threshold"] == 30


def test_job_board_listings_api(client: TestClient) -> None:
    client.post("/api/compliance/crisis/job-boards/scan")
    rows = client.get("/api/compliance/crisis/job-boards/listings?limit=10").json()
    assert isinstance(rows, list)
    assert rows
    assert "facility_name" in rows[0]
    assert "is_crisis" in rows[0]


def test_admin_panel_renders_job_board_scan(client: TestClient) -> None:
    html = client.get("/admin").text
    assert "scan-job-boards-btn" in html
    assert "compliance-job-board-table" in html
    js = client.get("/admin/app.js").text
    assert "scanJobBoardCrisis" in js
    assert "/api/compliance/crisis/job-boards/scan" in js
    assert "renderComplianceJobBoards" in js
