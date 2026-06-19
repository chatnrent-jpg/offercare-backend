from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility, OfferCareJobOffer, VmsShiftIngestionLog
from app.services.vms_shift_ingestion import ingest_vms_shifts, persist_vms_shifts, run_vms_ingestion
from app.services.vms_types import VmsShiftRecord


def _sample_record() -> VmsShiftRecord:
    token = uuid4().hex[:8]
    return VmsShiftRecord(
        external_id=f"test-shift-{token}",
        facility_name="FutureCare Northpoint",
        shift_role="CNA",
        hourly_pay_rate=33.0,
        shift_starts_at=datetime.now(timezone.utc),
        source="SHIFTWISE",
    )


def test_dry_run_fetches_shiftwise_and_fieldglass_shifts() -> None:
    rows = ingest_vms_shifts()
    assert len(rows) >= 3
    sources = {row.source for row in rows}
    assert "SHIFTWISE" in sources
    assert "FIELDGLASS" in sources
    assert all(row.hourly_pay_rate > 0 for row in rows)


def test_persist_vms_shifts_creates_offers_for_matched_facilities() -> None:
    db = SessionLocal()
    try:
        db.add(
            MarylandFacility(
                name="FutureCare Northpoint",
                facility_type="NURSING_HOME",
                county="Baltimore",
                state="MD",
            )
        )
        db.add(
            MarylandFacility(
                name="Genesis HealthCare Baltimore Center",
                facility_type="NURSING_HOME",
                county="Baltimore",
                state="MD",
            )
        )
        db.commit()
        token = uuid4().hex[:6]
        records = [
            VmsShiftRecord(
                external_id=f"fc-{token}",
                facility_name="FutureCare Northpoint",
                shift_role="CNA",
                hourly_pay_rate=34.0,
                shift_starts_at=datetime.now(timezone.utc),
                source="SHIFTWISE",
            ),
            VmsShiftRecord(
                external_id=f"gh-{token}",
                facility_name="Genesis HealthCare Baltimore Center",
                shift_role="LPN",
                hourly_pay_rate=45.0,
                shift_starts_at=datetime.now(timezone.utc),
                source="FIELDGLASS",
            ),
        ]
        result = persist_vms_shifts(db, records)
        assert result["offers_created"] == 2
        logs = db.query(VmsShiftIngestionLog).filter(VmsShiftIngestionLog.status == "INGESTED").all()
        assert len(logs) >= 2
    finally:
        db.close()


def test_persist_skips_duplicate_external_ids() -> None:
    db = SessionLocal()
    try:
        db.add(
            MarylandFacility(
                name="FutureCare Northpoint",
                facility_type="NURSING_HOME",
                county="Baltimore",
                state="MD",
            )
        )
        db.commit()
        record = _sample_record()
        first = persist_vms_shifts(db, [record])
        second = persist_vms_shifts(db, [record])
        assert first["offers_created"] == 1
        assert second["offers_skipped"] == 1
    finally:
        db.close()


def test_vms_ingest_api_creates_offers(client: TestClient) -> None:
    client.post(
        "/api/facilities",
        json={
            "name": "CommuniCare Silver Spring",
            "facility_type": "NURSING_HOME",
            "county": "Montgomery",
            "state": "MD",
        },
    )
    response = client.post("/api/vms/shifts/ingest?persist=true")
    assert response.status_code == 200
    body = response.json()
    assert body["shifts_fetched"] >= 3
    assert body["offers_created"] + body["offers_skipped"] + body["skipped_no_facility"] >= 3


def test_vms_ingest_log_api(client: TestClient) -> None:
    client.post("/api/vms/shifts/ingest?persist=true")
    rows = client.get("/api/vms/shifts/ingest/log?limit=10").json()
    assert isinstance(rows, list)
    assert rows
    assert "status" in rows[0]
    assert "source" in rows[0]


def test_admin_renders_vms_ingest_log(client: TestClient) -> None:
    js = client.get("/admin/app.js").text
    assert "renderComplianceVmsIngest" in js
    assert "/api/vms/shifts/ingest" in js
    html = client.get("/admin").text
    assert "compliance-vms-ingest-table" in html
