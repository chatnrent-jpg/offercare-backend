from __future__ import annotations

from pathlib import Path

from data_engine.clay_ohcq_enrichment import (
    ClayOhcqLeadRow,
    build_v3_records_payload,
    build_webhook_payload,
    load_clay_config,
    read_ohcq_citation_csv,
    run_clay_ohcq_enrichment_push,
)


def test_read_ohcq_citation_csv_deduplicates(tmp_path: Path) -> None:
    csv_path = tmp_path / "flags.csv"
    csv_path.write_text(
        "facility_name,county,facility_type,flag_reason,deficiency_summary,md_license_number,cms_ccn\n"
        "Alpha SNF,Montgomery,SNF,insufficient_staffing_citation,Short staffed,MD-1,215001\n"
        "Alpha SNF,Montgomery,SNF,insufficient_staffing_citation,Duplicate,MD-1,215001\n"
        "Beta SNF,Howard,SNF,below_state_mandated_care_hours,Low HPRD,MD-2,215002\n",
        encoding="utf-8",
    )
    rows = read_ohcq_citation_csv(csv_path)
    assert len(rows) == 2
    assert rows[0].search_location == "Montgomery County, Maryland, United States"
    assert rows[1].county == "Howard"


def test_webhook_payload_uses_clay_column_names() -> None:
    row = ClayOhcqLeadRow(
        facility_name="Test SNF",
        county="Baltimore City",
        facility_type="SNF",
        flag_reason="insufficient_staffing_citation",
        deficiency_summary="Staffing shortage",
        md_license_number="MD-99",
        cms_ccn="215099",
        search_location="Baltimore City, Maryland, United States",
        record_id="ohcq-test-baltimore-city",
    )
    payload = build_webhook_payload([row])[0]
    assert payload["Facility Name"] == "Test SNF"
    assert payload["Maryland County"] == "Baltimore City"
    assert payload["Search Location"] == "Baltimore City, Maryland, United States"


def test_load_clay_config_has_target_roles() -> None:
    config = load_clay_config()
    roles = config.get("target_roles") or []
    role_ids = {role.get("role_id") for role in roles}
    assert "don" in role_ids
    assert "hr_staffing_coordinator" in role_ids
    enrichments = config.get("enrichment_columns") or []
    assert any(col.get("clay_action") == "Find People at Company" for col in enrichments)


def test_build_v3_records_payload_shape() -> None:
    row = ClayOhcqLeadRow(
        facility_name="Gamma SNF",
        county="Frederick",
        facility_type="SNF",
        flag_reason="low_staffing_rating",
        deficiency_summary="",
        md_license_number="",
        cms_ccn="",
        search_location="Frederick County, Maryland, United States",
        record_id="ohcq-gamma-frederick",
    )
    body = build_v3_records_payload([row], field_map={"facility_name": "fld_abc"})
    assert "records" in body
    assert body["records"][0]["id"] == "ohcq-gamma-frederick"
    assert body["records"][0]["cells"]["fld_abc"] == "Gamma SNF"


def test_run_clay_push_dry_run_from_live_csv() -> None:
    summary = run_clay_ohcq_enrichment_push(dry_run=True, limit=3)
    assert summary["ok"] is True
    assert summary["input_rows"] == 3
    assert summary["push"]["dry_run"] is True
    assert "Director of Nursing" in summary["target_roles"][0]
