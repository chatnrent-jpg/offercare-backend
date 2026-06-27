"""Backup routing engine — isolated disruption mitigation workflow (staging)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ACTIVE_SHIFTS_PATH = _REPO_ROOT / "logs" / "manus" / "active_shifts.json"
_DEFAULT_DISPATCH_LOG_PATH = _REPO_ROOT / "logs" / "manus" / "backup_dispatches.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_token(value: str) -> str:
    return str(value or "").strip().upper()


def _normalize_county(value: str) -> str:
    return str(value or "").strip().lower()


def _provider_id(applicant: dict[str, Any]) -> str:
    return str(applicant.get("license_number") or applicant.get("provider_id") or "").strip()


class BackupRoutingEngine:
    """Routes backup clinicians when an assigned provider cancels a shift."""

    def __init__(self, workforce_registry: dict[str, Any]) -> None:
        if not isinstance(workforce_registry, dict):
            raise TypeError("workforce_registry must be a dict from processed_providers.json")
        applicants = workforce_registry.get("applicants")
        if not isinstance(applicants, list):
            raise ValueError("workforce_registry must contain an applicants list")
        self.workforce_registry = dict(workforce_registry)
        self.applicants = list(applicants)

    def _find_shift(self, disrupted_shift_id: str, shifts: list[dict[str, Any]]) -> dict[str, Any] | None:
        token = str(disrupted_shift_id or "").strip()
        for shift in shifts:
            if str(shift.get("order_id") or "") == token:
                return shift
        return None

    def _is_active_compliant(self, applicant: dict[str, Any]) -> bool:
        return bool(applicant.get("compliant")) and bool(applicant.get("placement_eligible"))

    def _passes_gna_firewall(self, applicant: dict[str, Any], shift: dict[str, Any]) -> bool:
        facility_type = _normalize_token(str(shift.get("facility_type") or ""))
        required_role = _normalize_token(str(shift.get("required_role") or ""))
        license_type = _normalize_token(str(applicant.get("license_type") or ""))

        if facility_type == "SNF" and required_role == "CNA":
            if license_type != "CNA":
                return False
            return bool(applicant.get("has_gna_endorsement"))
        return True

    def _role_matches(self, applicant: dict[str, Any], shift: dict[str, Any]) -> bool:
        required_role = _normalize_token(str(shift.get("required_role") or ""))
        license_type = _normalize_token(str(applicant.get("license_type") or ""))
        return license_type == required_role

    def _county_matches(self, applicant: dict[str, Any], shift: dict[str, Any]) -> bool:
        facility_county = _normalize_county(str(shift.get("county") or ""))
        provider_county = _normalize_county(str(applicant.get("county") or ""))
        return bool(facility_county) and facility_county == provider_county

    def _rank_key(self, applicant: dict[str, Any]) -> tuple[int, str]:
        index = int(applicant.get("applicant_index") or 9999)
        verified = str(applicant.get("verification_timestamp") or "")
        return (index, verified)

    def _select_backup_candidates(
        self,
        shift: dict[str, Any],
        original_provider_id: str,
    ) -> list[dict[str, Any]]:
        excluded = str(original_provider_id or "").strip()
        eligible: list[dict[str, Any]] = []

        for applicant in self.applicants:
            provider_id = _provider_id(applicant)
            if not provider_id or provider_id == excluded:
                continue
            if not self._is_active_compliant(applicant):
                continue
            if not self._role_matches(applicant, shift):
                continue
            if not self._passes_gna_firewall(applicant, shift):
                continue
            if not self._county_matches(applicant, shift):
                continue
            eligible.append(applicant)

        eligible.sort(key=self._rank_key)
        top_two = eligible[:2]

        ranked: list[dict[str, Any]] = []
        for rank, applicant in enumerate(top_two, start=1):
            ranked.append(
                {
                    "rank": rank,
                    "provider_id": _provider_id(applicant),
                    "name": str(applicant.get("name") or ""),
                    "license_type": str(applicant.get("license_type") or ""),
                    "county": str(applicant.get("county") or ""),
                    "has_gna_endorsement": bool(applicant.get("has_gna_endorsement")),
                    "compliance_status": str(applicant.get("compliance_status") or ""),
                }
            )
        return ranked

    def _load_active_shifts(self, active_shifts_path: Path) -> list[dict[str, Any]]:
        if not active_shifts_path.is_file():
            raise FileNotFoundError(f"active shifts file not found: {active_shifts_path}")
        payload = json.loads(active_shifts_path.read_text(encoding="utf-8"))
        shifts = payload.get("shifts")
        if not isinstance(shifts, list):
            raise ValueError("active_shifts.json must contain a shifts list")
        return shifts

    def _persist_dispatch(
        self,
        dispatch_payload: dict[str, Any],
        dispatch_log_path: Path,
    ) -> None:
        dispatch_log_path.parent.mkdir(parents=True, exist_ok=True)

        if dispatch_log_path.is_file():
            existing = json.loads(dispatch_log_path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                raise ValueError("backup_dispatches.json must be a JSON object")
            dispatches = existing.get("dispatches")
            if not isinstance(dispatches, list):
                dispatches = []
        else:
            existing = {
                "mode": "STAGING",
                "live_execution": False,
                "product": "VettedCare.ai Backup Routing Engine",
                "dispatches": [],
            }
            dispatches = []

        dispatches.append(dispatch_payload)
        existing["dispatches"] = dispatches
        existing["count"] = len(dispatches)
        existing["updated_at_utc"] = _utc_now_iso()
        existing["live_execution"] = bool(dispatch_payload.get("live_execution")) or bool(
            existing.get("live_execution")
        )

        dispatch_log_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def trigger_backup_routing(
        self,
        disrupted_shift_id: str,
        original_provider_id: str,
        *,
        shift_override: dict[str, Any] | None = None,
        live_execution: bool = False,
        slice_key: str | None = None,
        active_shifts_path: Path | None = None,
        dispatch_log_path: Path | None = None,
    ) -> dict[str, Any]:
        if not disrupted_shift_id:
            raise ValueError("disrupted_shift_id is required")
        if not original_provider_id:
            raise ValueError("original_provider_id is required")

        log_path = dispatch_log_path or _DEFAULT_DISPATCH_LOG_PATH

        if shift_override is not None:
            shift = dict(shift_override)
        else:
            shifts_path = active_shifts_path or _DEFAULT_ACTIVE_SHIFTS_PATH
            shifts = self._load_active_shifts(shifts_path)
            shift = self._find_shift(disrupted_shift_id, shifts)
            if shift is None:
                raise ValueError(f"disrupted shift not found: {disrupted_shift_id}")

        backup_candidates = self._select_backup_candidates(shift, original_provider_id)
        status = "DISPATCH_STAGED" if backup_candidates else "NO_BACKUP_AVAILABLE"

        dispatch_payload = {
            "dispatch_id": f"backup-{disrupted_shift_id[:8]}-{_utc_now_iso()}",
            "disrupted_shift_id": disrupted_shift_id,
            "original_provider_id": original_provider_id,
            "status": status,
            "live_execution": bool(live_execution),
            "slice_key": slice_key,
            "staged_at_utc": _utc_now_iso(),
            "shift": {
                "order_id": shift.get("order_id") or disrupted_shift_id,
                "facility_name": shift.get("facility_name"),
                "facility_type": shift.get("facility_type"),
                "required_role": shift.get("required_role"),
                "county": shift.get("county"),
                "shift_timestamp": shift.get("shift_timestamp"),
            },
            "backup_candidates": backup_candidates,
            "routing_notes": (
                "Prioritized same-county compliant backups; SNF CNA GNA firewall enforced."
            ),
        }

        self._persist_dispatch(dispatch_payload, log_path)
        return dispatch_payload


def _mock_workforce_registry() -> dict[str, Any]:
    """Controlled registry for terminal self-test (two Montgomery CNA backups)."""
    return {
        "mode": "STAGING",
        "live_execution": False,
        "applicants": [
            {
                "applicant_index": 1,
                "name": "Aisha Thompson",
                "license_type": "CNA",
                "license_number": "CNA-MD-88421",
                "has_gna_endorsement": True,
                "county": "Montgomery",
                "compliant": True,
                "placement_eligible": True,
                "compliance_status": "COMPLIANT",
                "verification_timestamp": "2026-06-20T14:30:00+00:00",
            },
            {
                "applicant_index": 2,
                "name": "Nia Patterson",
                "license_type": "CNA",
                "license_number": "CNA-MD-99001",
                "has_gna_endorsement": True,
                "county": "Montgomery",
                "compliant": True,
                "placement_eligible": True,
                "compliance_status": "COMPLIANT",
                "verification_timestamp": "2026-06-21T10:00:00+00:00",
            },
            {
                "applicant_index": 3,
                "name": "Jordan Lee",
                "license_type": "CNA",
                "license_number": "CNA-MD-99002",
                "has_gna_endorsement": True,
                "county": "Montgomery",
                "compliant": True,
                "placement_eligible": True,
                "compliance_status": "COMPLIANT",
                "verification_timestamp": "2026-06-22T08:15:00+00:00",
            },
            {
                "applicant_index": 4,
                "name": "Brian Okafor",
                "license_type": "CNA",
                "license_number": "CNA-MD-77219",
                "has_gna_endorsement": False,
                "county": "Montgomery",
                "compliant": False,
                "placement_eligible": False,
                "compliance_status": "REJECTED_COMPLIANCE",
                "verification_timestamp": "2026-06-21T09:15:00+00:00",
            },
            {
                "applicant_index": 5,
                "name": "Elena Vasquez",
                "license_type": "CNA",
                "license_number": "CNA-MD-90331",
                "has_gna_endorsement": True,
                "county": "Anne Arundel",
                "compliant": True,
                "placement_eligible": True,
                "compliance_status": "COMPLIANT",
                "verification_timestamp": "2026-06-18T08:20:00+00:00",
            },
        ],
    }


def _mock_active_shifts_payload() -> dict[str, Any]:
    return {
        "mode": "STAGING",
        "shifts": [
            {
                "order_id": "sim-callout-montgomery-cna",
                "facility_name": "Arbor Ridge at Riderwood",
                "facility_type": "SNF",
                "county": "Montgomery",
                "required_role": "CNA",
                "shift_timestamp": "2026-06-27T07:00:00+00:00",
            }
        ],
    }


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        shifts_file = tmp_path / "active_shifts.json"
        dispatch_file = tmp_path / "backup_dispatches.json"
        shifts_file.write_text(json.dumps(_mock_active_shifts_payload(), indent=2), encoding="utf-8")

        engine = BackupRoutingEngine(_mock_workforce_registry())
        result = engine.trigger_backup_routing(
            disrupted_shift_id="sim-callout-montgomery-cna",
            original_provider_id="CNA-MD-88421",
            active_shifts_path=shifts_file,
            dispatch_log_path=dispatch_file,
        )

        assert result["status"] == "DISPATCH_STAGED"
        assert result["original_provider_id"] == "CNA-MD-88421"
        assert result["shift"]["facility_type"] == "SNF"
        assert result["shift"]["required_role"] == "CNA"
        assert result["shift"]["county"] == "Montgomery"
        assert len(result["backup_candidates"]) == 2
        assert result["backup_candidates"][0]["provider_id"] == "CNA-MD-99001"
        assert result["backup_candidates"][1]["provider_id"] == "CNA-MD-99002"
        assert "CNA-MD-88421" not in {c["provider_id"] for c in result["backup_candidates"]}
        assert "CNA-MD-77219" not in {c["provider_id"] for c in result["backup_candidates"]}
        assert "CNA-MD-90331" not in {c["provider_id"] for c in result["backup_candidates"]}

        log_payload = json.loads(dispatch_file.read_text(encoding="utf-8"))
        assert log_payload["mode"] == "STAGING"
        assert log_payload["live_execution"] is False
        assert len(log_payload["dispatches"]) == 1
        assert log_payload["dispatches"][0]["status"] == "DISPATCH_STAGED"

    print("BackupRoutingEngine self-test passed.")
    print("  call-out excluded original provider CNA-MD-88421")
    print("  SNF CNA GNA firewall blocked non-compliant Montgomery CNA")
    print("  cross-county CNA excluded; top 2 same-county backups ranked")
    print("  dispatch payload staged to backup_dispatches.json (temp sandbox)")
