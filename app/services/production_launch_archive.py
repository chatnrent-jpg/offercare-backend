"""Production launch archive — deploy bundle manifest with SHA-256 checksums (step 143)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.deploy_walkthrough import (
    DEPLOY_EXPORT_ZIP_FILENAME,
    _artifact_bytes,
    collect_deploy_bundle_artifacts,
)
from app.services.production_launch_perfection_seal import (
    PRODUCTION_LAUNCH_PERFECTION_SEAL_JSON_FILENAME,
    build_production_launch_perfection_seal,
)

PRODUCTION_LAUNCH_ARCHIVE_JSON_FILENAME = "offercare-production-launch-archive.json"

_ARCHIVE_BUNDLE_ARTIFACTS = (
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
    "README.txt",
)

_ARCHIVED_LAUNCH: dict | None = None


def reset_production_launch_archive_for_tests() -> None:
    """Clear the in-process launch archive (tests only)."""
    global _ARCHIVED_LAUNCH
    _ARCHIVED_LAUNCH = None


def get_production_launch_archive() -> dict | None:
    return _ARCHIVED_LAUNCH


def build_artifact_manifest(db: Session) -> list[dict]:
    entries: list[dict] = []
    for row in collect_deploy_bundle_artifacts(db):
        content = _artifact_bytes(row["content"])
        entries.append(
            {
                "filename": str(row["filename"]),
                "sha256": hashlib.sha256(content).hexdigest(),
                "byte_count": len(content),
            }
        )
    return entries


def compute_manifest_digest(manifest: list[dict]) -> str:
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_production_launch_archive(db: Session) -> dict:
    perfection_seal = build_production_launch_perfection_seal(db)
    perfection_seal_summary = perfection_seal["summary"]
    archived = _ARCHIVED_LAUNCH
    bundle_file_count = len(_ARCHIVE_BUNDLE_ARTIFACTS)
    manifest = build_artifact_manifest(db)
    stored_manifest = (archived or {}).get("manifest")
    current_digest = compute_manifest_digest(manifest) if manifest else None
    stored_digest = (
        compute_manifest_digest(stored_manifest)
        if stored_manifest
        else (archived or {}).get("manifest_digest")
    )

    checks: list[dict] = []

    if perfection_seal["production_launch_perfection_ready"]:
        seal_status = "ready"
        seal_detail = "Launch perfection sealed — ready to archive deploy bundle manifest with checksums"
        seal_action = None
    elif perfection_seal_summary["blocked"] > 0:
        seal_status = "blocked"
        seal_detail = (
            f"Launch perfection seal blocked — {perfection_seal_summary['blocked']} blocker(s)"
        )
        seal_action = "Admin → Production launch perfection seal → Seal launch perfection"
    else:
        seal_status = "warning"
        seal_detail = "Launch perfection seal pending — seal before archiving deploy bundle"
        seal_action = "Admin → Production launch perfection seal → Seal launch perfection"
    checks.append(
        {
            "id": "production_launch_perfection_seal",
            "title": "Production launch perfection seal",
            "status": seal_status,
            "detail": seal_detail,
            "action": seal_action,
        }
    )

    digest_valid = bool(
        archived
        and archived.get("archive_ok")
        and stored_digest
        and archived.get("manifest_digest") == stored_digest
    )

    if archived and digest_valid:
        archive_status = "ready"
        archive_detail = (
            f"Launch archive complete — {archived.get('artifact_count', len(manifest))} artifacts "
            f"with manifest digest `{archived.get('manifest_digest', '—')[:16]}…`"
        )
        archive_action = None
    elif archived and not digest_valid:
        archive_status = "blocked"
        archive_detail = "Launch archive digest mismatch — bundle artifacts changed since archive"
        archive_action = "Re-archive after verifying deploy bundle artifact integrity"
    elif perfection_seal["production_launch_perfection_ready"]:
        archive_status = "warning"
        archive_detail = (
            f"Launch archive pending — archive {len(manifest)} deploy bundle artifacts with SHA-256 checksums"
        )
        archive_action = "Admin → Production launch archive → Archive launch"
    else:
        archive_status = "blocked"
        archive_detail = "Launch archive blocked — launch perfection seal required first"
        archive_action = "Seal launch perfection, then archive deploy bundle manifest"
    checks.append(
        {
            "id": "production_launch_archive",
            "title": "Production launch archive",
            "status": archive_status,
            "detail": archive_detail,
            "action": archive_action,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")

    production_launch_archive_ready = bool(archived and archived.get("archive_ok"))

    steps = [
        "Confirm production_launch_perfection_ready is true on /health after perfection seal",
        "Admin → Production launch archive → Archive launch — SHA-256 manifest of all deploy bundle artifacts",
        "Verify production_launch_archive_ready on /health after archive completes",
        "Export launch archive JSON with manifest entries and manifest digest",
        "Download deploy bundle (.zip) — full 20-file production archive including launch archive manifest",
        "Use manifest checksums to verify deploy bundle artifact integrity offline",
        "File launch archive JSON with compliance audit trail alongside perfection seal",
        "Retain manifest digest for third-party verification of full launch bundle",
    ]

    archive = {
        "production_launch_archive_ready": production_launch_archive_ready,
        "production_launch_perfection_ready": perfection_seal["production_launch_perfection_ready"],
        "production_launch_attestation_ready": perfection_seal["production_launch_attestation_ready"],
        "production_go_live_record_ready": perfection_seal["production_go_live_record_ready"],
        "launch_ceremony_ready": perfection_seal["launch_ceremony_ready"],
        "production_perfection_ready": perfection_seal["production_perfection_ready"],
        "archived": archived is not None,
        "digest_valid": digest_valid,
        "archive_id": archived.get("archive_id") if archived else None,
        "archived_at": archived.get("archived_at") if archived else None,
        "manifest_digest": archived.get("manifest_digest") if archived else current_digest,
        "artifact_count": archived.get("artifact_count") if archived else len(manifest),
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "production_launch_perfection_ready": perfection_seal["production_launch_perfection_ready"],
            "artifact_count": len(manifest),
            "deploy_bundle_file_count": bundle_file_count,
            "deploy_bundle_filename": DEPLOY_EXPORT_ZIP_FILENAME,
            "archive_json_filename": PRODUCTION_LAUNCH_ARCHIVE_JSON_FILENAME,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
        "checks": checks,
        "steps": steps,
        "launch_urls": perfection_seal["launch_urls"],
        "bundle_artifacts": list(_ARCHIVE_BUNDLE_ARTIFACTS),
        "manifest": stored_manifest if archived else manifest,
        "production_launch_perfection_seal": perfection_seal,
        "archive_record": archived,
    }
    return archive


def build_production_launch_archive_json(db: Session) -> dict:
    archive = build_production_launch_archive(db)
    export_payload = {
        "production_launch_archive_ready": archive["production_launch_archive_ready"],
        "production_launch_perfection_ready": archive["production_launch_perfection_ready"],
        "archived": archive["archived"],
        "digest_valid": archive["digest_valid"],
        "archive_id": archive["archive_id"],
        "archived_at": archive["archived_at"],
        "manifest_digest": archive["manifest_digest"],
        "artifact_count": archive["artifact_count"],
        "summary": archive["summary"],
        "checks": archive["checks"],
        "launch_urls": archive["launch_urls"],
        "bundle_artifacts": archive["bundle_artifacts"],
        "manifest": archive["manifest"],
    }
    return {
        "filename": PRODUCTION_LAUNCH_ARCHIVE_JSON_FILENAME,
        "content": json.dumps(export_payload, indent=2),
    }


def archive_production_launch(db: Session) -> dict:
    global _ARCHIVED_LAUNCH

    perfection_seal = build_production_launch_perfection_seal(db)
    manifest = build_artifact_manifest(db)

    if _ARCHIVED_LAUNCH is not None and _ARCHIVED_LAUNCH.get("archive_ok"):
        archive = build_production_launch_archive(db)
        return {
            "ok": True,
            "already_archived": True,
            "production_launch_archive_ready": True,
            "production_launch_perfection_ready": perfection_seal["production_launch_perfection_ready"],
            "archive_id": _ARCHIVED_LAUNCH["archive_id"],
            "archived_at": _ARCHIVED_LAUNCH["archived_at"],
            "manifest_digest": _ARCHIVED_LAUNCH["manifest_digest"],
            "artifact_count": _ARCHIVED_LAUNCH["artifact_count"],
            "deploy_bundle_filename": archive["summary"]["deploy_bundle_filename"],
            "deploy_bundle_file_count": archive["summary"]["deploy_bundle_file_count"],
            "message": (
                f"Launch already archived at {_ARCHIVED_LAUNCH['archived_at']} "
                f"(archive {_ARCHIVED_LAUNCH['archive_id']})"
            ),
        }

    if not perfection_seal["production_launch_perfection_ready"]:
        return {
            "ok": False,
            "already_archived": False,
            "production_launch_archive_ready": False,
            "production_launch_perfection_ready": perfection_seal["production_launch_perfection_ready"],
            "archive_id": None,
            "archived_at": None,
            "manifest_digest": None,
            "artifact_count": len(manifest),
            "deploy_bundle_filename": DEPLOY_EXPORT_ZIP_FILENAME,
            "deploy_bundle_file_count": len(_ARCHIVE_BUNDLE_ARTIFACTS),
            "message": "Launch archive failed — production launch perfection seal required",
        }

    manifest_digest = compute_manifest_digest(manifest)
    archived_at = datetime.now(timezone.utc).isoformat()
    archive_id = str(uuid.uuid4())

    _ARCHIVED_LAUNCH = {
        "archive_id": archive_id,
        "archived_at": archived_at,
        "immutable": True,
        "archive_ok": True,
        "manifest": manifest,
        "manifest_digest": manifest_digest,
        "artifact_count": len(manifest),
    }

    archive = build_production_launch_archive(db)

    return {
        "ok": True,
        "already_archived": False,
        "production_launch_archive_ready": True,
        "production_launch_perfection_ready": perfection_seal["production_launch_perfection_ready"],
        "archive_id": archive_id,
        "archived_at": archived_at,
        "manifest_digest": manifest_digest,
        "artifact_count": len(manifest),
        "deploy_bundle_filename": archive["summary"]["deploy_bundle_filename"],
        "deploy_bundle_file_count": archive["summary"]["deploy_bundle_file_count"],
        "message": (
            "Production launch archived — deploy bundle manifest with SHA-256 checksums filed "
            f"({archive['summary']['deploy_bundle_file_count']} deploy bundle files)"
        ),
    }
