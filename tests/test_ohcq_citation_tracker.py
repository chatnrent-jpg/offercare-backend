from __future__ import annotations

from pathlib import Path

from data_engine.ohcq_citation_tracker import (
    FacilityRegistryRow,
    StaffingFlagRow,
    _is_staffing_citation,
    _norm_county,
    _registry_lookup,
    _resolve_registry_row,
    flags_from_cms_below_mandated_hours,
    flags_from_cms_staffing_citations,
    merge_staffing_flags,
    run_ohcq_staffing_citation_sweep,
    write_staffing_flags_csv,
)


def test_norm_county_strips_suffix() -> None:
    assert _norm_county("Montgomery County") == "Montgomery"
    assert _norm_county("baltimore city") == "Baltimore City"


def test_is_staffing_citation_detects_f725_tag() -> None:
    row = {
        "deficiency_tag_number": "0725",
        "deficiency_category": "Nursing and Physician Services Deficiencies",
        "deficiency_description": "Provide sufficient nursing staff.",
    }
    assert _is_staffing_citation(row) is True


def test_flags_from_cms_staffing_citations_enriches_county_from_registry() -> None:
    registry = [
        FacilityRegistryRow(
            facility_name="FutureCare Northpoint",
            facility_type="SNF",
            county="Baltimore",
            md_license_number="SNF-001",
        )
    ]
    registry_index = _registry_lookup(registry)
    citation = {
        "provider_name": "FutureCare Northpoint",
        "deficiency_tag_number": "0725",
        "deficiency_category": "Nursing and Physician Services Deficiencies",
        "deficiency_description": "Insufficient staffing shortage noted during survey.",
        "survey_date": "2026-02-01",
        "cms_certification_number_ccn": "215001",
    }
    flags = flags_from_cms_staffing_citations(
        [citation],
        registry_index=registry_index,
        scraped_at="2026-07-02T00:00:00+00:00",
    )
    assert len(flags) == 1
    assert flags[0].county == "Baltimore"
    assert flags[0].flag_reason == "insufficient_staffing_citation"
    assert flags[0].md_license_number == "SNF-001"


def test_flags_from_cms_below_mandated_hours() -> None:
    provider = {
        "provider_name": "Low Staff SNF",
        "countyparish": "Howard",
        "reported_total_nurse_staffing_hours_per_resident_per_day": "2.50",
        "casemix_total_nurse_staffing_hours_per_resident_per_day": "3.90",
        "staffing_rating": "1",
        "cms_certification_number_ccn": "215002",
    }
    flags = flags_from_cms_below_mandated_hours(
        [provider],
        registry_index=_registry_lookup([]),
        scraped_at="2026-07-02T00:00:00+00:00",
    )
    assert len(flags) == 1
    assert flags[0].flag_reason == "below_state_mandated_care_hours"
    assert flags[0].county == "Howard"


def test_merge_staffing_flags_deduplicates() -> None:
    row = StaffingFlagRow(
        facility_name="A",
        county="Montgomery",
        facility_type="SNF",
        flag_reason="insufficient_staffing_citation",
    )
    merged = merge_staffing_flags([row, row])
    assert len(merged) == 1


def test_resolve_registry_row_fuzzy_name() -> None:
    registry = [
        FacilityRegistryRow(
            facility_name="Autumn Lake Healthcare at Ballenger Creek",
            facility_type="SNF",
            county="Frederick",
            md_license_number="",
        )
    ]
    index = _registry_lookup(registry)
    resolved = _resolve_registry_row(
        facility_name="AUTUMN LAKE HEALTHCARE AT BALLENGER CREEK",
        registry_index=index,
    )
    assert resolved is not None
    assert resolved.county == "Frederick"


def test_dry_run_writes_csv(tmp_path: Path) -> None:
    output = tmp_path / "ohcq_flags.csv"
    summary = run_ohcq_staffing_citation_sweep(output_path=output, dry_run=True)
    assert summary["ok"] is True
    assert summary["flag_count"] == 2
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "facility_name" in text
    assert "Montgomery" in text


def test_flags_from_cms_low_staffing_rating_without_reported_hours() -> None:
    provider = {
        "provider_name": "Rating Only SNF",
        "countyparish": "Montgomery",
        "reported_total_nurse_staffing_hours_per_resident_per_day": "",
        "casemix_total_nurse_staffing_hours_per_resident_per_day": "",
        "staffing_rating": "1",
    }
    flags = flags_from_cms_below_mandated_hours(
        [provider],
        registry_index=_registry_lookup([]),
        scraped_at="2026-07-02T00:00:00+00:00",
    )
    assert len(flags) == 1
    assert flags[0].flag_reason == "low_staffing_rating"


def test_write_staffing_flags_csv(tmp_path: Path) -> None:
    output = tmp_path / "flags.csv"
    path = write_staffing_flags_csv(
        [
            StaffingFlagRow(
                facility_name="Test Facility",
                county="Prince George's",
                facility_type="ALF",
                flag_reason="insufficient_staffing_citation",
            )
        ],
        output,
    )
    assert path == output
    assert "Prince George's" in output.read_text(encoding="utf-8")
