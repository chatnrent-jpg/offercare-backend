from __future__ import annotations

from data_engine.md_county_normalizer import normalize_md_county
from data_engine.md_ohcq_leads_pipeline import (
    county_normalization_report,
    integration_keys_status,
    run_md_ohcq_leads_pipeline,
)


def test_normalize_adelphi_to_prince_georges() -> None:
    result = normalize_md_county("Adelphi")
    assert result.normalized == "Prince George's"
    assert result.verified is True
    assert result.source == "city_map"


def test_normalize_official_county_passthrough() -> None:
    result = normalize_md_county("Anne Arundel")
    assert result.normalized == "Anne Arundel"
    assert result.verified is True


def test_integration_keys_status_shape() -> None:
    keys = integration_keys_status()
    assert "CLAY_TABLE_WEBHOOK_URL" in keys
    assert "HEYREACH_API_KEY" in keys
    assert keys["CLAY_TABLE_WEBHOOK_URL"]["set"] is False


def test_county_report_on_live_flags() -> None:
    from data_engine.paths import LEADS_DIR

    report = county_normalization_report(LEADS_DIR / "ohcq_staffing_citation_flags_md.csv")
    assert report["total"] >= 300
    assert report["verified"] >= report["total"] - 50


def test_offline_pipeline_build() -> None:
    summary = run_md_ohcq_leads_pipeline(skip_tracker=True, limit=5, dry_run=True)
    assert summary["ok"] is True
    assert summary["mode"] == "offline_build"
    clay = next(s for s in summary["steps"] if s["step"] == "clay_enrichment")
    assert clay["status"] == "staging_ready"
    heyreach = next(s for s in summary["steps"] if s["step"] == "heyreach_sequence")
    assert heyreach["status"] == "completed"
    assert heyreach["heyreach_leads"] == 5
