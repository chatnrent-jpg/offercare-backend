from __future__ import annotations

from data_engine.heyreach_outreach import (
    build_heyreach_don_leads,
    compliance_hook,
    county_phrase,
    load_heyreach_config,
    read_clay_enriched_leads,
    render_messages_for_lead,
    run_heyreach_ohcq_sequence_build,
)


def test_county_phrase_baltimore_city() -> None:
    assert county_phrase("Baltimore City") == "in Baltimore City"
    assert county_phrase("Montgomery") == "in Montgomery County"
    assert county_phrase("") == "across Maryland"


def test_compliance_hook_variants() -> None:
    assert "citation" in compliance_hook("insufficient_staffing_citation")
    assert "shortfall" in compliance_hook("below_state_mandated_care_hours")


def test_render_messages_inserts_county_dynamically() -> None:
    config = load_heyreach_config()
    messages = render_messages_for_lead(
        {
            "facility_name": "ADELPHI NURSING AND REHABILITATION CENTER",
            "county": "Prince George's",
            "flag_reason": "insufficient_staffing_citation",
            "don_full_name": "Patricia Hughes",
        },
        config=config,
    )
    body = messages["linkedin_connection_request.body"]
    assert "Prince George's County" in body
    assert "15 minutes" in body
    assert "GNAs and LPNs" in body
    assert "staffing citation" in messages["email_follow_up.body"].lower() or "citation" in messages["email_follow_up.body"].lower()


def test_build_leads_from_flags_fallback(tmp_path) -> None:
    flags = tmp_path / "flags.csv"
    flags.write_text(
        "facility_name,county,facility_type,flag_reason,don_full_name,don_verified_email,don_linkedin_url\n"
        "Test SNF,Howard,SNF,insufficient_staffing_citation,Jane Doe,jane@test.org,https://linkedin.com/in/jane\n",
        encoding="utf-8",
    )
    rows = read_clay_enriched_leads(flags_path=flags, enriched_path=tmp_path / "missing.csv")
    leads = build_heyreach_don_leads(rows, config=load_heyreach_config())
    assert len(leads) == 1
    assert leads[0].county_phrase == "in Howard County"
    assert "Howard County" in leads[0].email_body


def test_run_sequence_build_from_live_flags_csv() -> None:
    summary = run_heyreach_ohcq_sequence_build(limit=2, dry_run=True)
    assert summary["ok"] is True
    assert summary["heyreach_leads"] == 2
    assert summary["import_csv"].endswith("heyreach_md_don_ohcq_import.csv")
    assert "linkedin_connection_request" in summary["channels"]
