"""Lookahead-safe shift matching — delegates to shared shift_match_core."""

from __future__ import annotations

from typing import Any

from strategy.shift_match_core import rank_compliant_matches


class LookaheadShiftMatcher:
    """Backward-compatible wrapper around unified ranking core."""

    def __init__(self, candidates: list[dict[str, Any]]) -> None:
        if not isinstance(candidates, list):
            raise TypeError("candidates must be a list of profile dicts")
        self.candidates = list(candidates)

    def find_compliant_matches(
        self,
        shift_request: dict[str, Any],
        evaluation_timestamp: str,
    ) -> list[dict[str, Any]]:
        return rank_compliant_matches(self.candidates, shift_request, evaluation_timestamp)


def _mock_candidates() -> list[dict[str, Any]]:
    return [
        {
            "provider_id": "cna-001",
            "full_name": "Alice Compliant",
            "role": "CNA",
            "county": "Baltimore",
            "has_gna_endorsement": True,
            "license_verified_at": "2026-06-20T10:00:00+00:00",
            "background_check_verified_at": "2026-06-20T11:00:00+00:00",
            "placement_eligible": True,
        },
        {
            "provider_id": "cna-002",
            "full_name": "Bob No GNA",
            "role": "CNA",
            "county": "Baltimore",
            "has_gna_endorsement": False,
            "license_verified_at": "2026-06-20T10:00:00+00:00",
            "background_check_verified_at": "2026-06-20T11:00:00+00:00",
            "placement_eligible": True,
        },
        {
            "provider_id": "cna-003",
            "full_name": "Carla Lookahead Violation",
            "role": "CNA",
            "county": "Montgomery",
            "has_gna_endorsement": True,
            "license_verified_at": "2026-06-25T15:00:00+00:00",
            "background_check_verified_at": "2026-06-20T11:00:00+00:00",
            "placement_eligible": True,
        },
        {
            "provider_id": "cna-004",
            "full_name": "Diana Montgomery GNA",
            "role": "CNA",
            "county": "Montgomery",
            "has_gna_endorsement": True,
            "license_verified_at": "2026-06-18T09:00:00+00:00",
            "background_check_verified_at": "2026-06-18T09:30:00+00:00",
            "placement_eligible": True,
        },
        {
            "provider_id": "lpn-001",
            "full_name": "Evan LPN",
            "role": "LPN",
            "county": "Baltimore",
            "has_gna_endorsement": False,
            "license_verified_at": "2026-06-19T08:00:00+00:00",
            "background_check_verified_at": "2026-06-19T08:30:00+00:00",
            "placement_eligible": True,
        },
    ]


if __name__ == "__main__":
    matcher = LookaheadShiftMatcher(_mock_candidates())

    snf_shift = {
        "facility_type": "SNF",
        "required_role": "CNA",
        "facility_county": "Montgomery",
        "evaluation_window_barrier": "2026-06-24T23:59:59+00:00",
    }
    evaluation_ts = "2026-06-24T23:59:59+00:00"

    snf_matches = matcher.find_compliant_matches(snf_shift, evaluation_ts)
    snf_ids = [row["provider_id"] for row in snf_matches]

    assert "cna-002" not in snf_ids, "SNF CNA without GNA must be dropped"
    assert "cna-003" not in snf_ids, "post-barrier license verification must be dropped"
    assert snf_ids == ["cna-004", "cna-001"], "county match (Montgomery) must rank first"
    assert snf_matches[0]["provider_id"] == "cna-004"
    assert snf_matches[0]["_match_meta"]["county_match"] is True

    lpn_shift = {
        "facility_type": "SNF",
        "required_role": "LPN",
        "facility_county": "Baltimore",
        "evaluation_window_barrier": "2026-06-24T23:59:59+00:00",
    }
    lpn_matches = matcher.find_compliant_matches(lpn_shift, evaluation_ts)
    assert [row["provider_id"] for row in lpn_matches] == ["lpn-001"]

    alf_shift = {
        "facility_type": "ALF",
        "required_role": "CNA",
        "facility_county": "Baltimore",
        "evaluation_window_barrier": "2026-06-24T23:59:59+00:00",
    }
    alf_matches = matcher.find_compliant_matches(alf_shift, evaluation_ts)
    alf_ids = [row["provider_id"] for row in alf_matches]
    assert "cna-002" in alf_ids, "ALF CNA is not subject to SNF GNA firewall"
    assert "cna-003" not in alf_ids, "lookahead barrier still applies for ALF"

    print("LookaheadShiftMatcher self-test passed.")
    print(f"SNF/CNA matches: {snf_ids}")
    print(f"LPN matches: {[row['provider_id'] for row in lpn_matches]}")
    print(f"ALF/CNA matches: {alf_ids}")
