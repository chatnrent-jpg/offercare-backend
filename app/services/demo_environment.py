"""Inspect the Mid-Atlantic demo environment after seeding."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    ClinicalPlacementLedger,
    ClinicianPortalAccount,
    ClinicianPushSubscription,
    MarylandFacility,
    MarylandProvider,
    OfferCareJobOffer,
    VmsSubmissionLog,
)
from app.seed import DEMO_FACILITY_NAMES, DEMO_SEED_CLINICIAN_EMAILS, seed_all_mid_atlantic_demos
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD
from app.services.demo_push_subscriptions import ensure_demo_push_subscriptions
from app.services.matched_shift_alerts import notify_matched_clinicians_for_offer, notify_matched_clinicians_for_offers
from app.services.push_subscriptions import list_push_subscriptions_for_provider
from app.services.shift_lock import lock_shift_for_provider
from app.services.shift_matching import shift_matches_provider
from app.services.shift_offer_generator import get_open_shift_by_id
from app.services.states import normalize_state

SAMPLE_DEMO_CLINICIAN_EMAIL = "nj.snf.cna.a@offercare.demo"
DEMO_STATUS_JSON_FILENAME = "offercare-demo-status.json"
DEMO_STATUS_CSV_FILENAME = "offercare-demo-status.csv"
DEMO_GATES_JSON_FILENAME = "offercare-demo-gates.json"
DEMO_GATES_TXT_FILENAME = "offercare-demo-gates.txt"
DEMO_EXPORT_ZIP_FILENAME = "offercare-demo-bundle.zip"
DEMO_EXPORT_README_FILENAME = "README.txt"

DEMO_NEXT_STEPS = [
    "Admin → Run full demo setup auto-resets locked shifts, then seeds portal logins, push subs, and matched alerts",
    "Review this panel to confirm each shift is BROADCASTING with matched clinicians",
    "Check the demo health badge — green means ready, yellow needs attention, red means run full demo setup",
    "Demo health badge shows present vs broadcasting facility counts alongside status and issues",
    "Demo health badge shows demo admin action count alongside confirmation gate count",
    "Deploy checklist auto-checks demo environment health alongside Docker, Twilio, and portal items",
    "Export demo status as JSON or CSV for QA checklists and walkthrough sign-off",
    "Download demo bundle (.zip) for walkthrough markdown, gates JSON, and status exports in one file",
    "Copy or download demo walkthrough script (.md) for a presenter-ready guide with deep links per shift",
    "Open portal deep links — login form pre-fills the matched @offercare.demo clinician",
    "Portal warns if you sign in as the wrong demo clinician for a deep-linked shift",
    "Demo clinicians sign in at /portal with their @offercare.demo email and SecretPass1",
    "Or run individual ensure/notify buttons below for partial demo refreshes",
    "Smoke test demo lock to verify portal lock flow and placement ledger without opening /portal",
    "Or use Lock test on a specific demo shift row to verify lock + placement for that facility",
    "Or use Notify on a specific demo shift row to test matched push alerts for one facility",
    "Or use Reset on a locked demo shift row to unlock that facility without resetting all 10 demos",
    "Locked demo rows stay visible with LOCKED status and Reset even when loaded is false after a lock test",
    "Demo health counts locked rows as present — only truly missing shifts lower the facility count",
    "Per-row Reset returns a broadcasting offer_row snapshot for Lock test and Notify after unlock",
    "Reset demo environment to unlock shifts and clear placements before the next walkthrough",
    "Demo-ready gate warns before copying or downloading walkthrough, portal links, or bundle when health is not green",
    "Demo-ready gate also warns before Run full demo setup when health is not green",
    "Demo-ready reset gate warns before Reset demo environment when health is green",
    "Demo health badge summarizes which admin actions require confirmation gates",
    "Per-row Reset asks for confirmation when unlocking a locked shift during an intact walkthrough",
    "Lock test asks for confirmation when locking a broadcasting shift during an intact walkthrough",
    "Notify matched asks for confirmation when sending push alerts during an intact walkthrough",
    "Ensure demo portal logins asks for confirmation when resetting passwords during an intact walkthrough",
    "Ensure demo push subscriptions asks for confirmation when registering push subs during an intact walkthrough",
    "Copy demo portal links asks for confirmation when demo health is not green",
    "GET /api/seed/demo-gates returns active confirmation gates and the full gate matrix",
    "Export demo gates as JSON from the Demo environment panel for QA sign-off without the full bundle",
    "Demo walkthrough markdown includes the full confirmation gate matrix with active/inactive status per gate",
    "Copy active gates from the Demo environment panel for a presenter-ready gate matrix snapshot with the demo admin actions catalog",
    "Download demo gates (.txt) or find offercare-demo-gates.txt inside demo and deploy bundles",
    "Deploy checklist embeds demo_gates — export JSON/CSV or review the gate matrix in the deploy walkthrough panel",
    "Demo environment panel renders the embedded demo_gates gate matrix after refresh",
    "Demo environment panel renders the embedded demo admin actions catalog alongside the gate matrix",
    "Demo environment panel gate matrix header shows demo admin action count alongside gate count",
    "Export demo status JSON embeds the full demo_gates snapshot for structured gate sign-off",
    "Demo status CSV includes demo gate summary and gate matrix sections",
    "Demo and deploy bundles include demo status JSON/CSV with embedded demo_gates for offline gate sign-off",
    "Deploy bundle checklist JSON/CSV includes the embedded demo_gates snapshot for offline deploy sign-off",
    "Run full demo setup returns status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "Reset demo environment returns status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "Per-row Reset returns status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "Lock test returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "Notify matched returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "Ensure demo portal logins returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "Ensure demo push subscriptions returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
    "All demo admin actions return embedded demo_gates with demo_admin_action_count and the demo_admin_actions catalog — the gate matrix refreshes immediately after setup, reset, lock test, notify, and ensure actions",
    "Demo status CSV includes the demo admin actions catalog with embedded demo_gates endpoints",
    "Demo status JSON includes the demo admin actions catalog with embedded demo_gates endpoints",
    "Demo status JSON includes top-level demo_admin_action_count alongside demo_admin_actions",
    "Deploy checklist JSON includes the demo admin actions catalog with embedded demo_gates endpoints",
    "Export demo gates JSON includes the demo admin actions catalog with embedded demo_gates endpoints",
    "Demo gates JSON includes demo admin action count alongside gate count",
    "Download demo gates (.txt) includes the demo admin actions catalog with embedded demo_gates endpoints",
    "Export gates (.json) and Download gates (.txt) toasts show demo admin action count",
]

DEMO_GATE_DEFINITIONS = [
    {"id": "export_walkthrough", "action": "Export / copy walkthrough", "confirm_when": "health_not_green"},
    {"id": "copy_demo_links", "action": "Copy demo portal links", "confirm_when": "health_not_green"},
    {"id": "run_full_setup", "action": "Run full demo setup", "confirm_when": "health_not_green"},
    {"id": "reset_environment", "action": "Reset demo environment", "confirm_when": "health_green"},
    {"id": "reset_offer", "action": "Per-row Reset", "confirm_when": "walkthrough_intact"},
    {"id": "lock_test", "action": "Lock test", "confirm_when": "walkthrough_intact"},
    {"id": "notify_matched", "action": "Notify matched", "confirm_when": "walkthrough_intact"},
    {"id": "ensure_portal", "action": "Ensure demo portal logins", "confirm_when": "walkthrough_intact"},
    {"id": "ensure_push", "action": "Ensure demo push subscriptions", "confirm_when": "walkthrough_intact"},
]

DEMO_ADMIN_ACTION_DEMO_GATES = [
    {"action": "Run full demo setup", "endpoint": "POST /api/seed/demo-setup", "field": "status.demo_gates"},
    {"action": "Reset demo environment", "endpoint": "POST /api/seed/demo-reset", "field": "status.demo_gates"},
    {"action": "Per-row Reset", "endpoint": "POST /api/seed/demo-reset-offer", "field": "status.demo_gates"},
    {"action": "Lock test", "endpoint": "POST /api/seed/demo-lock-smoke", "field": "demo_status.demo_gates"},
    {"action": "Notify matched (bulk)", "endpoint": "POST /api/seed/notify-matched-demos", "field": "demo_status.demo_gates"},
    {"action": "Notify matched (per row)", "endpoint": "POST /api/seed/demo-notify-matched", "field": "demo_status.demo_gates"},
    {"action": "Ensure demo portal logins", "endpoint": "POST /api/seed/demo-portal-accounts", "field": "demo_status.demo_gates"},
    {"action": "Ensure demo push subscriptions", "endpoint": "POST /api/seed/demo-push-subscriptions", "field": "demo_status.demo_gates"},
]


def append_demo_admin_actions_csv(writer: csv.writer) -> None:
    writer.writerow([])
    writer.writerow(["DEMO ADMIN ACTIONS"])
    writer.writerow(["action", "endpoint", "demo_gates_field"])
    for row in DEMO_ADMIN_ACTION_DEMO_GATES:
        writer.writerow([row["action"], row["endpoint"], row["field"]])


def demo_portal_deep_link(offer_id: str | UUID | None) -> str | None:
    if not offer_id:
        return None
    return f"/portal/?offer={offer_id}"


def find_demo_clinician_for_shift(db: Session, row: dict) -> MarylandProvider | None:
    providers = (
        db.query(MarylandProvider)
        .filter(
            MarylandProvider.email.in_(DEMO_SEED_CLINICIAN_EMAILS),
            MarylandProvider.license_status == "VERIFIED",
            MarylandProvider.state == normalize_state(str(row["state"])),
        )
        .order_by(MarylandProvider.email.asc())
        .all()
    )
    for provider in providers:
        if shift_matches_provider(
            provider=provider,
            facility_state=str(row["state"]),
            facility_type=str(row["facility_type"]),
            shift_role=str(row["shift_role"]),
            hourly_pay_rate=float(row["hourly_pay_rate"]),
        ):
            return provider
    return None


def _demo_clinician_fields(provider: MarylandProvider | None) -> dict[str, str | None]:
    if provider is None:
        return {"demo_clinician_email": None, "demo_clinician_name": None}
    return {
        "demo_clinician_email": provider.email,
        "demo_clinician_name": provider.full_name,
    }


def _demo_offer_resettable(offer_id: str | None, compliance_lock_status: str | None) -> bool:
    status = str(compliance_lock_status or "")
    return bool(offer_id and status and status != "BROADCASTING")


def _demo_facility_present(row: dict) -> bool:
    return bool(row.get("loaded") or row.get("resettable"))


def _build_locked_demo_offer_row(
    db: Session,
    *,
    facility_name: str,
    facility: MarylandFacility,
    offer: OfferCareJobOffer,
) -> dict:
    row = get_open_shift_by_id(db, offer.offer_id)
    lock_status = str(offer.compliance_lock_status)
    if row is None:
        return {
            "facility_name": facility_name,
            "state": facility.state,
            "facility_type": facility.facility_type,
            "shift_role": offer.shift_role,
            "offer_id": str(offer.offer_id),
            "loaded": False,
            "resettable": _demo_offer_resettable(str(offer.offer_id), lock_status),
            "compliance_lock_status": lock_status,
            "matched_clinician_count": 0,
            "push_ready_count": 0,
            "portal_deep_link": demo_portal_deep_link(str(offer.offer_id)),
            **_demo_clinician_fields(None),
        }
    matched_count, push_ready_count = _count_matched_clinicians(db, row)
    demo_clinician = find_demo_clinician_for_shift(db, row)
    return {
        "facility_name": facility_name,
        "state": str(row["state"]),
        "facility_type": str(row["facility_type"]),
        "shift_role": str(row["shift_role"]),
        "offer_id": str(row["offer_id"]),
        "loaded": False,
        "resettable": _demo_offer_resettable(str(row["offer_id"]), lock_status),
        "compliance_lock_status": lock_status,
        "matched_clinician_count": matched_count,
        "push_ready_count": push_ready_count,
        "portal_deep_link": demo_portal_deep_link(str(row["offer_id"])),
        **_demo_clinician_fields(demo_clinician),
    }


def _build_broadcasting_demo_offer_row(
    db: Session,
    *,
    facility_name: str,
    facility: MarylandFacility,
    offer: OfferCareJobOffer,
) -> dict:
    row = get_open_shift_by_id(db, offer.offer_id)
    lock_status = str(offer.compliance_lock_status)
    if row is None:
        return {
            "facility_name": facility_name,
            "state": facility.state,
            "facility_type": facility.facility_type,
            "shift_role": offer.shift_role,
            "offer_id": str(offer.offer_id),
            "loaded": False,
            "resettable": _demo_offer_resettable(str(offer.offer_id), lock_status),
            "compliance_lock_status": lock_status,
            "matched_clinician_count": 0,
            "push_ready_count": 0,
            "portal_deep_link": demo_portal_deep_link(str(offer.offer_id)),
            **_demo_clinician_fields(None),
        }
    matched_count, push_ready_count = _count_matched_clinicians(db, row)
    demo_clinician = find_demo_clinician_for_shift(db, row)
    return {
        "facility_name": facility_name,
        "state": str(row["state"]),
        "facility_type": str(row["facility_type"]),
        "shift_role": str(row["shift_role"]),
        "offer_id": str(row["offer_id"]),
        "loaded": True,
        "resettable": False,
        "compliance_lock_status": lock_status,
        "matched_clinician_count": matched_count,
        "push_ready_count": push_ready_count,
        "portal_deep_link": demo_portal_deep_link(str(row["offer_id"])),
        **_demo_clinician_fields(demo_clinician),
    }


def _count_matched_clinicians(db: Session, row: dict) -> tuple[int, int]:
    facility_state = normalize_state(str(row["state"]))
    providers = (
        db.query(MarylandProvider)
        .filter(
            MarylandProvider.state == facility_state,
            MarylandProvider.license_status == "VERIFIED",
        )
        .all()
    )
    matched = 0
    push_ready = 0
    for provider in providers:
        if not shift_matches_provider(
            provider=provider,
            facility_state=str(row["state"]),
            facility_type=str(row["facility_type"]),
            shift_role=str(row["shift_role"]),
            hourly_pay_rate=float(row["hourly_pay_rate"]),
        ):
            continue
        matched += 1
        if list_push_subscriptions_for_provider(db, provider.provider_id):
            push_ready += 1
    return matched, push_ready


def demo_walkthrough_intact(health: dict) -> bool:
    if health.get("status") == "green":
        return True
    present = health.get("present_facility_count")
    expected = health.get("expected_facility_count")
    if present is None or expected is None or present != expected:
        return False
    issues = list(health.get("issues") or [])
    return bool(issues) and all("locked" in issue.lower() for issue in issues)


def build_demo_gate_hints(health: dict) -> list[str]:
    status = str(health.get("status") or "")
    intact = demo_walkthrough_intact(health)
    if status == "green":
        hints = [
            "Exports and walkthrough copy proceed without confirmation",
            "Reset demo environment asks for confirmation before clearing a ready walkthrough",
        ]
    else:
        hints = [
            "Export walkthrough or bundle asks for confirmation until health is green",
            "Copy demo portal links asks for confirmation until health is green",
            "Run full demo setup asks for confirmation until health is green",
            "Reset demo environment proceeds without confirmation while health needs attention",
        ]
    if intact:
        hints.append(
            "Per-row Reset on a locked shift asks for confirmation during an intact walkthrough"
        )
        hints.append(
            "Lock test on a broadcasting shift asks for confirmation during an intact walkthrough"
        )
        hints.append(
            "Notify matched asks for confirmation during an intact walkthrough"
        )
        hints.append(
            "Ensure demo portal logins asks for confirmation during an intact walkthrough"
        )
        hints.append(
            "Ensure demo push subscriptions asks for confirmation during an intact walkthrough"
        )
    hints.append(
        f"Demo admin actions ({len(DEMO_ADMIN_ACTION_DEMO_GATES)} cataloged) return embedded demo_gates on each response"
    )
    return hints


def build_demo_active_gates(health: dict) -> list[str]:
    intact = demo_walkthrough_intact(health)
    status = str(health.get("status") or "")
    active: list[str] = []
    if status != "green":
        active.extend(["export_walkthrough", "copy_demo_links", "run_full_setup"])
    else:
        active.append("reset_environment")
    if intact:
        active.extend(["reset_offer", "lock_test", "notify_matched", "ensure_portal", "ensure_push"])
    return active


def build_demo_gates_clipboard_text(summary: dict) -> str:
    active = summary.get("active_gates") or []
    lines = [
        "OfferCare Demo Confirmation Gates",
        f"Health: {summary.get('health_label') or '—'} ({summary.get('health_status') or 'pending'})",
        f"Walkthrough intact: {'yes' if summary.get('walkthrough_intact') else 'no'}",
        (
            f"Active gates: {', '.join(active)}"
            if active
            else "Active gates: none"
        ),
        f"Total gates: {summary.get('gate_count', len(DEMO_GATE_DEFINITIONS))}",
        (
            f"Demo admin actions: {summary.get('demo_admin_action_count', len(DEMO_ADMIN_ACTION_DEMO_GATES))}"
        ),
        "",
        "Gate matrix:",
    ]
    for row in summary.get("gates") or []:
        state = "active now" if row.get("active") else "inactive"
        confirm_when = str(row.get("confirm_when") or "").replace("_", " ")
        lines.append(
            f"- {row.get('action')} ({row.get('id')}) — confirm when {confirm_when} — {state}"
        )
    actions = summary.get("demo_admin_actions") or []
    if actions:
        lines.extend(
            [
                "",
                "Demo admin actions:",
            ]
        )
        for row in actions:
            lines.append(
                f"- {row['action']} — {row['endpoint']} → {row['field']}"
            )
    return "\n".join(lines)


def build_demo_gates_payload_from_status(status: dict) -> dict:
    health = status["health"]
    active = build_demo_active_gates(health)
    payload = {
        "walkthrough_intact": demo_walkthrough_intact(health),
        "health_status": str(health["status"]),
        "health_label": str(health["label"]),
        "summary": str(health["summary"]),
        "issues": list(health.get("issues") or []),
        "present_facility_count": health.get("present_facility_count"),
        "broadcasting_facility_count": health.get("broadcasting_facility_count"),
        "expected_facility_count": health.get("expected_facility_count"),
        "gate_hints": list(health.get("gate_hints") or []),
        "active_gates": active,
        "gate_count": len(DEMO_GATE_DEFINITIONS),
        "demo_admin_action_count": len(DEMO_ADMIN_ACTION_DEMO_GATES),
        "gates": [
            {**row, "active": row["id"] in active}
            for row in DEMO_GATE_DEFINITIONS
        ],
        "demo_admin_actions": list(DEMO_ADMIN_ACTION_DEMO_GATES),
    }
    payload["clipboard_text"] = build_demo_gates_clipboard_text(payload)
    return payload


def build_demo_gates_summary(db: Session) -> dict:
    status = build_demo_environment_status(db)
    return status["demo_gates"]


def build_demo_health(
    *,
    loaded: bool,
    facility_count: int,
    expected_facility_count: int,
    portal_ready: bool,
    push_subscriptions_ready: bool,
    offers: list[dict],
) -> dict:
    issues: list[str] = []

    if facility_count == 0:
        return {
            "status": "red",
            "label": "NOT READY",
            "summary": "No demo shifts loaded. Run full demo setup.",
            "issues": ["No demo facilities loaded"],
        }

    if facility_count < expected_facility_count:
        issues.append(f"{facility_count}/{expected_facility_count} demo facilities present")

    if not portal_ready:
        issues.append("Portal logins incomplete for demo clinicians")

    if not push_subscriptions_ready:
        issues.append("Push subscriptions incomplete for demo clinicians")

    locked = [
        row["facility_name"]
        for row in offers
        if row.get("offer_id") and row.get("compliance_lock_status") not in (None, "BROADCASTING")
    ]
    if locked:
        issues.append(f"{len(locked)} shift(s) locked — reset demo environment")

    unloaded = [
        row["facility_name"]
        for row in offers
        if not row.get("loaded") and not row.get("resettable")
    ]
    if unloaded:
        issues.append(f"{len(unloaded)} shift(s) missing or not broadcasting")

    no_match = [
        row["facility_name"]
        for row in offers
        if row.get("loaded") and row.get("matched_clinician_count", 0) == 0
    ]
    if no_match:
        issues.append(f"{len(no_match)} shift(s) with zero matched clinicians")

    ready = (
        loaded
        and portal_ready
        and push_subscriptions_ready
        and not locked
        and not unloaded
        and not no_match
    )
    if ready:
        return {
            "status": "green",
            "label": "READY",
            "summary": "Demo environment is ready for walkthroughs.",
            "issues": [],
        }

    if facility_count < max(1, expected_facility_count // 2):
        status = "red"
        label = "NOT READY"
    else:
        status = "yellow"
        label = "PARTIAL"

    return {
        "status": status,
        "label": label,
        "summary": issues[0] if issues else "Demo environment needs attention.",
        "issues": issues,
    }


def build_demo_environment_status(db: Session) -> dict:
    offers: list[dict] = []
    loaded_count = 0

    for facility_name in DEMO_FACILITY_NAMES:
        facility = (
            db.query(MarylandFacility)
            .filter(MarylandFacility.name == facility_name)
            .first()
        )
        if facility is None:
            offers.append(
                {
                    "facility_name": facility_name,
                    "state": "",
                    "facility_type": "",
                    "shift_role": "",
                    "offer_id": None,
                    "loaded": False,
                    "resettable": False,
                    "compliance_lock_status": None,
                    "matched_clinician_count": 0,
                    "push_ready_count": 0,
                    "portal_deep_link": None,
                }
            )
            continue

        offer = (
            db.query(OfferCareJobOffer)
            .filter(
                OfferCareJobOffer.facility_id == facility.facility_id,
                OfferCareJobOffer.compliance_lock_status == "BROADCASTING",
            )
            .order_by(OfferCareJobOffer.created_at.asc())
            .first()
        )
        if offer is None:
            primary_offer = (
                db.query(OfferCareJobOffer)
                .filter(OfferCareJobOffer.facility_id == facility.facility_id)
                .order_by(OfferCareJobOffer.created_at.asc())
                .first()
            )
            if primary_offer is not None and str(primary_offer.compliance_lock_status) != "BROADCASTING":
                offers.append(
                    _build_locked_demo_offer_row(
                        db,
                        facility_name=facility_name,
                        facility=facility,
                        offer=primary_offer,
                    )
                )
                continue
            offers.append(
                {
                    "facility_name": facility_name,
                    "state": facility.state,
                    "facility_type": facility.facility_type,
                    "shift_role": "",
                    "offer_id": None,
                    "loaded": False,
                    "resettable": False,
                    "compliance_lock_status": None,
                    "matched_clinician_count": 0,
                    "push_ready_count": 0,
                    "portal_deep_link": None,
                }
            )
            continue

        row = get_open_shift_by_id(db, offer.offer_id)
        if row is None:
            offers.append(
                {
                    "facility_name": facility_name,
                    "state": facility.state,
                    "facility_type": facility.facility_type,
                    "shift_role": offer.shift_role,
                    "offer_id": str(offer.offer_id),
                    "loaded": False,
                    "resettable": _demo_offer_resettable(str(offer.offer_id), offer.compliance_lock_status),
                    "compliance_lock_status": offer.compliance_lock_status,
                    "matched_clinician_count": 0,
                    "push_ready_count": 0,
                    "portal_deep_link": demo_portal_deep_link(str(offer.offer_id)),
                    **_demo_clinician_fields(None),
                }
            )
            continue

        matched_count, push_ready_count = _count_matched_clinicians(db, row)
        demo_clinician = find_demo_clinician_for_shift(db, row)
        loaded_count += 1
        offers.append(
            {
                "facility_name": facility_name,
                "state": str(row["state"]),
                "facility_type": str(row["facility_type"]),
                "shift_role": str(row["shift_role"]),
                "offer_id": str(row["offer_id"]),
                "loaded": True,
                "resettable": False,
                "compliance_lock_status": str(row["compliance_lock_status"]),
                "matched_clinician_count": matched_count,
                "push_ready_count": push_ready_count,
                "portal_deep_link": demo_portal_deep_link(str(row["offer_id"])),
                **_demo_clinician_fields(demo_clinician),
            }
        )

    clinicians = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email.in_(DEMO_SEED_CLINICIAN_EMAILS))
        .order_by(MarylandProvider.state.asc(), MarylandProvider.email.asc())
        .all()
    )
    portal_account_ids: set = set()
    push_subscription_ids: set = set()
    if clinicians:
        provider_ids = [provider.provider_id for provider in clinicians]
        portal_account_ids = {
            row[0]
            for row in db.query(ClinicianPortalAccount.provider_id)
            .filter(ClinicianPortalAccount.provider_id.in_(provider_ids))
            .all()
        }
        push_subscription_ids = {
            row[0]
            for row in db.query(ClinicianPushSubscription.provider_id)
            .filter(ClinicianPushSubscription.provider_id.in_(provider_ids))
            .distinct()
            .all()
        }

    clinician_rows = [
        {
            "email": provider.email,
            "full_name": provider.full_name,
            "state": provider.state,
            "credential_type": provider.credential_type,
            "portal_enabled": provider.provider_id in portal_account_ids,
            "push_enabled": provider.provider_id in push_subscription_ids,
        }
        for provider in clinicians
    ]

    present_count = sum(1 for row in offers if _demo_facility_present(row))
    expected_count = len(DEMO_FACILITY_NAMES)
    health = build_demo_health(
        loaded=loaded_count == expected_count,
        facility_count=present_count,
        expected_facility_count=expected_count,
        portal_ready=bool(clinicians) and all(row["portal_enabled"] for row in clinician_rows),
        push_subscriptions_ready=bool(clinicians)
        and all(row["push_enabled"] for row in clinician_rows),
        offers=offers,
    )
    health = {
        **health,
        "present_facility_count": present_count,
        "broadcasting_facility_count": loaded_count,
        "expected_facility_count": expected_count,
    }
    health["gate_hints"] = build_demo_gate_hints(health)
    health["active_gates"] = build_demo_active_gates(health)
    health["gate_count"] = len(DEMO_GATE_DEFINITIONS)
    health["demo_admin_action_count"] = len(DEMO_ADMIN_ACTION_DEMO_GATES)

    status = {
        "loaded": loaded_count == expected_count,
        "facility_count": loaded_count,
        "present_facility_count": present_count,
        "expected_facility_count": expected_count,
        "portal_account_count": sum(1 for row in clinician_rows if row["portal_enabled"]),
        "portal_ready": bool(clinicians) and all(row["portal_enabled"] for row in clinician_rows),
        "push_subscription_count": sum(1 for row in clinician_rows if row["push_enabled"]),
        "push_subscriptions_ready": bool(clinicians) and all(row["push_enabled"] for row in clinician_rows),
        "demo_portal_password_hint": DEMO_PORTAL_PASSWORD,
        "offers": offers,
        "clinicians": clinician_rows,
        "next_steps": DEMO_NEXT_STEPS,
        "health": health,
    }
    status["demo_gates"] = build_demo_gates_payload_from_status(status)
    status["demo_admin_actions"] = list(DEMO_ADMIN_ACTION_DEMO_GATES)
    status["demo_admin_action_count"] = len(DEMO_ADMIN_ACTION_DEMO_GATES)
    return status


def list_demo_offer_ids(db: Session) -> list[UUID]:
    status = build_demo_environment_status(db)
    return [UUID(row["offer_id"]) for row in status["offers"] if row.get("offer_id")]


def _primary_demo_offers(db: Session) -> list[OfferCareJobOffer]:
    offers: list[OfferCareJobOffer] = []
    for facility_name in DEMO_FACILITY_NAMES:
        facility = (
            db.query(MarylandFacility)
            .filter(MarylandFacility.name == facility_name)
            .first()
        )
        if facility is None:
            continue
        offer = (
            db.query(OfferCareJobOffer)
            .filter(OfferCareJobOffer.facility_id == facility.facility_id)
            .order_by(OfferCareJobOffer.created_at.asc())
            .first()
        )
        if offer is not None:
            offers.append(offer)
    return offers


def _reset_demo_offers(db: Session, offers: list[OfferCareJobOffer]) -> dict:
    offer_ids = [offer.offer_id for offer in offers]
    placements_cleared = 0
    offers_reset = 0
    if offer_ids:
        placement_ids = [
            row[0]
            for row in db.query(ClinicalPlacementLedger.placement_id)
            .filter(ClinicalPlacementLedger.offer_id.in_(offer_ids))
            .all()
        ]
        if placement_ids:
            db.query(VmsSubmissionLog).filter(
                VmsSubmissionLog.placement_id.in_(placement_ids)
            ).delete(synchronize_session=False)
        placements_cleared = (
            db.query(ClinicalPlacementLedger)
            .filter(ClinicalPlacementLedger.offer_id.in_(offer_ids))
            .delete(synchronize_session=False)
        )
    for offer in offers:
        changed = (
            str(offer.compliance_lock_status) != "BROADCASTING"
            or offer.assigned_provider_id is not None
        )
        if changed:
            offers_reset += 1
        offer.compliance_lock_status = "BROADCASTING"
        offer.assigned_provider_id = None
    if offer_ids:
        db.commit()
    return {
        "offer_count": len(offers),
        "offers_reset": offers_reset,
        "placements_cleared": placements_cleared,
    }


def reset_demo_environment(db: Session) -> dict:
    return _reset_demo_offers(db, _primary_demo_offers(db))


def reset_demo_offer(db: Session, offer_id: UUID) -> dict | None:
    offer = (
        db.query(OfferCareJobOffer)
        .filter(OfferCareJobOffer.offer_id == offer_id)
        .first()
    )
    if offer is None:
        return None
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id == offer.facility_id)
        .first()
    )
    if facility is None or facility.name not in DEMO_FACILITY_NAMES:
        return None
    result = _reset_demo_offers(db, [offer])
    facility_name = facility.name
    if result["offers_reset"] or result["placements_cleared"]:
        message = (
            f"Reset {facility_name} — unlocked shift and cleared "
            f"{result['placements_cleared']} placement(s)"
        )
    else:
        message = f"{facility_name} is already broadcasting with no placements to clear"
    db.refresh(offer)
    offer_row = _build_broadcasting_demo_offer_row(
        db,
        facility_name=facility_name,
        facility=facility,
        offer=offer,
    )
    return {
        "offer_id": str(offer_id),
        "facility_name": facility_name,
        "shift_role": offer.shift_role,
        "offers_reset": result["offers_reset"],
        "placements_cleared": result["placements_cleared"],
        "message": message,
        "offer_row": offer_row,
    }


def notify_matched_on_demo_environment(db: Session) -> dict:
    offer_ids = list_demo_offer_ids(db)
    sent = notify_matched_clinicians_for_offers(db, offer_ids) if offer_ids else 0
    return {"offer_count": len(offer_ids), "matched_push_alerts_sent": sent}


def notify_matched_on_demo_offer(db: Session, offer_id: UUID) -> dict | None:
    row = _demo_status_row_for_offer(db, offer_id)
    if row is None or not row.get("offer_id"):
        return None
    if str(row.get("compliance_lock_status") or "") != "BROADCASTING":
        return {
            "offer_id": str(offer_id),
            "facility_name": str(row.get("facility_name") or ""),
            "shift_role": str(row.get("shift_role") or ""),
            "matched_push_alerts_sent": 0,
            "message": "Shift is not broadcasting.",
        }
    sent = notify_matched_clinicians_for_offer(db, offer_id)
    return {
        "offer_id": str(offer_id),
        "facility_name": str(row.get("facility_name") or ""),
        "shift_role": str(row.get("shift_role") or ""),
        "matched_push_alerts_sent": sent,
        "message": f"Sent {sent} matched push alert(s) for {row.get('facility_name')}.",
    }


def run_full_demo_setup(db: Session, *, notify_matched: bool = True) -> dict:
    reset = reset_demo_environment(db)
    seed = seed_all_mid_atlantic_demos(db)
    push_subscriptions = ensure_demo_push_subscriptions(db)
    if notify_matched:
        matched_push = notify_matched_on_demo_environment(db)
    else:
        matched_push = {
            "offer_count": len(list_demo_offer_ids(db)),
            "matched_push_alerts_sent": 0,
        }
    status = build_demo_environment_status(db)
    return {
        "reset": reset,
        "seed": seed,
        "push_subscriptions": push_subscriptions,
        "matched_push": matched_push,
        "status": status,
    }


def build_demo_ready_gate(db: Session) -> dict:
    health = build_demo_environment_status(db)["health"]
    ready = health["status"] == "green"
    warning = None
    if not ready:
        issues = list(health.get("issues") or [])
        issue_preview = "; ".join(issues[:3])
        if len(issues) > 3:
            issue_preview += f" (+{len(issues) - 3} more)"
        warning = (
            f"Demo health is {health['label']} ({health['status']}) — {health['summary']}"
            + (f" Issues: {issue_preview}" if issue_preview else "")
            + ". Run full demo setup or resolve issues before exporting walkthrough materials."
        )
    return {
        "ready": ready,
        "health_status": str(health["status"]),
        "health_label": str(health["label"]),
        "summary": str(health["summary"]),
        "issues": list(health.get("issues") or []),
        "warning": warning,
    }


def build_demo_walkthrough_script(db: Session) -> dict:
    status = build_demo_environment_status(db)
    gate = build_demo_ready_gate(db)
    links = build_demo_links(db)
    lines = [
        "# OfferCare Mid-Atlantic Demo Walkthrough",
        "",
        "## Before you start",
        "1. Admin → Run full demo setup (auto-resets locked shifts, then re-seeds)",
        "2. Or use Reset demo environment between walkthroughs without re-seeding",
        "",
        "## Portal login",
        f"- Portal: {links['portal_login_url']}",
        f"- Password for all demo clinicians: {links['portal_password_hint']}",
        "",
        "## Demo shifts",
    ]
    for index, row in enumerate(links["offers"], start=1):
        clinician_email = row.get("demo_clinician_email") or "matched clinician"
        clinician_name = row.get("demo_clinician_name") or ""
        name_suffix = f" ({clinician_name})" if clinician_name else ""
        lines.extend(
            [
                "",
                f"### {index}. {row['facility_name']} ({row['state']})",
                f"- Role: {row['shift_role']}",
                f"- Sign in as: `{clinician_email}`{name_suffix}",
                f"- Deep link: `{row['portal_url']}`",
                "- Walkthrough: open link → sign in → highlight shift → tap Lock",
            ]
        )
    lines.extend(
        [
            "",
            "## After each walkthrough",
            "- Admin → Reset demo environment to unlock shifts and clear placements",
            "",
            "## Status snapshot",
            f"- Health: {status['health']['label']} ({status['health']['status']})",
            f"- Present: {status['present_facility_count']}/{status['expected_facility_count']} facilities",
            f"- Broadcasting: {status['facility_count']}/{status['expected_facility_count']} facilities",
            f"- Demo admin actions: {len(DEMO_ADMIN_ACTION_DEMO_GATES)} cataloged",
            f"- Portal ready: {'yes' if status['portal_ready'] else 'no'}",
            f"- Push subscriptions ready: {'yes' if status['push_subscriptions_ready'] else 'no'}",
            "",
            "## Admin confirmation gates",
        ]
    )
    for hint in status["health"].get("gate_hints") or []:
        lines.append(f"- {hint}")
    active_gates = status["health"].get("active_gates") or []
    if active_gates:
        lines.append(f"- Active now: {', '.join(active_gates)}")
    gates_summary = build_demo_gates_summary(db)
    lines.extend(
        [
            "",
            "### Gate matrix",
            f"- Total confirmation gates: {gates_summary['gate_count']}",
            f"- Demo admin actions catalog: {gates_summary['demo_admin_action_count']}",
        ]
    )
    for row in gates_summary["gates"]:
        state = "active now" if row["active"] else "inactive"
        confirm_when = str(row["confirm_when"]).replace("_", " ")
        lines.append(
            f"- {row['action']} (`{row['id']}`) — confirm when {confirm_when} — {state}"
        )
    lines.extend(
        [
            "",
            "### Demo actions with embedded demo_gates",
            "- Embedded demo_gates snapshots include gate_count, demo_admin_action_count, and the demo_admin_actions catalog on every mutating response",
            "- Demo admin actions refresh the gate matrix without a separate status fetch:",
        ]
    )
    for row in DEMO_ADMIN_ACTION_DEMO_GATES:
        lines.append(
            f"- {row['action']} — `{row['endpoint']}` → `{row['field']}` "
            "(gate matrix, demo_admin_action_count, demo_admin_actions catalog)"
        )
    return {
        "markdown": "\n".join(lines),
        "offer_count": len(links["offers"]),
        "filename": "offercare-demo-walkthrough.md",
        "demo_ready": gate["ready"],
        "demo_ready_warning": gate["warning"],
        "health_status": gate["health_status"],
        "health_label": gate["health_label"],
    }


def build_demo_status_json(db: Session) -> dict:
    status = build_demo_environment_status(db)
    return {
        "filename": DEMO_STATUS_JSON_FILENAME,
        "content": json.dumps(status, indent=2),
    }


def build_demo_gates_json(db: Session) -> dict:
    summary = build_demo_gates_summary(db)
    return {
        "filename": DEMO_GATES_JSON_FILENAME,
        "content": json.dumps(summary, indent=2),
    }


def build_demo_gates_txt(db: Session) -> dict:
    summary = build_demo_gates_summary(db)
    return {
        "filename": DEMO_GATES_TXT_FILENAME,
        "content": summary["clipboard_text"],
    }


def build_demo_status_csv(db: Session) -> dict:
    status = build_demo_environment_status(db)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["DEMO STATUS SUMMARY"])
    writer.writerow(["metric", "value"])
    writer.writerow(["health_status", status["health"]["status"]])
    writer.writerow(["health_label", status["health"]["label"]])
    writer.writerow(["health_summary", status["health"]["summary"]])
    writer.writerow(["health_present_facility_count", status["health"].get("present_facility_count", "")])
    writer.writerow(
        ["health_broadcasting_facility_count", status["health"].get("broadcasting_facility_count", "")]
    )
    writer.writerow(
        ["health_expected_facility_count", status["health"].get("expected_facility_count", "")]
    )
    writer.writerow(["health_gate_hints", "; ".join(status["health"].get("gate_hints") or [])])
    writer.writerow(["health_active_gates", ", ".join(status["health"].get("active_gates") or [])])
    writer.writerow(["health_gate_count", status["health"].get("gate_count", "")])
    writer.writerow(["health_demo_admin_action_count", status["health"].get("demo_admin_action_count", "")])
    writer.writerow(["demo_admin_action_count", status.get("demo_admin_action_count", "")])
    writer.writerow(["loaded", status["loaded"]])
    writer.writerow(["facility_count", status["facility_count"]])
    writer.writerow(["present_facility_count", status["present_facility_count"]])
    writer.writerow(["expected_facility_count", status["expected_facility_count"]])
    writer.writerow(["portal_ready", status["portal_ready"]])
    writer.writerow(["push_subscriptions_ready", status["push_subscriptions_ready"]])
    writer.writerow(["portal_account_count", status["portal_account_count"]])
    writer.writerow(["push_subscription_count", status["push_subscription_count"]])
    writer.writerow([])
    writer.writerow(["DEMO OFFERS"])
    writer.writerow(
        [
            "facility_name",
            "state",
            "facility_type",
            "shift_role",
            "offer_id",
            "loaded",
            "resettable",
            "compliance_lock_status",
            "matched_clinician_count",
            "push_ready_count",
            "demo_clinician_email",
            "demo_clinician_name",
            "portal_deep_link",
        ]
    )
    for row in status["offers"]:
        writer.writerow(
            [
                row.get("facility_name", ""),
                row.get("state", ""),
                row.get("facility_type", ""),
                row.get("shift_role", ""),
                row.get("offer_id", ""),
                row.get("loaded", False),
                row.get("resettable", False),
                row.get("compliance_lock_status", ""),
                row.get("matched_clinician_count", 0),
                row.get("push_ready_count", 0),
                row.get("demo_clinician_email", ""),
                row.get("demo_clinician_name", ""),
                row.get("portal_deep_link", ""),
            ]
        )
    writer.writerow([])
    writer.writerow(["DEMO CLINICIANS"])
    writer.writerow(["email", "full_name", "state", "credential_type", "portal_enabled", "push_enabled"])
    for row in status["clinicians"]:
        writer.writerow(
            [
                row.get("email", ""),
                row.get("full_name", ""),
                row.get("state", ""),
                row.get("credential_type", ""),
                row.get("portal_enabled", False),
                row.get("push_enabled", False),
            ]
        )
    demo_gates = status.get("demo_gates")
    if demo_gates:
        writer.writerow([])
        writer.writerow(["DEMO GATES"])
        writer.writerow(["metric", "value"])
        writer.writerow(["walkthrough_intact", demo_gates["walkthrough_intact"]])
        writer.writerow(["health_status", demo_gates["health_status"]])
        writer.writerow(["health_label", demo_gates["health_label"]])
        writer.writerow(["gate_count", demo_gates["gate_count"]])
        writer.writerow(["demo_admin_action_count", demo_gates["demo_admin_action_count"]])
        writer.writerow(["active_gates", ", ".join(demo_gates["active_gates"])])
        writer.writerow([])
        writer.writerow(["DEMO GATE MATRIX"])
        writer.writerow(["id", "action", "confirm_when", "active"])
        for row in demo_gates["gates"]:
            writer.writerow([row["id"], row["action"], row["confirm_when"], row["active"]])
        append_demo_admin_actions_csv(writer)
    return {
        "filename": DEMO_STATUS_CSV_FILENAME,
        "content": buffer.getvalue(),
    }


def build_demo_export_bundle(db: Session) -> dict:
    walkthrough = build_demo_walkthrough_script(db)
    status_json = build_demo_status_json(db)
    status_csv = build_demo_status_csv(db)
    gates_json = build_demo_gates_json(db)
    gates_txt = build_demo_gates_txt(db)
    status = build_demo_environment_status(db)
    gate = build_demo_ready_gate(db)
    gates = build_demo_gates_summary(db)
    health = status["health"]
    readme = "\n".join(
        [
            "OfferCare Mid-Atlantic Demo Bundle",
            "",
            f"Health: {health['label']} ({health['status']})",
            health["summary"],
            (
                f"Active gates: {', '.join(gates['active_gates'])}"
                if gates["active_gates"]
                else "Active gates: none"
            ),
            f"Confirmation gates configured: {gates['gate_count']}",
            f"Demo admin actions catalog: {len(DEMO_ADMIN_ACTION_DEMO_GATES)} actions",
            "",
            "Files:",
            f"- {walkthrough['filename']} — presenter walkthrough with deep links",
            f"- {gates_json['filename']} — confirmation gate matrix, active gates, and demo admin actions catalog",
            f"- {gates_txt['filename']} — copy/paste gate matrix snapshot with demo admin actions catalog",
            f"- {status_json['filename']} — full demo status snapshot with embedded demo_gates and demo admin actions catalog",
            f"- {status_csv['filename']} — QA checklist spreadsheet with demo gate matrix",
            "",
            "Generated from Admin → Demo environment panel.",
        ]
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(walkthrough["filename"], walkthrough["markdown"])
        archive.writestr(gates_json["filename"], gates_json["content"])
        archive.writestr(gates_txt["filename"], gates_txt["content"])
        archive.writestr(status_json["filename"], status_json["content"])
        archive.writestr(status_csv["filename"], status_csv["content"])
        archive.writestr(DEMO_EXPORT_README_FILENAME, readme)
    return {
        "filename": DEMO_EXPORT_ZIP_FILENAME,
        "content": buffer.getvalue(),
        "file_count": 6,
        "demo_ready": gate["ready"],
        "demo_ready_warning": gate["warning"],
        "health_status": gate["health_status"],
        "health_label": gate["health_label"],
        "active_gates": gates["active_gates"],
    }


def build_demo_links(db: Session) -> dict:
    status = build_demo_environment_status(db)
    offers = [
        {
            "facility_name": row["facility_name"],
            "state": row["state"],
            "shift_role": row["shift_role"],
            "offer_id": row["offer_id"],
            "portal_url": row["portal_deep_link"],
            "demo_clinician_email": row.get("demo_clinician_email"),
            "demo_clinician_name": row.get("demo_clinician_name"),
        }
        for row in status["offers"]
        if row.get("offer_id") and row.get("portal_deep_link")
    ]
    sample_email = SAMPLE_DEMO_CLINICIAN_EMAIL
    if not any(row["email"] == sample_email for row in status["clinicians"]):
        sample_email = status["clinicians"][0]["email"] if status["clinicians"] else sample_email
    return {
        "portal_login_url": "/portal/",
        "portal_password_hint": status["demo_portal_password_hint"],
        "sample_clinician_email": sample_email,
        "offers": offers,
    }


def get_demo_hint_for_offer(db: Session, offer_id: UUID) -> dict | None:
    row = get_open_shift_by_id(db, offer_id)
    if row is None or str(row["facility_name"]) not in DEMO_FACILITY_NAMES:
        return None
    demo_clinician = find_demo_clinician_for_shift(db, row)
    if demo_clinician is None:
        return None
    return {
        "offer_id": str(offer_id),
        "facility_name": str(row["facility_name"]),
        "shift_role": str(row["shift_role"]),
        "clinician_email": demo_clinician.email,
        "clinician_name": demo_clinician.full_name,
        "portal_password_hint": DEMO_PORTAL_PASSWORD,
    }


def check_demo_hint_for_clinician(
    db: Session,
    offer_id: UUID,
    provider: MarylandProvider,
) -> dict | None:
    hint = get_demo_hint_for_offer(db, offer_id)
    if hint is None:
        return None
    matches = str(provider.email).lower() == str(hint["clinician_email"]).lower()
    if matches:
        message = f"Signed in as the matched clinician for {hint['facility_name']}."
    else:
        message = (
            f"This demo shift is matched to {hint['clinician_email']}. "
            "Sign out and sign in as that clinician to lock it."
        )
    return {
        "offer_id": hint["offer_id"],
        "facility_name": hint["facility_name"],
        "shift_role": hint["shift_role"],
        "expected_clinician_email": hint["clinician_email"],
        "expected_clinician_name": hint["clinician_name"],
        "signed_in_email": provider.email,
        "signed_in_name": provider.full_name,
        "matches": matches,
        "message": message,
    }


def _demo_status_row_for_offer(db: Session, offer_id: UUID | None) -> dict | None:
    if offer_id is not None:
        offer = (
            db.query(OfferCareJobOffer)
            .filter(OfferCareJobOffer.offer_id == offer_id)
            .first()
        )
        if offer is None:
            return None
        facility = (
            db.query(MarylandFacility)
            .filter(MarylandFacility.facility_id == offer.facility_id)
            .first()
        )
        if facility is None or facility.name not in DEMO_FACILITY_NAMES:
            return None
        shift_row = get_open_shift_by_id(db, offer_id)
        demo_clinician = find_demo_clinician_for_shift(db, shift_row) if shift_row else None
        lock_status = str(offer.compliance_lock_status)
        if shift_row is None and lock_status != "BROADCASTING":
            return _build_locked_demo_offer_row(
                db,
                facility_name=facility.name,
                facility=facility,
                offer=offer,
            )
        return {
            "facility_name": facility.name,
            "state": facility.state,
            "facility_type": facility.facility_type,
            "shift_role": offer.shift_role,
            "offer_id": str(offer.offer_id),
            "loaded": shift_row is not None,
            "resettable": _demo_offer_resettable(str(offer.offer_id), lock_status),
            "compliance_lock_status": offer.compliance_lock_status,
            **_demo_clinician_fields(demo_clinician),
        }

    status = build_demo_environment_status(db)
    for row in status["offers"]:
        if (
            row.get("loaded")
            and row.get("offer_id")
            and row.get("compliance_lock_status") == "BROADCASTING"
        ):
            return row
    return next((row for row in status["offers"] if row.get("loaded") and row.get("offer_id")), None)


def run_demo_lock_smoke_test(db: Session, *, offer_id: UUID | None = None) -> dict:
    row = _demo_status_row_for_offer(db, offer_id)
    if row is None or not row.get("offer_id"):
        return {
            "ok": False,
            "status": "no_offers",
            "message": "No loaded demo offers found. Run full demo setup first.",
        }

    shift_row = get_open_shift_by_id(db, UUID(str(row["offer_id"])))
    if shift_row is None and str(row.get("compliance_lock_status") or "") != "BROADCASTING":
        return {
            "ok": False,
            "status": "already_locked",
            "message": "This shift was already locked by another clinician.",
            "facility_name": row.get("facility_name"),
            "shift_role": row.get("shift_role"),
            "offer_id": row.get("offer_id"),
            "clinician_email": row.get("demo_clinician_email"),
            "clinician_name": row.get("demo_clinician_name"),
            "compliance_lock_status": row.get("compliance_lock_status"),
        }
    if shift_row is None:
        return {
            "ok": False,
            "status": "not_found",
            "message": "Demo shift not found or no longer broadcasting.",
            "facility_name": row.get("facility_name"),
            "shift_role": row.get("shift_role"),
            "offer_id": row.get("offer_id"),
        }

    provider = find_demo_clinician_for_shift(db, shift_row)
    if provider is None:
        return {
            "ok": False,
            "status": "no_clinician",
            "message": "No matched demo clinician found for this shift.",
            "facility_name": row.get("facility_name"),
            "shift_role": row.get("shift_role"),
            "offer_id": row.get("offer_id"),
        }

    result = lock_shift_for_provider(
        db,
        provider=provider,
        offer_id=UUID(str(row["offer_id"])),
    )
    offer = (
        db.query(OfferCareJobOffer)
        .filter(OfferCareJobOffer.offer_id == UUID(str(row["offer_id"])))
        .first()
    )
    placement = None
    if result.placement_id is not None:
        placement = (
            db.query(ClinicalPlacementLedger)
            .filter(ClinicalPlacementLedger.placement_id == result.placement_id)
            .first()
        )

    offer_row = None
    if offer is not None:
        facility = (
            db.query(MarylandFacility)
            .filter(MarylandFacility.facility_id == offer.facility_id)
            .first()
        )
        if facility is not None:
            offer_row = _build_locked_demo_offer_row(
                db,
                facility_name=row.get("facility_name") or facility.name,
                facility=facility,
                offer=offer,
            )

    return {
        "ok": result.status == "locked" and placement is not None,
        "status": result.status,
        "message": result.message,
        "facility_name": row.get("facility_name"),
        "shift_role": row.get("shift_role"),
        "offer_id": str(result.offer_id) if result.offer_id else row.get("offer_id"),
        "clinician_email": provider.email,
        "clinician_name": provider.full_name,
        "compliance_lock_status": offer.compliance_lock_status if offer else None,
        "placement_id": str(result.placement_id) if result.placement_id else None,
        "placement_verified": placement is not None,
        "vms_submission_status": placement.vms_submission_status if placement else None,
        "offer_row": offer_row,
    }
