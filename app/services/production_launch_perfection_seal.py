"""Production launch perfection seal — ceremony → seal → attest capstone (step 142)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.deploy_walkthrough import DEPLOY_EXPORT_ZIP_FILENAME
from app.services.production_go_live_record import seal_production_go_live_record
from app.services.production_launch_attestation import (
    PRODUCTION_LAUNCH_ATTESTATION_JSON_FILENAME,
    PRODUCTION_LAUNCH_ATTESTATION_MD_FILENAME,
    attest_production_launch,
    build_production_launch_attestation,
)
from app.services.production_launch_ceremony import (
    PRODUCTION_LAUNCH_CEREMONY_JSON_FILENAME,
    PRODUCTION_LAUNCH_CEREMONY_MD_FILENAME,
)
from app.services.production_perfection_capstone import (
    PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME,
    build_production_perfection_capstone,
)
from app.services.production_go_live_record import PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME

PRODUCTION_LAUNCH_PERFECTION_SEAL_JSON_FILENAME = "offercare-production-launch-perfection-seal.json"

_PERFECTION_SEAL_BUNDLE_ARTIFACTS = (
    "offercare-deploy-checklist.json",
    "offercare-deploy-checklist.csv",
    "offercare-demo-walkthrough.md",
    "offercare-demo-gates.json",
    "offercare-demo-gates.txt",
    "offercare-demo-status.json",
    "offercare-demo-status.csv",
    "offercare-maryland-production-runbook.json",
    "offercare-twilio-sms-production-runbook.json",
    "offercare-maryland-launch-capstone.json",
    "offercare-production-ops-dashboard.json",
    PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME,
    PRODUCTION_LAUNCH_CEREMONY_MD_FILENAME,
    PRODUCTION_LAUNCH_CEREMONY_JSON_FILENAME,
    PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME,
    PRODUCTION_LAUNCH_ATTESTATION_MD_FILENAME,
    PRODUCTION_LAUNCH_ATTESTATION_JSON_FILENAME,
    PRODUCTION_LAUNCH_PERFECTION_SEAL_JSON_FILENAME,
    "README.txt",
)

_PERFECTION_LAUNCH_SEAL: dict | None = None


def reset_production_launch_perfection_seal_for_tests() -> None:
    """Clear the in-process perfection seal (tests only)."""
    global _PERFECTION_LAUNCH_SEAL
    _PERFECTION_LAUNCH_SEAL = None


def get_production_launch_perfection_seal() -> dict | None:
    return _PERFECTION_LAUNCH_SEAL


def _status_label(ready: bool) -> str:
    return "READY" if ready else "NOT YET"


def build_production_launch_perfection_seal(db: Session) -> dict:
    perfection = build_production_perfection_capstone(db)
    perfection_summary = perfection["summary"]
    attestation = build_production_launch_attestation(db)
    attestation_summary = attestation["summary"]
    sealed = _PERFECTION_LAUNCH_SEAL
    bundle_file_count = len(_PERFECTION_SEAL_BUNDLE_ARTIFACTS)

    checks: list[dict] = []

    if perfection["production_perfection_ready"]:
        perf_status = "ready"
        perf_detail = "Production perfection green — ready for launch perfection seal"
        perf_action = None
    elif perfection_summary["blocked"] > 0:
        perf_status = "blocked"
        perf_detail = (
            f"Production perfection blocked — {perfection_summary['blocked']} blocker(s)"
        )
        perf_action = "Admin → Production perfection → Run production perfection check"
    else:
        perf_status = "warning"
        perf_detail = "Production perfection partial — complete ops and launch capstones first"
        perf_action = "Admin → Production perfection → Run production perfection check"
    checks.append(
        {
            "id": "production_perfection",
            "title": "Production perfection",
            "status": perf_status,
            "detail": perf_detail,
            "action": perf_action,
        }
    )

    if attestation["production_launch_attestation_ready"]:
        attest_status = "ready"
        attest_detail = (
            f"Launch attestation complete — digest `{attestation.get('digest_sha256', '—')[:16]}…`"
        )
        attest_action = None
    elif attestation_summary["blocked"] > 0:
        attest_status = "blocked"
        attest_detail = (
            f"Launch attestation blocked — {attestation_summary['blocked']} blocker(s)"
        )
        attest_action = "Complete go-live seal chain via launch perfection seal"
    else:
        attest_status = "warning"
        attest_detail = "Launch attestation pending — run launch perfection seal to chain ceremony → seal → attest"
        attest_action = "Admin → Production launch perfection seal → Seal launch perfection"
    checks.append(
        {
            "id": "production_launch_attestation",
            "title": "Production launch attestation",
            "status": attest_status,
            "detail": attest_detail,
            "action": attest_action,
        }
    )

    if sealed and sealed.get("seal_ok"):
        seal_status = "ready"
        seal_detail = (
            f"Launch perfection sealed at {sealed.get('sealed_at', '—')} — "
            "ceremony, go-live record, and attestation chained"
        )
        seal_action = None
    elif sealed:
        seal_status = "blocked"
        seal_detail = "Launch perfection seal attempted but failed — re-run after perfection is green"
        seal_action = "Admin → Production launch perfection seal → Seal launch perfection"
    elif perfection["production_perfection_ready"]:
        seal_status = "warning"
        seal_detail = (
            "Launch perfection seal pending — one-click ceremony → seal → attest for go-live capstone"
        )
        seal_action = "Admin → Production launch perfection seal → Seal launch perfection"
    else:
        seal_status = "blocked"
        seal_detail = "Launch perfection seal blocked — production perfection must be green first"
        seal_action = "Run production perfection check, then seal launch perfection"
    checks.append(
        {
            "id": "production_launch_perfection_seal",
            "title": "Production launch perfection seal",
            "status": seal_status,
            "detail": seal_detail,
            "action": seal_action,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")

    production_launch_perfection_ready = bool(sealed and sealed.get("seal_ok"))

    steps = [
        "Confirm production_perfection_ready is true on /health and Admin perfection panel",
        "Admin → Production launch perfection seal → Seal launch perfection — chains ceremony, go-live seal, and attestation",
        "Verify production_launch_perfection_ready on /health after seal completes",
        "Export launch perfection seal JSON for executive launch capstone archive",
        "Download deploy bundle (.zip) — full 19-file production archive including perfection seal",
        "Confirm production_launch_attestation_ready and production_go_live_record_ready on /health",
        "Retain SHA-256 digest from attestation chain for compliance verification",
        "Share worker landing /join URL with Maryland operations for go-live communications",
    ]

    capstone = {
        "production_launch_perfection_ready": production_launch_perfection_ready,
        "production_perfection_ready": perfection["production_perfection_ready"],
        "production_launch_attestation_ready": attestation["production_launch_attestation_ready"],
        "production_go_live_record_ready": attestation["production_go_live_record_ready"],
        "launch_ceremony_ready": attestation["launch_ceremony_ready"],
        "production_ops_ready": perfection["production_ops_ready"],
        "maryland_launch_ready": perfection["maryland_launch_ready"],
        "sealed": sealed is not None,
        "immutable": bool(sealed and sealed.get("immutable")),
        "seal_id": sealed.get("seal_id") if sealed else None,
        "sealed_at": sealed.get("sealed_at") if sealed else None,
        "record_id": sealed.get("record_id") if sealed else attestation.get("record_id"),
        "attestation_id": sealed.get("attestation_id") if sealed else attestation.get("attestation_id"),
        "digest_sha256": sealed.get("digest_sha256") if sealed else attestation.get("digest_sha256"),
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "production_perfection_ready": perfection["production_perfection_ready"],
            "production_launch_attestation_ready": attestation["production_launch_attestation_ready"],
            "production_go_live_record_ready": attestation["production_go_live_record_ready"],
            "launch_ceremony_ready": attestation["launch_ceremony_ready"],
            "live_scrapers_all_live": perfection_summary.get("live_scrapers_all_live"),
            "deploy_bundle_file_count": bundle_file_count,
            "deploy_bundle_filename": DEPLOY_EXPORT_ZIP_FILENAME,
            "perfection_seal_filename": PRODUCTION_LAUNCH_PERFECTION_SEAL_JSON_FILENAME,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
        "checks": checks,
        "steps": steps,
        "launch_urls": perfection["launch_urls"],
        "bundle_artifacts": list(_PERFECTION_SEAL_BUNDLE_ARTIFACTS),
        "production_launch_attestation": attestation,
        "production_perfection_capstone": perfection,
        "perfection_seal_record": sealed,
    }
    return capstone


def build_production_launch_perfection_seal_json(db: Session) -> dict:
    capstone = build_production_launch_perfection_seal(db)
    export_payload = {
        "production_launch_perfection_ready": capstone["production_launch_perfection_ready"],
        "production_perfection_ready": capstone["production_perfection_ready"],
        "production_launch_attestation_ready": capstone["production_launch_attestation_ready"],
        "production_go_live_record_ready": capstone["production_go_live_record_ready"],
        "launch_ceremony_ready": capstone["launch_ceremony_ready"],
        "sealed": capstone["sealed"],
        "immutable": capstone["immutable"],
        "seal_id": capstone["seal_id"],
        "sealed_at": capstone["sealed_at"],
        "record_id": capstone["record_id"],
        "attestation_id": capstone["attestation_id"],
        "digest_sha256": capstone["digest_sha256"],
        "summary": capstone["summary"],
        "checks": capstone["checks"],
        "launch_urls": capstone["launch_urls"],
        "bundle_artifacts": capstone["bundle_artifacts"],
        "perfection_seal_record": capstone["perfection_seal_record"],
        "go_live_seal": (capstone["perfection_seal_record"] or {}).get("go_live_seal"),
        "attestation": (capstone["perfection_seal_record"] or {}).get("attestation"),
    }
    return {
        "filename": PRODUCTION_LAUNCH_PERFECTION_SEAL_JSON_FILENAME,
        "content": json.dumps(export_payload, indent=2),
    }


def seal_production_launch_perfection(
    db: Session,
    *,
    phone_number: str | None = None,
    probe_scrapers: bool = True,
) -> dict:
    global _PERFECTION_LAUNCH_SEAL

    if _PERFECTION_LAUNCH_SEAL is not None and _PERFECTION_LAUNCH_SEAL.get("seal_ok"):
        capstone = build_production_launch_perfection_seal(db)
        return {
            "ok": True,
            "already_sealed": True,
            "production_launch_perfection_ready": True,
            "production_perfection_ready": capstone["production_perfection_ready"],
            "production_launch_attestation_ready": capstone["production_launch_attestation_ready"],
            "production_go_live_record_ready": capstone["production_go_live_record_ready"],
            "launch_ceremony_ready": capstone["launch_ceremony_ready"],
            "seal_id": _PERFECTION_LAUNCH_SEAL["seal_id"],
            "sealed_at": _PERFECTION_LAUNCH_SEAL["sealed_at"],
            "record_id": _PERFECTION_LAUNCH_SEAL.get("record_id"),
            "attestation_id": _PERFECTION_LAUNCH_SEAL.get("attestation_id"),
            "digest_sha256": _PERFECTION_LAUNCH_SEAL.get("digest_sha256"),
            "deploy_bundle_filename": capstone["summary"]["deploy_bundle_filename"],
            "deploy_bundle_file_count": capstone["summary"]["deploy_bundle_file_count"],
            "facility_name": _PERFECTION_LAUNCH_SEAL.get("facility_name"),
            "placement_id": _PERFECTION_LAUNCH_SEAL.get("placement_id"),
            "message": (
                f"Launch perfection already sealed at {_PERFECTION_LAUNCH_SEAL['sealed_at']} "
                f"(seal {_PERFECTION_LAUNCH_SEAL['seal_id']})"
            ),
        }

    perfection = build_production_perfection_capstone(db)
    if not perfection["production_perfection_ready"]:
        capstone = build_production_launch_perfection_seal(db)
        return {
            "ok": False,
            "already_sealed": False,
            "production_launch_perfection_ready": False,
            "production_perfection_ready": False,
            "production_launch_attestation_ready": capstone["production_launch_attestation_ready"],
            "production_go_live_record_ready": capstone["production_go_live_record_ready"],
            "launch_ceremony_ready": capstone["launch_ceremony_ready"],
            "seal_id": None,
            "sealed_at": None,
            "record_id": None,
            "attestation_id": None,
            "digest_sha256": None,
            "deploy_bundle_filename": DEPLOY_EXPORT_ZIP_FILENAME,
            "deploy_bundle_file_count": len(_PERFECTION_SEAL_BUNDLE_ARTIFACTS),
            "facility_name": None,
            "placement_id": None,
            "message": "Launch perfection seal failed — production perfection is not green",
        }

    go_live_result = seal_production_go_live_record(
        db,
        phone_number=phone_number,
        probe_scrapers=probe_scrapers,
    )
    if not go_live_result["ok"]:
        return {
            "ok": False,
            "already_sealed": False,
            "production_launch_perfection_ready": False,
            "production_perfection_ready": perfection["production_perfection_ready"],
            "production_launch_attestation_ready": False,
            "production_go_live_record_ready": go_live_result.get("production_go_live_record_ready", False),
            "launch_ceremony_ready": go_live_result.get("launch_ceremony_ready", False),
            "seal_id": None,
            "sealed_at": None,
            "record_id": go_live_result.get("record_id"),
            "attestation_id": None,
            "digest_sha256": None,
            "deploy_bundle_filename": go_live_result.get("deploy_bundle_filename", DEPLOY_EXPORT_ZIP_FILENAME),
            "deploy_bundle_file_count": go_live_result.get(
                "deploy_bundle_file_count", len(_PERFECTION_SEAL_BUNDLE_ARTIFACTS)
            ),
            "facility_name": go_live_result.get("facility_name"),
            "placement_id": go_live_result.get("placement_id"),
            "message": go_live_result.get("message") or "Launch perfection seal failed — go-live seal did not pass",
        }

    attest_result = attest_production_launch(db)
    if not attest_result["ok"]:
        return {
            "ok": False,
            "already_sealed": False,
            "production_launch_perfection_ready": False,
            "production_perfection_ready": perfection["production_perfection_ready"],
            "production_launch_attestation_ready": False,
            "production_go_live_record_ready": attest_result.get("production_go_live_record_ready", True),
            "launch_ceremony_ready": go_live_result.get("launch_ceremony_ready", True),
            "seal_id": None,
            "sealed_at": None,
            "record_id": attest_result.get("record_id"),
            "attestation_id": attest_result.get("attestation_id"),
            "digest_sha256": attest_result.get("digest_sha256"),
            "deploy_bundle_filename": attest_result.get("deploy_bundle_filename", DEPLOY_EXPORT_ZIP_FILENAME),
            "deploy_bundle_file_count": attest_result.get(
                "deploy_bundle_file_count", len(_PERFECTION_SEAL_BUNDLE_ARTIFACTS)
            ),
            "facility_name": go_live_result.get("facility_name"),
            "placement_id": go_live_result.get("placement_id"),
            "message": attest_result.get("message") or "Launch perfection seal failed — attestation did not pass",
        }

    sealed_at = datetime.now(timezone.utc).isoformat()
    seal_id = str(uuid.uuid4())

    _PERFECTION_LAUNCH_SEAL = {
        "seal_id": seal_id,
        "sealed_at": sealed_at,
        "immutable": True,
        "seal_ok": True,
        "go_live_seal": go_live_result,
        "attestation": attest_result,
        "record_id": attest_result.get("record_id"),
        "attestation_id": attest_result.get("attestation_id"),
        "digest_sha256": attest_result.get("digest_sha256"),
        "facility_name": go_live_result.get("facility_name"),
        "placement_id": go_live_result.get("placement_id"),
    }

    capstone = build_production_launch_perfection_seal(db)

    return {
        "ok": True,
        "already_sealed": False,
        "production_launch_perfection_ready": True,
        "production_perfection_ready": perfection["production_perfection_ready"],
        "production_launch_attestation_ready": True,
        "production_go_live_record_ready": True,
        "launch_ceremony_ready": go_live_result.get("launch_ceremony_ready", True),
        "seal_id": seal_id,
        "sealed_at": sealed_at,
        "record_id": attest_result.get("record_id"),
        "attestation_id": attest_result.get("attestation_id"),
        "digest_sha256": attest_result.get("digest_sha256"),
        "deploy_bundle_filename": capstone["summary"]["deploy_bundle_filename"],
        "deploy_bundle_file_count": capstone["summary"]["deploy_bundle_file_count"],
        "facility_name": go_live_result.get("facility_name"),
        "placement_id": go_live_result.get("placement_id"),
        "message": (
            "Production launch perfection sealed — ceremony, go-live record, and attestation chained "
            f"({capstone['summary']['deploy_bundle_file_count']} deploy bundle files)"
        ),
    }
