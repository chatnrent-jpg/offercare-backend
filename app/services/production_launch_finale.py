"""Production launch perfection finale — perfection seal + archive capstone (step 144)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.deploy_walkthrough import DEPLOY_EXPORT_ZIP_FILENAME
from app.services.production_launch_archive import (
    PRODUCTION_LAUNCH_ARCHIVE_JSON_FILENAME,
    archive_production_launch,
    build_production_launch_archive,
)
from app.services.production_launch_perfection_seal import (
    PRODUCTION_LAUNCH_PERFECTION_SEAL_JSON_FILENAME,
    build_production_launch_perfection_seal,
    seal_production_launch_perfection,
)
from app.services.production_perfection_capstone import build_production_perfection_capstone

PRODUCTION_LAUNCH_FINALE_JSON_FILENAME = "offercare-production-launch-finale.json"

_FINALE_BUNDLE_ARTIFACTS = (
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
    "offercare-production-perfection-capstone.json",
    "offercare-production-launch-ceremony.md",
    "offercare-production-launch-ceremony.json",
    "offercare-production-go-live-record.json",
    "offercare-production-launch-attestation.md",
    "offercare-production-launch-attestation.json",
    PRODUCTION_LAUNCH_PERFECTION_SEAL_JSON_FILENAME,
    PRODUCTION_LAUNCH_ARCHIVE_JSON_FILENAME,
    PRODUCTION_LAUNCH_FINALE_JSON_FILENAME,
    "README.txt",
)

_FINALE_LAUNCH: dict | None = None


def reset_production_launch_finale_for_tests() -> None:
    """Clear the in-process launch finale (tests only)."""
    global _FINALE_LAUNCH
    _FINALE_LAUNCH = None


def get_production_launch_finale() -> dict | None:
    return _FINALE_LAUNCH


def build_production_launch_finale(db: Session) -> dict:
    perfection = build_production_perfection_capstone(db)
    perfection_summary = perfection["summary"]
    launch_archive = build_production_launch_archive(db)
    archive_summary = launch_archive["summary"]
    finale = _FINALE_LAUNCH
    bundle_file_count = len(_FINALE_BUNDLE_ARTIFACTS)

    checks: list[dict] = []

    if launch_archive["production_launch_archive_ready"]:
        archive_status = "ready"
        archive_detail = (
            f"Launch archive complete — {launch_archive.get('artifact_count', '—')} artifacts with manifest digest"
        )
        archive_action = None
    elif archive_summary["blocked"] > 0:
        archive_status = "blocked"
        archive_detail = (
            f"Launch archive blocked — {archive_summary['blocked']} blocker(s)"
        )
        archive_action = "Admin → Production launch archive → Archive launch"
    else:
        archive_status = "warning"
        archive_detail = "Launch archive pending — run finale to seal perfection and archive bundle"
        archive_action = "Admin → Production launch perfection finale → Run launch finale"
    checks.append(
        {
            "id": "production_launch_archive",
            "title": "Production launch archive",
            "status": archive_status,
            "detail": archive_detail,
            "action": archive_action,
        }
    )

    if finale and finale.get("finale_ok"):
        finale_status = "ready"
        finale_detail = (
            f"Launch perfection finale complete at {finale.get('completed_at', '—')} — "
            "perfection seal and archive chained"
        )
        finale_action = None
    elif finale:
        finale_status = "blocked"
        finale_detail = "Launch finale attempted but failed — re-run after perfection is green"
        finale_action = "Admin → Production launch perfection finale → Run launch finale"
    elif launch_archive["production_launch_archive_ready"]:
        finale_status = "warning"
        finale_detail = "Launch finale pending — one-click perfection seal + archive for go-live capstone"
        finale_action = "Admin → Production launch perfection finale → Run launch finale"
    elif perfection["production_perfection_ready"]:
        finale_status = "warning"
        finale_detail = "Launch finale pending — chains perfection seal then archive in one action"
        finale_action = "Admin → Production launch perfection finale → Run launch finale"
    else:
        finale_status = "blocked"
        finale_detail = "Launch finale blocked — production perfection must be green first"
        finale_action = "Run production perfection check, then run launch finale"
    checks.append(
        {
            "id": "production_launch_finale",
            "title": "Production launch perfection finale",
            "status": finale_status,
            "detail": finale_detail,
            "action": finale_action,
        }
    )

    if perfection["production_perfection_ready"]:
        perf_status = "ready"
        perf_detail = "Production perfection green — ready for launch perfection finale"
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

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")

    production_launch_finale_ready = bool(finale and finale.get("finale_ok"))

    steps = [
        "Confirm production_perfection_ready is true on /health and Admin perfection panel",
        "Admin → Production launch perfection finale → Run launch finale — chains perfection seal + archive",
        "Verify production_launch_finale_ready on /health after finale completes",
        "Export launch finale JSON for executive go-live capstone archive",
        "Download deploy bundle (.zip) — full 21-file production archive including finale snapshot",
        "Confirm production_launch_archive_ready and production_launch_perfection_ready on /health",
        "Use launch archive manifest checksums to verify deploy bundle artifact integrity",
        "Share worker landing /join URL with Maryland operations for go-live communications",
    ]

    capstone = {
        "production_launch_finale_ready": production_launch_finale_ready,
        "production_launch_archive_ready": launch_archive["production_launch_archive_ready"],
        "production_launch_perfection_ready": launch_archive["production_launch_perfection_ready"],
        "production_launch_attestation_ready": launch_archive["production_launch_attestation_ready"],
        "production_go_live_record_ready": launch_archive["production_go_live_record_ready"],
        "launch_ceremony_ready": launch_archive["launch_ceremony_ready"],
        "production_perfection_ready": perfection["production_perfection_ready"],
        "completed": finale is not None,
        "immutable": bool(finale and finale.get("immutable")),
        "finale_id": finale.get("finale_id") if finale else None,
        "completed_at": finale.get("completed_at") if finale else None,
        "manifest_digest": launch_archive.get("manifest_digest"),
        "artifact_count": launch_archive.get("artifact_count"),
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "production_perfection_ready": perfection["production_perfection_ready"],
            "production_launch_archive_ready": launch_archive["production_launch_archive_ready"],
            "deploy_bundle_file_count": bundle_file_count,
            "deploy_bundle_filename": DEPLOY_EXPORT_ZIP_FILENAME,
            "finale_json_filename": PRODUCTION_LAUNCH_FINALE_JSON_FILENAME,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
        "checks": checks,
        "steps": steps,
        "launch_urls": perfection["launch_urls"],
        "bundle_artifacts": list(_FINALE_BUNDLE_ARTIFACTS),
        "production_launch_archive": launch_archive,
        "production_perfection_capstone": perfection,
        "finale_record": finale,
    }
    return capstone


def build_production_launch_finale_json(db: Session) -> dict:
    capstone = build_production_launch_finale(db)
    export_payload = {
        "production_launch_finale_ready": capstone["production_launch_finale_ready"],
        "production_launch_archive_ready": capstone["production_launch_archive_ready"],
        "production_launch_perfection_ready": capstone["production_launch_perfection_ready"],
        "production_perfection_ready": capstone["production_perfection_ready"],
        "completed": capstone["completed"],
        "immutable": capstone["immutable"],
        "finale_id": capstone["finale_id"],
        "completed_at": capstone["completed_at"],
        "manifest_digest": capstone["manifest_digest"],
        "artifact_count": capstone["artifact_count"],
        "summary": capstone["summary"],
        "checks": capstone["checks"],
        "launch_urls": capstone["launch_urls"],
        "bundle_artifacts": capstone["bundle_artifacts"],
        "finale_record": capstone["finale_record"],
        "perfection_seal": (capstone["finale_record"] or {}).get("perfection_seal"),
        "archive": (capstone["finale_record"] or {}).get("archive"),
    }
    return {
        "filename": PRODUCTION_LAUNCH_FINALE_JSON_FILENAME,
        "content": json.dumps(export_payload, indent=2),
    }


def run_production_launch_finale(
    db: Session,
    *,
    phone_number: str | None = None,
    probe_scrapers: bool = True,
) -> dict:
    global _FINALE_LAUNCH

    if _FINALE_LAUNCH is not None and _FINALE_LAUNCH.get("finale_ok"):
        capstone = build_production_launch_finale(db)
        return {
            "ok": True,
            "already_completed": True,
            "production_launch_finale_ready": True,
            "production_launch_archive_ready": capstone["production_launch_archive_ready"],
            "production_launch_perfection_ready": capstone["production_launch_perfection_ready"],
            "production_perfection_ready": capstone["production_perfection_ready"],
            "finale_id": _FINALE_LAUNCH["finale_id"],
            "completed_at": _FINALE_LAUNCH["completed_at"],
            "manifest_digest": _FINALE_LAUNCH.get("manifest_digest"),
            "artifact_count": _FINALE_LAUNCH.get("artifact_count"),
            "deploy_bundle_filename": capstone["summary"]["deploy_bundle_filename"],
            "deploy_bundle_file_count": capstone["summary"]["deploy_bundle_file_count"],
            "facility_name": _FINALE_LAUNCH.get("facility_name"),
            "placement_id": _FINALE_LAUNCH.get("placement_id"),
            "message": (
                f"Launch finale already completed at {_FINALE_LAUNCH['completed_at']} "
                f"(finale {_FINALE_LAUNCH['finale_id']})"
            ),
        }

    perfection = build_production_perfection_capstone(db)
    if not perfection["production_perfection_ready"]:
        capstone = build_production_launch_finale(db)
        return {
            "ok": False,
            "already_completed": False,
            "production_launch_finale_ready": False,
            "production_launch_archive_ready": capstone["production_launch_archive_ready"],
            "production_launch_perfection_ready": capstone["production_launch_perfection_ready"],
            "production_perfection_ready": False,
            "finale_id": None,
            "completed_at": None,
            "manifest_digest": None,
            "artifact_count": capstone.get("artifact_count"),
            "deploy_bundle_filename": DEPLOY_EXPORT_ZIP_FILENAME,
            "deploy_bundle_file_count": len(_FINALE_BUNDLE_ARTIFACTS),
            "facility_name": None,
            "placement_id": None,
            "message": "Launch finale failed — production perfection is not green",
        }

    seal_result = seal_production_launch_perfection(
        db,
        phone_number=phone_number,
        probe_scrapers=probe_scrapers,
    )
    if not seal_result["ok"]:
        return {
            "ok": False,
            "already_completed": False,
            "production_launch_finale_ready": False,
            "production_launch_archive_ready": False,
            "production_launch_perfection_ready": seal_result.get("production_launch_perfection_ready", False),
            "production_perfection_ready": perfection["production_perfection_ready"],
            "finale_id": None,
            "completed_at": None,
            "manifest_digest": seal_result.get("digest_sha256"),
            "artifact_count": None,
            "deploy_bundle_filename": seal_result.get("deploy_bundle_filename", DEPLOY_EXPORT_ZIP_FILENAME),
            "deploy_bundle_file_count": seal_result.get(
                "deploy_bundle_file_count", len(_FINALE_BUNDLE_ARTIFACTS)
            ),
            "facility_name": seal_result.get("facility_name"),
            "placement_id": seal_result.get("placement_id"),
            "message": seal_result.get("message") or "Launch finale failed — perfection seal did not pass",
        }

    archive_result = archive_production_launch(db)
    if not archive_result["ok"]:
        return {
            "ok": False,
            "already_completed": False,
            "production_launch_finale_ready": False,
            "production_launch_archive_ready": archive_result.get("production_launch_archive_ready", False),
            "production_launch_perfection_ready": True,
            "production_perfection_ready": perfection["production_perfection_ready"],
            "finale_id": None,
            "completed_at": None,
            "manifest_digest": archive_result.get("manifest_digest"),
            "artifact_count": archive_result.get("artifact_count"),
            "deploy_bundle_filename": archive_result.get("deploy_bundle_filename", DEPLOY_EXPORT_ZIP_FILENAME),
            "deploy_bundle_file_count": archive_result.get(
                "deploy_bundle_file_count", len(_FINALE_BUNDLE_ARTIFACTS)
            ),
            "facility_name": seal_result.get("facility_name"),
            "placement_id": seal_result.get("placement_id"),
            "message": archive_result.get("message") or "Launch finale failed — archive did not pass",
        }

    completed_at = datetime.now(timezone.utc).isoformat()
    finale_id = str(uuid.uuid4())

    _FINALE_LAUNCH = {
        "finale_id": finale_id,
        "completed_at": completed_at,
        "immutable": True,
        "finale_ok": True,
        "perfection_seal": seal_result,
        "archive": archive_result,
        "manifest_digest": archive_result.get("manifest_digest"),
        "artifact_count": archive_result.get("artifact_count"),
        "facility_name": seal_result.get("facility_name"),
        "placement_id": seal_result.get("placement_id"),
    }

    capstone = build_production_launch_finale(db)

    return {
        "ok": True,
        "already_completed": False,
        "production_launch_finale_ready": True,
        "production_launch_archive_ready": True,
        "production_launch_perfection_ready": True,
        "production_perfection_ready": perfection["production_perfection_ready"],
        "finale_id": finale_id,
        "completed_at": completed_at,
        "manifest_digest": archive_result.get("manifest_digest"),
        "artifact_count": archive_result.get("artifact_count"),
        "deploy_bundle_filename": capstone["summary"]["deploy_bundle_filename"],
        "deploy_bundle_file_count": capstone["summary"]["deploy_bundle_file_count"],
        "facility_name": seal_result.get("facility_name"),
        "placement_id": seal_result.get("placement_id"),
        "message": (
            "Production launch perfection finale complete — perfection seal and archive chained "
            f"({capstone['summary']['deploy_bundle_file_count']} deploy bundle files)"
        ),
    }
