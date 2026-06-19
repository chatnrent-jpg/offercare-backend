"""Production launch attestation — SHA-256 digest of sealed go-live record (step 141)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.deploy_walkthrough import DEPLOY_EXPORT_ZIP_FILENAME
from app.services.production_go_live_record import (
    PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME,
    build_production_go_live_record,
    get_sealed_launch_record,
)

PRODUCTION_LAUNCH_ATTESTATION_JSON_FILENAME = "offercare-production-launch-attestation.json"
PRODUCTION_LAUNCH_ATTESTATION_MD_FILENAME = "offercare-production-launch-attestation.md"

_ATTESTATION_BUNDLE_ARTIFACTS = (
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
    PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME,
    PRODUCTION_LAUNCH_ATTESTATION_MD_FILENAME,
    PRODUCTION_LAUNCH_ATTESTATION_JSON_FILENAME,
    "README.txt",
)

_ATTESTED_LAUNCH: dict | None = None


def reset_launch_attestation_for_tests() -> None:
    """Clear the in-process attestation (tests only)."""
    global _ATTESTED_LAUNCH
    _ATTESTED_LAUNCH = None


def get_launch_attestation() -> dict | None:
    return _ATTESTED_LAUNCH


def _status_label(ready: bool) -> str:
    return "READY" if ready else "NOT YET"


def build_go_live_attestation_subject(db: Session) -> dict | None:
    sealed = get_sealed_launch_record()
    if not sealed or not sealed.get("seal_ok"):
        return None
    return {
        "record_id": sealed["record_id"],
        "sealed_at": sealed["sealed_at"],
        "immutable": sealed["immutable"],
        "facility_name": sealed.get("facility_name"),
        "placement_id": sealed.get("placement_id"),
        "health_snapshot": sealed["health_snapshot"],
        "ceremony_run": sealed["ceremony_run"],
        "go_live_record_filename": PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME,
    }


def compute_go_live_record_digest(subject: dict) -> str:
    canonical = json.dumps(subject, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_attestation_markdown(attestation: dict) -> str:
    summary = attestation["summary"]
    digest = attestation.get("digest_sha256") or "—"
    lines = [
        "# OfferCare Maryland Production Launch Attestation",
        "",
        f"Generated: {summary.get('refreshed_at', datetime.now(timezone.utc).isoformat())}",
        "",
        "## Executive summary",
        "",
        f"- **Launch attestation:** {_status_label(attestation['production_launch_attestation_ready'])}",
        f"- **Go-live record:** {_status_label(attestation['production_go_live_record_ready'])}",
        f"- **Launch ceremony:** {_status_label(attestation['launch_ceremony_ready'])}",
        f"- **Record ID:** {attestation.get('record_id') or '—'}",
        f"- **Attestation ID:** {attestation.get('attestation_id') or '—'}",
        f"- **SHA-256 digest:** `{digest}`",
        f"- **Deploy bundle:** {DEPLOY_EXPORT_ZIP_FILENAME} ({summary.get('deploy_bundle_file_count', 18)} files)",
        "",
        "## Attestation checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for row in attestation["checks"]:
        lines.append(f"| {row['title']} | {row['status'].upper()} | {row['detail']} |")
    lines.extend(
        [
            "",
            "## Cryptographic attestation",
            "",
            "This document attests that the sealed production go-live record was archived",
            "at launch and its canonical JSON subject hashes to the SHA-256 digest below.",
            "",
            f"- **Algorithm:** SHA-256",
            f"- **Subject:** sealed go-live record (`{PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME}`)",
            f"- **Digest:** `{digest}`",
            f"- **Attested at:** {attestation.get('attested_at') or '—'}",
            "",
            "## Compliance sign-off",
            "",
            "- [ ] Compliance officer — go-live record digest verified",
            "- [ ] Security lead — SHA-256 attestation matches archived JSON",
            "- [ ] Operations lead — health snapshot at seal time reviewed",
            "- [ ] Executive sponsor — launch attestation filed for audit trail",
            "",
            "## Attestation steps completed",
            "",
        ]
    )
    for index, step in enumerate(attestation.get("steps") or [], start=1):
        lines.append(f"{index}. {step}")
    lines.append("")
    return "\n".join(lines)


def build_production_launch_attestation(db: Session) -> dict:
    go_live = build_production_go_live_record(db)
    go_live_summary = go_live["summary"]
    attested = _ATTESTED_LAUNCH
    bundle_file_count = len(_ATTESTATION_BUNDLE_ARTIFACTS)
    subject = build_go_live_attestation_subject(db)
    current_digest = compute_go_live_record_digest(subject) if subject else None

    checks: list[dict] = []

    if go_live["production_go_live_record_ready"]:
        go_live_status = "ready"
        go_live_detail = (
            f"Go-live record sealed — record {go_live.get('record_id') or '—'} ready for attestation"
        )
        go_live_action = None
    elif go_live_summary["blocked"] > 0:
        go_live_status = "blocked"
        go_live_detail = (
            f"Go-live record blocked — {go_live_summary['blocked']} blocker(s)"
        )
        go_live_action = "Admin → Production go-live record → Seal launch record"
    else:
        go_live_status = "warning"
        go_live_detail = "Go-live record not sealed — seal before cryptographic attestation"
        go_live_action = "Admin → Production go-live record → Seal launch record"
    checks.append(
        {
            "id": "production_go_live_record",
            "title": "Production go-live record",
            "status": go_live_status,
            "detail": go_live_detail,
            "action": go_live_action,
        }
    )

    digest_valid = bool(
        attested
        and current_digest
        and attested.get("digest_sha256") == current_digest
        and attested.get("record_id") == go_live.get("record_id")
    )

    if attested and digest_valid:
        attestation_status = "ready"
        attestation_detail = (
            f"Launch attestation complete — SHA-256 `{attested['digest_sha256'][:16]}…` "
            f"at {attested.get('attested_at', '—')}"
        )
        attestation_action = None
    elif attested and not digest_valid:
        attestation_status = "blocked"
        attestation_detail = "Launch attestation digest mismatch — sealed record changed since attestation"
        attestation_action = "Re-attest after verifying sealed go-live record integrity"
    elif go_live["production_go_live_record_ready"]:
        attestation_status = "warning"
        attestation_detail = "Launch attestation pending — attest sealed go-live record for compliance sign-off"
        attestation_action = "Admin → Production launch attestation → Attest launch"
    else:
        attestation_status = "blocked"
        attestation_detail = "Launch attestation blocked — sealed go-live record required first"
        attestation_action = "Seal go-live record, then attest launch"
    checks.append(
        {
            "id": "production_launch_attestation",
            "title": "Production launch attestation",
            "status": attestation_status,
            "detail": attestation_detail,
            "action": attestation_action,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")

    production_launch_attestation_ready = bool(attested and digest_valid)

    steps = [
        "Confirm production_go_live_record_ready is true on /health after seal completes",
        "Admin → Production launch attestation → Attest launch — SHA-256 digest of sealed go-live record",
        "Download launch attestation markdown for compliance officer sign-off",
        "Export launch attestation JSON with digest, record ID, and attestation ID",
        "Verify production_launch_attestation_ready on /health after attestation",
        "Export deploy bundle (.zip) — full 18-file archive including attestation artifacts",
        "File attestation markdown with compliance audit trail alongside sealed go-live record",
        "Retain SHA-256 digest for third-party verification of launch archive integrity",
    ]

    attestation = {
        "production_launch_attestation_ready": production_launch_attestation_ready,
        "production_go_live_record_ready": go_live["production_go_live_record_ready"],
        "launch_ceremony_ready": go_live["launch_ceremony_ready"],
        "production_perfection_ready": go_live["production_perfection_ready"],
        "production_ops_ready": go_live["production_ops_ready"],
        "maryland_launch_ready": go_live["maryland_launch_ready"],
        "attested": attested is not None,
        "digest_valid": digest_valid,
        "attestation_id": attested.get("attestation_id") if attested else None,
        "attested_at": attested.get("attested_at") if attested else None,
        "record_id": go_live.get("record_id"),
        "digest_sha256": attested.get("digest_sha256") if attested else current_digest,
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "production_go_live_record_ready": go_live["production_go_live_record_ready"],
            "launch_ceremony_ready": go_live["launch_ceremony_ready"],
            "production_perfection_ready": go_live["production_perfection_ready"],
            "live_scrapers_all_live": go_live_summary.get("live_scrapers_all_live"),
            "deploy_bundle_file_count": bundle_file_count,
            "deploy_bundle_filename": DEPLOY_EXPORT_ZIP_FILENAME,
            "go_live_record_filename": PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME,
            "attestation_json_filename": PRODUCTION_LAUNCH_ATTESTATION_JSON_FILENAME,
            "attestation_md_filename": PRODUCTION_LAUNCH_ATTESTATION_MD_FILENAME,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
        "checks": checks,
        "steps": steps,
        "launch_urls": go_live["launch_urls"],
        "bundle_artifacts": list(_ATTESTATION_BUNDLE_ARTIFACTS),
        "production_go_live_record": go_live,
        "attestation_subject": subject,
        "attestation_record": attested,
    }
    attestation["attestation_markdown"] = _build_attestation_markdown(attestation)
    return attestation


def build_production_launch_attestation_markdown(db: Session) -> dict:
    attestation = build_production_launch_attestation(db)
    return {
        "filename": PRODUCTION_LAUNCH_ATTESTATION_MD_FILENAME,
        "markdown": attestation["attestation_markdown"],
    }


def build_production_launch_attestation_json(db: Session) -> dict:
    attestation = build_production_launch_attestation(db)
    export_payload = {
        "production_launch_attestation_ready": attestation["production_launch_attestation_ready"],
        "production_go_live_record_ready": attestation["production_go_live_record_ready"],
        "launch_ceremony_ready": attestation["launch_ceremony_ready"],
        "attested": attestation["attested"],
        "digest_valid": attestation["digest_valid"],
        "attestation_id": attestation["attestation_id"],
        "attested_at": attestation["attested_at"],
        "record_id": attestation["record_id"],
        "digest_sha256": attestation["digest_sha256"],
        "summary": attestation["summary"],
        "checks": attestation["checks"],
        "launch_urls": attestation["launch_urls"],
        "bundle_artifacts": attestation["bundle_artifacts"],
        "attestation_subject": attestation["attestation_subject"],
        "attestation_markdown": attestation["attestation_markdown"],
    }
    return {
        "filename": PRODUCTION_LAUNCH_ATTESTATION_JSON_FILENAME,
        "content": json.dumps(export_payload, indent=2),
    }


def attest_production_launch(db: Session) -> dict:
    global _ATTESTED_LAUNCH

    go_live = build_production_go_live_record(db)
    subject = build_go_live_attestation_subject(db)

    if _ATTESTED_LAUNCH is not None:
        attestation = build_production_launch_attestation(db)
        if attestation["production_launch_attestation_ready"]:
            return {
                "ok": True,
                "already_attested": True,
                "production_launch_attestation_ready": True,
                "production_go_live_record_ready": go_live["production_go_live_record_ready"],
                "record_id": _ATTESTED_LAUNCH["record_id"],
                "attestation_id": _ATTESTED_LAUNCH["attestation_id"],
                "attested_at": _ATTESTED_LAUNCH["attested_at"],
                "digest_sha256": _ATTESTED_LAUNCH["digest_sha256"],
                "deploy_bundle_filename": attestation["summary"]["deploy_bundle_filename"],
                "deploy_bundle_file_count": attestation["summary"]["deploy_bundle_file_count"],
                "message": (
                    f"Launch already attested at {_ATTESTED_LAUNCH['attested_at']} "
                    f"(attestation {_ATTESTED_LAUNCH['attestation_id']})"
                ),
            }

    if not subject:
        return {
            "ok": False,
            "already_attested": False,
            "production_launch_attestation_ready": False,
            "production_go_live_record_ready": go_live["production_go_live_record_ready"],
            "record_id": go_live.get("record_id"),
            "attestation_id": None,
            "attested_at": None,
            "digest_sha256": None,
            "deploy_bundle_filename": DEPLOY_EXPORT_ZIP_FILENAME,
            "deploy_bundle_file_count": len(_ATTESTATION_BUNDLE_ARTIFACTS),
            "message": "Launch attestation failed — sealed go-live record required",
        }

    digest_sha256 = compute_go_live_record_digest(subject)
    attested_at = datetime.now(timezone.utc).isoformat()
    attestation_id = str(uuid.uuid4())

    _ATTESTED_LAUNCH = {
        "attestation_id": attestation_id,
        "attested_at": attested_at,
        "record_id": subject["record_id"],
        "digest_sha256": digest_sha256,
        "attestation_subject": subject,
        "immutable": True,
    }

    attestation = build_production_launch_attestation(db)

    return {
        "ok": True,
        "already_attested": False,
        "production_launch_attestation_ready": True,
        "production_go_live_record_ready": go_live["production_go_live_record_ready"],
        "record_id": subject["record_id"],
        "attestation_id": attestation_id,
        "attested_at": attested_at,
        "digest_sha256": digest_sha256,
        "deploy_bundle_filename": attestation["summary"]["deploy_bundle_filename"],
        "deploy_bundle_file_count": attestation["summary"]["deploy_bundle_file_count"],
        "message": (
            "Production launch attested — SHA-256 digest of sealed go-live record archived "
            f"({attestation['summary']['deploy_bundle_file_count']} deploy bundle files)"
        ),
    }
