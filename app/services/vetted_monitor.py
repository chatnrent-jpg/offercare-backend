"""VettedCare safety cycle — monitor, sync statuses, audit, and alert."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.compliance_monitor import run_compliance_monitor
from app.services.vetted_alerts import notify_status_change
from app.services.vetted_audit import log_vetted_event
from app.services.vetted_status import VETTED_ACTION_NEEDED, VETTED_BLOCKED, VETTED_EXPIRING


def run_vettedcare_safety_cycle(db: Session, *, actor: str = "vettedcare_monitor") -> dict:
    compliance = run_compliance_monitor(db)
    sync = sync_all_vetted_statuses(db, actor=actor)

    alerts_sent: list[dict] = []
    for change in sync["status_changes"]:
        from uuid import UUID

        from app.models import MarylandProvider

        provider = (
            db.query(MarylandProvider)
            .filter(MarylandProvider.provider_id == UUID(change["provider_id"]))
            .first()
        )
        if provider is None:
            continue

        reason = _reason_for_status(change["new_status"])
        log_vetted_event(
            db,
            event_type="VETTED_STATUS_CHANGED",
            provider_id=provider.provider_id,
            actor=actor,
            previous_status=change["previous_status"],
            new_status=change["new_status"],
            summary=f"{provider.full_name} status {change['previous_status']} → {change['new_status']}",
            metadata={"reason": reason},
        )

        if change["new_status"] in {VETTED_BLOCKED, VETTED_EXPIRING, VETTED_ACTION_NEEDED}:
            alert = notify_status_change(
                db,
                provider,
                previous_status=change["previous_status"],
                new_status=change["new_status"],
                reason=reason,
            )
            if not alert.get("skipped"):
                alerts_sent.append(alert)

    db.commit()
    return {
        "compliance": compliance,
        "vetted_sync": sync,
        "alerts_sent": alerts_sent,
    }


def _reason_for_status(status: str) -> str:
    mapping = {
        "CLEAR": "All required credentials verified and current.",
        "EXPIRING": "One or more credentials expire within the alert window.",
        "ACTION_NEEDED": "Missing documents or license verification pending.",
        "BLOCKED": "Exclusion hit, expired credential, or dispatch suspended for safety.",
    }
    return mapping.get(status, "Credential review required.")
