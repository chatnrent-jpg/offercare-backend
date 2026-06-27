"""Recruitment dashboard + Manus snapshot export."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.recruitment_dashboard import build_manus_recruitment_snapshot, build_recruitment_dashboard


def test_build_manus_recruitment_snapshot_shape() -> None:
    db = MagicMock()
    with patch(
        "app.services.recruitment_dashboard.build_recruitment_dashboard",
        return_value={
            "generated_at_utc": "2026-06-27T12:00:00+00:00",
            "summary": {"contracts_pending_review": 1},
            "drop_zones": {"raw_leads_csv": ["leads.csv"]},
            "manus_config": {"manus_workflows": [{"id": "rfp-rfq-monitor"}]},
            "contracts": [{"review_status": "PENDING_EXECUTIVE_REVIEW", "facility_name": "SNF A"}],
            "leads": [{"procurement_urgency": "HIGH", "facility_name": "Hospital B"}],
            "ingested_shifts": [],
        },
    ):
        snap = build_manus_recruitment_snapshot(db)
    assert snap["schema_version"] == "1.0"
    assert "manus_daily_prompt" in snap
    assert len(snap["contracts_pending_review"]) == 1
    assert len(snap["high_urgency_leads"]) == 1


def test_build_recruitment_dashboard_empty_db() -> None:
    db = MagicMock()
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.all.return_value = []
    with patch("app.services.recruitment_dashboard.ensure_data_engine_dirs"):
        payload = build_recruitment_dashboard(db, limit=10)
    assert payload["summary"]["contracts_total"] == 0
    assert "drop_zones" in payload
