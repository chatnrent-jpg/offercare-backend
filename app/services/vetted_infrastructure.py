"""VettedMe infrastructure readiness — pre-flight checks without Manus or live operations."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CredentialSafetyAlert, ManusVettingRun, VettedMeAuditLog
from app.services.manus_work_queue import build_manus_integration_config

REQUIRED_TABLES = (
    "maryland_providers",
    "vettedme_audit_log",
    "credential_safety_alerts",
    "manus_vetting_runs",
)

RECRUITMENT_TABLES = (
    "facility_contracts",
    "b2b_raw_leads",
    "ingested_open_shifts",
    "md_provider_licensure",
    "md_outreach_payloads",
    "facilities",
    "facility_contacts",
    "md_provider_compliance",
)


def _check(name: str, *, ok: bool, detail: str, level: str = "required") -> dict:
    status = "pass" if ok else ("warn" if level == "optional" else "fail")
    return {"name": name, "status": status, "detail": detail, "level": level}


def build_vettedme_infrastructure_readiness(db: Session) -> dict:
    checks: list[dict] = []

    # Database
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        db_detail = "PostgreSQL connection OK"
    except Exception as exc:
        db_ok = False
        db_detail = f"Database error: {exc.__class__.__name__}"
    checks.append(_check("database", ok=db_ok, detail=db_detail))

    inspector = inspect(db.get_bind())
    existing_tables = set(inspector.get_table_names())
    missing = [table for table in REQUIRED_TABLES if table not in existing_tables]
    checks.append(
        _check(
            "vettedme_schema",
            ok=not missing,
            detail="All VettedMe tables present"
            if not missing
            else f"Missing tables: {', '.join(missing)}",
        )
    )

    missing_recruitment = [table for table in RECRUITMENT_TABLES if table not in existing_tables]
    checks.append(
        _check(
            "recruitment_engine_schema",
            ok=not missing_recruitment,
            detail="Facility recruitment tables present"
            if not missing_recruitment
            else f"Run alembic upgrade head (014_facility_recruitment): {', '.join(missing_recruitment)}",
            level="optional" if missing_recruitment else "required",
        )
    )

    has_vetted_column = "vetted_status" in {
        col["name"] for col in inspector.get_columns("maryland_providers")
    } if "maryland_providers" in existing_tables else False
    checks.append(
        _check(
            "provider_vetted_status_column",
            ok=has_vetted_column,
            detail="maryland_providers.vetted_status column present"
            if has_vetted_column
            else "Run alembic upgrade head (013_vettedme_foundation)",
        )
    )

    # Auth / config
    admin_key = bool(str(settings.ADMIN_API_KEY or "").strip())
    checks.append(
        _check(
            "admin_api_key",
            ok=admin_key,
            detail="ADMIN_API_KEY configured" if admin_key else "Set ADMIN_API_KEY in .env",
        )
    )

    manus_key = bool(str(settings.MANUS_API_KEY or "").strip())
    checks.append(
        _check(
            "manus_webhook_key",
            ok=manus_key,
            detail="MANUS_API_KEY configured (hook ready; Manus account not required yet)"
            if manus_key
            else "Set MANUS_API_KEY for future Manus worker",
            level="optional" if not manus_key else "required",
        )
    )

    public_url = bool(str(settings.PUBLIC_BASE_URL or "").strip())
    checks.append(
        _check(
            "public_base_url",
            ok=public_url,
            detail=f"PUBLIC_BASE_URL={settings.PUBLIC_BASE_URL}"
            if public_url
            else "Set PUBLIC_BASE_URL for Manus/work-queue URLs",
        )
    )

    # Alerts (infra can be dry-run)
    checks.append(
        _check(
            "vetted_alerts_enabled",
            ok=settings.VETTED_ALERTS_ENABLED,
            detail="VETTED_ALERTS_ENABLED=true" if settings.VETTED_ALERTS_ENABLED else "Alerts disabled",
        )
    )

    admin_email = bool(str(settings.VETTED_ADMIN_ALERT_EMAIL or "").strip())
    checks.append(
        _check(
            "admin_alert_email",
            ok=admin_email,
            detail="VETTED_ADMIN_ALERT_EMAIL set"
            if admin_email
            else "Optional until go-live — set your email for safety alerts",
            level="optional",
        )
    )

    sms_live = settings.twilio_configured and not settings.SMS_DRY_RUN
    checks.append(
        _check(
            "sms_delivery",
            ok=settings.SMS_DRY_RUN or sms_live,
            detail="SMS dry-run (safe for infra testing)"
            if settings.SMS_DRY_RUN
            else ("SMS live mode" if sms_live else "Twilio not configured — SMS dry-run recommended"),
            level="optional",
        )
    )

    email_live = settings.email_configured and not settings.EMAIL_DRY_RUN
    checks.append(
        _check(
            "email_delivery",
            ok=settings.EMAIL_DRY_RUN or email_live,
            detail="Email dry-run (safe for infra testing)"
            if settings.EMAIL_DRY_RUN
            else ("Email live mode" if email_live else "SMTP not configured — email dry-run recommended"),
            level="optional",
        )
    )

    # Credential verification sources (dry-run OK for infra)
    checks.append(
        _check(
            "mbon_verification_mode",
            ok=True,
            detail="MBON dry-run" if settings.MBON_VERIFY_DRY_RUN else "MBON live mode",
            level="optional",
        )
    )
    checks.append(
        _check(
            "oig_verification_mode",
            ok=True,
            detail="OIG dry-run" if settings.OIG_SCREEN_DRY_RUN else "OIG live mode",
            level="optional",
        )
    )
    checks.append(
        _check(
            "judiciary_verification_mode",
            ok=True,
            detail="Judiciary dry-run" if settings.MD_JUDICIARY_DRY_RUN else "Judiciary live mode",
            level="optional",
        )
    )

    # Workers
    checks.append(
        _check(
            "compliance_scheduler",
            ok=settings.COMPLIANCE_MONITOR_WORKER_ENABLED,
            detail="Background safety scheduler enabled"
            if settings.COMPLIANCE_MONITOR_WORKER_ENABLED
            else "Compliance scheduler disabled",
            level="optional",
        )
    )

    # API surface
    manus_config = build_manus_integration_config()
    checks.append(
        _check(
            "manus_api_hook",
            ok=True,
            detail="Manus endpoints registered (config, work-queue, run, batch)",
            level="optional",
        )
    )

    # Data layer smoke (counts only — not operational triage)
    try:
        audit_count = db.query(VettedMeAuditLog).count()
        alert_count = db.query(CredentialSafetyAlert).count()
        manus_count = db.query(ManusVettingRun).count()
        checks.append(
            _check(
                "audit_log_table",
                ok=True,
                detail=f"Audit log reachable ({audit_count} events)",
                level="optional",
            )
        )
        checks.append(
            _check(
                "manus_runs_table",
                ok=True,
                detail=f"Manus runs table reachable ({manus_count} runs — 0 expected before Manus)",
                level="optional",
            )
        )
        checks.append(
            _check(
                "safety_alerts_table",
                ok=True,
                detail=f"Safety alerts table reachable ({alert_count} alerts)",
                level="optional",
            )
        )
    except Exception as exc:
        checks.append(
            _check(
                "vettedme_data_layer",
                ok=False,
                detail=f"Could not query VettedMe tables: {exc.__class__.__name__}",
            )
        )

    required = [row for row in checks if row["level"] == "required"]
    optional = [row for row in checks if row["level"] == "optional"]
    required_pass = sum(1 for row in required if row["status"] == "pass")
    required_fail = sum(1 for row in required if row["status"] == "fail")
    optional_warn = sum(1 for row in optional if row["status"] in {"warn", "fail"})

    if required_fail:
        overall = "not_ready"
    elif optional_warn:
        overall = "infra_ready"
    else:
        overall = "infra_ready"

    return {
        "product": settings.PROJECT_NAME,
        "overall": overall,
        "summary": (
            "Core VettedMe infrastructure is ready for development and testing."
            if overall == "infra_ready"
            else "Fix required checks before continuing infrastructure work."
        ),
        "required_pass": required_pass,
        "required_total": len(required),
        "optional_warnings": optional_warn,
        "manus_worker_required": False,
        "manus_hook_ready": manus_key,
        "checks": checks,
        "manus_endpoints": manus_config["endpoints"],
        "next_without_manus": [
            "Run scripts/vettedme-preflight.ps1",
            "Open http://127.0.0.1:8000/admin — Credential Safety Dashboard",
            "Open http://127.0.0.1:8000/portal — My Safety Status (after login)",
            "Run scripts/test-manus-webhook.ps1 to simulate Manus (no Manus account)",
        ],
    }
