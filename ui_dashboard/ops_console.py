"""VettedCare.ai — Maryland Market Operations Console (isolated Streamlit UI)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CSV_PATH = REPO_ROOT / "data_engine" / "raw_leads" / "md_facilities_scraped.csv"
QUEUE_PATH = REPO_ROOT / "logs" / "manus" / "md_outreach_queue.json"
PROVIDERS_PATH = REPO_ROOT / "logs" / "manus" / "processed_providers.json"
SHIFTS_PATH = REPO_ROOT / "logs" / "manus" / "active_shifts.json"
TIMESHEETS_PATH = REPO_ROOT / "logs" / "manus" / "reconciled_timesheets.json"
DESK_PIPELINE_PATH = REPO_ROOT / "logs" / "manus" / "desk_pipeline_runs.json"
MANUS_HANDOFF_PATH = REPO_ROOT / "logs" / "manus" / "manus_desk_handoff.json"
BACKUP_DISPATCH_PATH = REPO_ROOT / "logs" / "manus" / "backup_dispatches.json"
BACKUP_NOTIFY_PATH = REPO_ROOT / "logs" / "manus" / "backup_notify_cascade.json"
BACKUP_CASCADE_ACTIVE_PATH = REPO_ROOT / "logs" / "manus" / "backup_cascade_active.json"

st.set_page_config(
    page_title="VettedCare.ai — Maryland Operations",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DARK_CSS = """
<style>
    .stApp { background-color: #09090b; color: #e4e4e7; }
    [data-testid="stMetric"] {
        background: #0f172a;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 12px;
        box-shadow: 0 1px 2px rgba(37, 99, 235, 0.2);
    }
    [data-testid="stMetricLabel"] { color: #93c5fd !important; font-size: 0.8rem; }
    [data-testid="stMetricValue"] { color: #ffffff !important; }
    [data-testid="stDataFrame"],
    [data-testid="stTable"] {
        border: 1px solid #3b82f6;
        border-radius: 8px;
        overflow: hidden;
    }
    [data-testid="stCodeBlock"] {
        border: 1px solid #3b82f6 !important;
        border-radius: 8px;
    }
    .compliance-banner {
        background: #451a03; border: 1px solid #ea580c; border-radius: 8px;
        padding: 14px 18px; margin-top: 24px; color: #fed7aa; font-size: 0.95rem;
    }
    h1 { color: #fafafa !important; }
    h2 {
        color: #fafafa !important;
        border-left: 4px solid #3b82f6;
        padding-left: 12px;
    }
    h3, h4, h5 { color: #93c5fd !important; }
    .sys-chip {
        display: inline-block;
        background: #1e3a8a;
        color: #bfdbfe;
        border: 1px solid #3b82f6;
        border-radius: 999px;
        padding: 4px 12px;
        font-size: 0.75rem;
        font-family: monospace;
        margin-bottom: 12px;
    }
    [data-testid="stTextInput"] label,
    [data-testid="stTextInput"] label p {
        color: #93c5fd !important;
    }
    [data-testid="stTextInput"] input {
        background-color: #0f172a !important;
        color: #fafafa !important;
        border: 1px solid #3b82f6 !important;
        caret-color: #fafafa !important;
    }
    [data-testid="stTextInput"] input::placeholder {
        color: #64748b !important;
    }
    [data-testid="stTextArea"] label,
    [data-testid="stTextArea"] label p {
        color: #93c5fd !important;
    }
    [data-testid="stTextArea"] textarea {
        background-color: #0f172a !important;
        color: #fafafa !important;
        border: 1px solid #3b82f6 !important;
        caret-color: #fafafa !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #3b82f6 !important;
        background: #0f172a !important;
    }
    .stButton > button {
        background-color: #2563eb !important;
        color: #ffffff !important;
        border: 1px solid #3b82f6 !important;
        border-radius: 8px !important;
    }
    .stButton > button:hover {
        background-color: #1d4ed8 !important;
        color: #ffffff !important;
        border-color: #60a5fa !important;
    }
    .stButton > button p,
    .stButton > button div {
        color: #ffffff !important;
    }
    [data-testid="stCaptionContainer"] {
        color: #94a3b8 !important;
    }
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=30)
def load_facilities_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


@st.cache_data(ttl=30)
def load_outreach_queue(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        return pd.DataFrame(), {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("queue") or payload.get("payloads") or []
    return pd.DataFrame(rows), payload


@st.cache_data(ttl=30)
def load_processed_providers(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        return pd.DataFrame(), {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    applicants = payload.get("applicants") or []
    if not applicants:
        return pd.DataFrame(), payload
    rows = []
    for applicant in applicants:
        rows.append(
            {
                "name": applicant.get("name"),
                "license_type": applicant.get("license_type"),
                "license_number": applicant.get("license_number"),
                "has_gna_endorsement": bool(applicant.get("has_gna_endorsement")),
                "county": applicant.get("county"),
                "target_facility_type": applicant.get("target_facility_type"),
                "placement_eligible": bool(applicant.get("placement_eligible")),
                "compliance_status": applicant.get("compliance_status"),
                "days_to_expiry": applicant.get("days_to_expiry"),
                "errors": ", ".join(applicant.get("errors") or []),
            }
        )
    return pd.DataFrame(rows), payload


def _style_gna_endorsement(df: pd.DataFrame):
    gna_blue = "background-color: #1e3a8a; color: #bfdbfe; font-weight: 600"

    def _highlight(row: pd.Series):
        if bool(row.get("has_gna_endorsement")):
            return [gna_blue] * len(row)
        return [""] * len(row)

    return df.style.apply(_highlight, axis=1)


@st.cache_data(ttl=30)
def load_active_shifts(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        return pd.DataFrame(), {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    shifts = payload.get("shifts") or []
    return pd.DataFrame(shifts), payload


@st.cache_data(ttl=30)
def load_reconciled_timesheets(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        return pd.DataFrame(), {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    timesheets = payload.get("timesheets") or []
    return pd.DataFrame(timesheets), payload


@st.cache_data(ttl=30)
def load_desk_pipeline_runs(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        return pd.DataFrame(), {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = []
    for run in payload.get("runs") or []:
        pipeline = str(run.get("pipeline") or "full").upper()
        booking = _booking_from_desk_run(run)
        shift = booking.get("shift") or {}
        surge = booking.get("surge_pricing") or {}
        selected = booking.get("selected_provider") or {}
        rows.append(
            {
                "run_id": str(run.get("run_id") or "")[:24],
                "staged_at_utc": run.get("staged_at_utc"),
                "pipeline": pipeline,
                "status": run.get("status") or booking.get("status"),
                "facility": shift.get("facility_name"),
                "role": shift.get("required_role"),
                "selected_provider": selected.get("provider_id"),
                "surge_rate": surge.get("final_surge_bill_rate"),
                "source": (
                    "production_db"
                    if run.get("live_execution") is True or run.get("mode") == "PRODUCTION_SLICE"
                    else ("manus_api" if str(run.get("run_id") or "").startswith("desk-api-") else "desk_ui")
                ),
            }
        )
    return pd.DataFrame(rows), payload


def _booking_from_desk_run(run: dict) -> dict:
    if isinstance(run.get("booking"), dict):
        return run["booking"]
    result = run.get("result")
    if isinstance(result, dict):
        if isinstance(result.get("booking"), dict):
            return result["booking"]
        if result.get("pipeline") == "BOOKING":
            return result
    return {}


def _render_desk_booking_panel(booking: dict) -> None:
    surge = booking.get("surge_pricing") or {}
    selected = booking.get("selected_provider")

    st.success(f"Desk cycle complete · booking status: `{booking.get('status')}`")
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Matches Found", booking.get("match_count", 0))
    o2.metric("Active Commitments", booking.get("active_commitments_count", 0))
    o3.metric("Surge Multiplier", f"{surge.get('applied_multiplier', 1.0):.2f}x")
    o4.metric("Surge Bill Rate", f"${surge.get('final_surge_bill_rate', 0):.2f}/hr")

    if selected:
        st.markdown(
            f"**Selected provider:** `{selected.get('provider_id')}` · "
            f"{selected.get('full_name')} · conflict: `{selected.get('conflict_reason')}`"
        )
    elif booking.get("booking_candidates"):
        st.warning("Matches found but **ScheduleConflictEngine** blocked all assignments.")

    conflict_rows = booking.get("booking_candidates") or []
    if conflict_rows:
        st.markdown("**Global Scheduling Anti-Collision — candidate safety audit:**")
        st.dataframe(pd.DataFrame(conflict_rows), use_container_width=True, hide_index=True)

    st.markdown("**Surge pricing detail:**")
    st.json(
        {
            "base_bill_rate": surge.get("base_bill_rate"),
            "applied_multiplier": surge.get("applied_multiplier"),
            "final_surge_bill_rate": surge.get("final_surge_bill_rate"),
            "surge_tier_trigger": surge.get("surge_tier_trigger"),
        }
    )


def _render_desk_pipeline_live_feed(runs_df: pd.DataFrame, payload: dict) -> None:
    st.markdown("##### Live pipeline feed (Manus API + desk UI)")
    st.caption(
        f"Auto-refreshes from `{DESK_PIPELINE_PATH.relative_to(REPO_ROOT)}` · "
        f"last updated `{payload.get('updated_at_utc', '—')}`"
    )
    if runs_df.empty:
        st.info(
            "No desk pipeline runs yet. Trigger via **Run Full Desk Pipeline** or "
            "`POST /api/vettedcare/manus/desk/run`."
        )
        return

    st.dataframe(runs_df.iloc[::-1], use_container_width=True, hide_index=True)

    latest = (payload.get("runs") or [])[-1]
    pipeline = str(latest.get("pipeline") or "full").upper()
    with st.expander(f"Latest run detail · `{str(latest.get('run_id', ''))[:28]}…`", expanded=False):
        if pipeline in {"FULL", "BOOKING"} or latest.get("booking") or _booking_from_desk_run(latest):
            _render_desk_booking_panel(_booking_from_desk_run(latest))
        elif pipeline == "CALLOUT" or latest.get("dispatch"):
            dispatch = latest.get("dispatch") or (latest.get("result") or {}).get("dispatch") or {}
            st.warning(
                f"Call-out routing · status `{dispatch.get('status')}` · "
                f"backups `{len(dispatch.get('backup_candidates') or [])}`"
            )
            st.json(dispatch)
        elif pipeline in {"PENALTY", "PENALTY_AUDIT"} or latest.get("audit"):
            audit = latest.get("audit") or (latest.get("result") or {}).get("audit") or {}
            st.error(
                f"Penalty audit · `${audit.get('calculated_penalty_fee', 0):,.2f}` · "
                f"`{audit.get('invoice_status_flag')}`"
            )
            st.json(audit)
        else:
            st.json(latest)


@st.cache_data(ttl=30)
def load_backup_dispatches(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        return pd.DataFrame(), {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = []
    for dispatch in payload.get("dispatches") or []:
        shift = dispatch.get("shift") or {}
        rows.append(
            {
                "dispatch_id": str(dispatch.get("dispatch_id") or "")[:28],
                "staged_at_utc": dispatch.get("staged_at_utc"),
                "status": dispatch.get("status"),
                "live_execution": dispatch.get("live_execution"),
                "slice_key": dispatch.get("slice_key"),
                "facility": shift.get("facility_name"),
                "original_provider_id": dispatch.get("original_provider_id"),
                "backup_count": len(dispatch.get("backup_candidates") or []),
            }
        )
    return pd.DataFrame(rows), payload


def _render_backup_dispatch_feed(dispatches_df: pd.DataFrame, payload: dict) -> None:
    st.markdown("##### Backup dispatch feed (staging + live)")
    st.caption(
        f"Source: `{BACKUP_DISPATCH_PATH.relative_to(REPO_ROOT)}` · "
        f"log live_execution `{payload.get('live_execution', False)}`"
    )
    if dispatches_df.empty:
        st.info("No backup dispatches logged yet.")
        return
    st.dataframe(dispatches_df.iloc[::-1], use_container_width=True, hide_index=True)


@st.cache_data(ttl=30)
def load_backup_notify_cascade(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        return pd.DataFrame(), {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = []
    for event in payload.get("events") or []:
        cascade = event.get("cascade") or event.get("cascade_status") or {}
        notifications = event.get("notifications") or []
        if event.get("event_type") == "ADVANCE" and event.get("notification"):
            notifications = [event["notification"]]
        last_notify = notifications[-1] if notifications else {}
        rows.append(
            {
                "staged_at_utc": event.get("staged_at_utc"),
                "event_type": event.get("event_type") or "START",
                "dispatch_id": str(event.get("dispatch_id") or cascade.get("dispatch_id") or "")[:32],
                "status": event.get("status") or cascade.get("status"),
                "sms_dry_run": event.get("sms_dry_run"),
                "sent_count": cascade.get("sent_count", len(notifications)),
                "cascade_status": cascade.get("status"),
                "last_provider": last_notify.get("name") or last_notify.get("provider_id"),
                "last_rank": last_notify.get("rank"),
            }
        )
    return pd.DataFrame(rows), payload


@st.cache_data(ttl=30)
def load_backup_cascade_active(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        return pd.DataFrame(), {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = []
    for dispatch_id, session in (payload.get("cascades") or {}).items():
        notified = session.get("notified") or []
        rows.append(
            {
                "dispatch_id": str(dispatch_id)[:32],
                "status": session.get("status"),
                "slice_key": session.get("slice_key"),
                "notified_count": len(notified),
                "sent_count": sum(
                    1 for row in notified if str(row.get("status")) in {"DRY_RUN", "SENT"}
                ),
                "created_at_utc": session.get("created_at_utc"),
                "updated_at_utc": session.get("updated_at_utc"),
            }
        )
    return pd.DataFrame(rows), payload


def _render_backup_notify_cascade_feed(
    notify_df: pd.DataFrame,
    notify_meta: dict,
    active_df: pd.DataFrame,
    active_meta: dict,
) -> None:
    st.markdown("##### Backup notify cascade feed")
    st.caption(
        f"Sources: `{BACKUP_NOTIFY_PATH.relative_to(REPO_ROOT)}` · "
        f"`{BACKUP_CASCADE_ACTIVE_PATH.relative_to(REPO_ROOT)}`"
    )
    if active_df.empty and notify_df.empty:
        st.info("No backup notify cascade events yet.")
        return
    if not active_df.empty:
        st.markdown("**Active cascades**")
        st.dataframe(active_df.iloc[::-1], use_container_width=True, hide_index=True)
    if not notify_df.empty:
        st.markdown("**Notify event log**")
        st.dataframe(notify_df.iloc[::-1], use_container_width=True, hide_index=True)


def _financial_desk_metrics(timesheets_df: pd.DataFrame, payload: dict) -> tuple[float, float, int]:
    if timesheets_df.empty:
        return 0.0, 0.0, int(payload.get("overtime_compliance_holds") or 0)
    gross_revenue = float(timesheets_df["gross_bill_amount"].sum())
    total_margin = float(timesheets_df["desk_margin"].sum())
    margin_pct = (total_margin / gross_revenue * 100.0) if gross_revenue > 0 else 0.0
    holds = int((timesheets_df["status"] == "OVERTIME_COMPLIANCE_HOLD").sum())
    return gross_revenue, margin_pct, holds


def _fetch_pipeline_velocity_metrics() -> dict[str, float | int]:
    """Live CandidatePipelineBroker KPIs — safe fallback on DB timeout or broker failure."""
    try:
        from strategy.candidate_pipeline_broker import CandidatePipelineBroker

        broker = CandidatePipelineBroker()
        try:
            payload = broker.fetch_dashboard_payload()
        finally:
            broker.close()
        return {
            "average_match_time_seconds": float(payload.get("average_match_time_seconds") or 0.0),
            "total_automated_dispatches": int(payload.get("total_automated_dispatches") or 0),
            "stripe_conversion_rate": float(payload.get("stripe_conversion_rate") or 0.0),
        }
    except Exception:
        return {
            "average_match_time_seconds": 0.0,
            "total_automated_dispatches": 0,
            "stripe_conversion_rate": 0.0,
        }


def _scan_unfilled_retry_demands() -> list[Any]:
    """Active match-retry cascade queue — safe fallback on DB timeout."""
    try:
        from strategy.match_retry_scheduler import MatchRetryScheduler

        scheduler = MatchRetryScheduler()
        try:
            return list(scheduler.scan_unfilled_demands())
        finally:
            scheduler.close()
    except Exception:
        return []


def _evaluate_schedule_clearance_safe(
    provider_id: str,
    start_time: datetime,
    end_time: datetime,
) -> tuple[bool, dict[str, Any]]:
    """Wrap ScheduleConflictValidator — cleanroom fallback when calendar table is absent."""
    try:
        from strategy.schedule_conflict_validator import ScheduleConflictValidator

        validator = ScheduleConflictValidator()
        try:
            payload = validator.evaluate_schedule_clearance(provider_id, start_time, end_time)
        finally:
            validator.close()
        return False, payload
    except Exception:
        return True, {
            "has_conflict": False,
            "conflict_type": "CLEAR",
            "conflicting_event_id": None,
        }


def _format_calendar_timestamp(value: datetime | None) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _fetch_provider_calendar_events_safe(
    provider_id: str,
    *,
    limit: int = 50,
) -> tuple[bool, list[dict[str, Any]]]:
    """Load clinician calendar rows — cleanroom fallback when table is unavailable."""
    token = str(provider_id or "").strip().upper()
    if not token:
        return False, []
    try:
        from app.database import SessionLocal
        from app.models.clinician_calendar import ClinicianCalendarEvent

        db = SessionLocal()
        try:
            rows = (
                db.query(ClinicianCalendarEvent)
                .filter(ClinicianCalendarEvent.provider_id == token)
                .order_by(ClinicianCalendarEvent.start_time.asc())
                .limit(int(limit))
                .all()
            )
            events: list[dict[str, Any]] = []
            for row in rows:
                events.append(
                    {
                        "event_id": str(row.id),
                        "provider_id": str(row.provider_id),
                        "shift_id": str(row.shift_id or "—"),
                        "event_type": str(row.event_type),
                        "start_time": _format_calendar_timestamp(row.start_time),
                        "end_time": _format_calendar_timestamp(row.end_time),
                        "created_at": _format_calendar_timestamp(row.created_at),
                    }
                )
            return False, events
        finally:
            db.close()
    except Exception:
        return True, []


def _sentinel_validate_semantic_query(query: str) -> tuple[bool, str, list[str]]:
    """Sentinel pre-flight — pgvector / natural-language intake guard."""
    token = str(query or "").strip()
    issues: list[str] = []
    if len(token) < 8:
        issues.append("query_too_short_min_8_chars")
    if len(token) > 2000:
        issues.append("query_exceeds_2000_char_limit")
    if "\x00" in token:
        issues.append("null_byte_rejected")
    lowered = token.lower()
    if token and not any(ch.isalpha() for ch in token):
        issues.append("query_must_contain_alpha_tokens")
    if "drop table" in lowered or "delete from" in lowered:
        issues.append("sql_injection_pattern_rejected")
    if issues:
        return False, "SENTINEL_BLOCK", issues
    return True, "SENTINEL_PASS", ["embedding_dim_1536", "pgvector_cosine_ready"]


def _sentinel_validate_payout_payload(payload: dict) -> tuple[bool, str, list[str]]:
    """Sentinel pre-flight — Stripe instant payout timesheet shape guard."""
    issues: list[str] = []
    required = ("timesheet_id", "provider_id", "shift_status", "supervisor_signed", "gross_pay_amount")
    for key in required:
        if key not in payload or payload.get(key) in (None, ""):
            issues.append(f"missing_{key}")

    shift_status = str(payload.get("shift_status") or "").upper()
    if shift_status != "CONFIRMED":
        issues.append("shift_status_must_be_CONFIRMED")

    if not bool(payload.get("supervisor_signed")):
        issues.append("supervisor_signature_required")

    try:
        gross = float(payload.get("gross_pay_amount") or 0)
    except (TypeError, ValueError):
        gross = 0.0
        issues.append("gross_pay_amount_not_numeric")
    if gross <= 0:
        issues.append("gross_pay_amount_must_be_positive")

    provider_id = str(payload.get("provider_id") or "")
    if provider_id and not provider_id.startswith("CNA-MD-"):
        issues.append("provider_id_format_warning")

    stripe_card = str(payload.get("stripe_debit_card_id") or "")
    stripe_acct = str(payload.get("stripe_connect_account_id") or "")
    if not stripe_card or not stripe_acct:
        issues.append("stripe_destination_incomplete")

    if issues:
        return False, "SENTINEL_BLOCK", issues
    return True, "SENTINEL_PASS", ["stripe_instant_payout_shape_ok", f"net_pay_line_${gross:.2f}"]


def _compliance_verification_badge(
    *,
    compliance_status: str | None = None,
    is_eligible: bool | None = None,
) -> str:
    """Map credential screening codes to inline Streamlit verification badges."""
    try:
        status = str(compliance_status or "").strip().upper()
        eligible = bool(is_eligible) if is_eligible is not None else True
    except Exception:
        return "🟡 AUDIT PENDING"

    if status == "CREDENTIALS_PASSED" and eligible:
        return "🟢 CREDENTIALS VERIFIED"
    if status == "OIG_FLAGGED":
        return "🔴 SECURITY ALERT: OIG EXCLUDED"
    if status == "LICENSE_EXPIRED":
        return "⚠️ COMPLIANCE FAULT: LICENSE EXPIRED"
    if status == "CREDENTIALS_PENDING" or not status:
        return "🟡 AUDIT PENDING"
    if not eligible:
        return f"🟡 {status.replace('_', ' ')}"
    return "🟡 AUDIT PENDING"


def _compliance_badge_for_match(row: Any) -> str:
    try:
        if isinstance(row, dict):
            return _compliance_verification_badge(
                compliance_status=row.get("compliance_status"),
                is_eligible=row.get("is_eligible"),
            )
        return _compliance_verification_badge(
            compliance_status=getattr(row, "compliance_status", None),
            is_eligible=getattr(row, "is_eligible", None),
        )
    except Exception:
        return "🟡 AUDIT PENDING"


def _render_sentinel_chip(ok: bool, label: str, detail: str) -> None:
    color = "#166534" if ok else "#991b1b"
    border = "#4ade80" if ok else "#f87171"
    text = "#ecfdf5" if ok else "#fef2f2"
    st.markdown(
        f"""
        <div style="
            display:inline-block;
            background:{color};
            border:1px solid {border};
            border-radius:999px;
            padding:4px 12px;
            margin:0 8px 8px 0;
            font-size:0.75rem;
            font-family:monospace;
            color:{text};
        ">{label} · {detail}</div>
        """,
        unsafe_allow_html=True,
    )


def _matcher_candidates_from_providers(payload: dict) -> list[dict]:
    candidates: list[dict] = []
    for applicant in payload.get("applicants") or []:
        verification_ts = str(applicant.get("verification_timestamp") or "").strip()
        if not verification_ts:
            continue
        candidates.append(
            {
                "provider_id": applicant.get("license_number") or applicant.get("name"),
                "full_name": applicant.get("name"),
                "role": str(applicant.get("license_type") or "").upper(),
                "county": applicant.get("county"),
                "has_gna_endorsement": bool(applicant.get("has_gna_endorsement")),
                "license_verified_at": verification_ts,
                "background_check_verified_at": verification_ts,
                "placement_eligible": bool(applicant.get("placement_eligible")),
            }
        )
    return candidates


def _gna_barred_cnas(candidates: list[dict], shift: dict) -> list[str]:
    if str(shift.get("facility_type")).upper() != "SNF":
        return []
    if str(shift.get("required_role")).upper() != "CNA":
        return []
    barred: list[str] = []
    for candidate in candidates:
        if str(candidate.get("role")).upper() != "CNA":
            continue
        if not bool(candidate.get("has_gna_endorsement")):
            barred.append(str(candidate.get("provider_id")))
    return barred


def _require_ops_console_auth() -> bool:
    from app.config import settings

    admin_key = str(settings.ADMIN_API_KEY or "").strip()
    if not admin_key:
        st.warning("ADMIN_API_KEY not set — console open in staging-only mode.")
        return True

    if st.session_state.get("ops_console_authenticated"):
        return True

    st.markdown("### Ops Console Access")
    st.caption("Authenticate with your VettedCare `ADMIN_API_KEY` to unlock production controls.")
    entered = st.text_input("Admin API Key", type="password", key="ops_console_admin_key")
    if st.button("Unlock Console", type="primary", key="ops_console_unlock"):
        if entered == admin_key:
            st.session_state.ops_console_authenticated = True
            st.rerun()
        else:
            st.error("Invalid admin key.")
    return False


def main() -> None:
    if not _require_ops_console_auth():
        return

    facilities_df = load_facilities_csv(CSV_PATH)
    queue_df, queue_meta = load_outreach_queue(QUEUE_PATH)
    providers_df, providers_meta = load_processed_providers(PROVIDERS_PATH)
    shifts_df, shifts_meta = load_active_shifts(SHIFTS_PATH)
    timesheets_df, timesheets_meta = load_reconciled_timesheets(TIMESHEETS_PATH)
    desk_runs_df, desk_runs_meta = load_desk_pipeline_runs(DESK_PIPELINE_PATH)
    backup_dispatches_df, backup_dispatches_meta = load_backup_dispatches(BACKUP_DISPATCH_PATH)
    backup_notify_df, backup_notify_meta = load_backup_notify_cascade(BACKUP_NOTIFY_PATH)
    backup_active_df, backup_active_meta = load_backup_cascade_active(BACKUP_CASCADE_ACTIVE_PATH)

    facility_count = len(facilities_df)
    campaign_count = len(queue_df) if not queue_df.empty else int(queue_meta.get("count") or 0)
    if not providers_df.empty and "placement_eligible" in providers_df.columns:
        eligible_count = int(providers_df["placement_eligible"].sum())
    else:
        eligible_count = int(providers_meta.get("placement_eligible_count") or 0)

    st.markdown(
        '<span class="sys-chip">SYS_STATUS · MD_MARKET_OPS · STAGING</span>',
        unsafe_allow_html=True,
    )
    st.title("VettedCare.ai — Maryland Market Operations Console")
    st.caption("Facility registry · Staging outreach queue · COMAR compliance guardrails")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Facilities Ingested", facility_count)
    col2.metric("Staging Campaigns", campaign_count)
    col3.metric("Compliance Guardrails", "STRICT / COMAR 10.07.02 Active")
    col4.metric("Eligible Providers", eligible_count)

    gross_revenue, margin_pct, compliance_holds = _financial_desk_metrics(timesheets_df, timesheets_meta)
    st.markdown("##### Financial Desk Health")
    fin1, fin2, fin3 = st.columns(3)
    fin1.metric("Gross Revenue Generated", f"${gross_revenue:,.2f}")
    fin2.metric("Gross Margin %", f"{margin_pct:.1f}%")
    fin3.metric("Compliance Holds Active", compliance_holds)

    st.subheader("Maryland Facility Registry")
    st.caption(f"Source: `{CSV_PATH.relative_to(REPO_ROOT)}`")
    if facilities_df.empty:
        st.warning("No facility rows found. Expected `data_engine/raw_leads/md_facilities_scraped.csv`.")
    else:
        st.dataframe(facilities_df, use_container_width=True, hide_index=True)

    st.subheader("Maryland Compliant Workforce Registry")
    st.caption(f"Source: `{PROVIDERS_PATH.relative_to(REPO_ROOT)}` · GNA-endorsed rows highlighted")
    if providers_df.empty:
        st.warning(
            "No processed provider rows found. Run `scripts/process_nurse_applicants.py` to generate staging data."
        )
    else:
        st.dataframe(
            _style_gna_endorsement(providers_df),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Algorithmic Shift Matching Desk")
    st.caption(f"Source: `{SHIFTS_PATH.relative_to(REPO_ROOT)}` · engine: `strategy/unified_shift_matcher.py`")
    if shifts_df.empty:
        st.warning(
            "No active shift orders found. Run `scripts/simulate_shift_orders.py` to generate staging shifts."
        )
    else:
        st.dataframe(shifts_df, use_container_width=True, hide_index=True)

        if st.button("Run Live Staging Match Test", type="primary"):
            from strategy.unified_shift_matcher import UnifiedShiftMatcher

            candidates = _matcher_candidates_from_providers(providers_meta)
            if not candidates:
                st.error("No matcher candidates found in processed_providers.json")
            else:
                matcher = UnifiedShiftMatcher(candidates, source="registry")
                evaluation_ts = datetime.now(timezone.utc).isoformat()
                st.success(f"Match engine run · evaluation barrier: `{evaluation_ts}`")

                for _, shift in shifts_df.iterrows():
                    shift_request = {
                        "order_id": shift.get("order_id"),
                        "facility_name": shift.get("facility_name"),
                        "facility_type": shift.get("facility_type"),
                        "required_role": shift.get("required_role"),
                        "facility_county": shift.get("county"),
                        "county": shift.get("county"),
                        "evaluation_window_barrier": shift.get("shift_timestamp"),
                    }
                    matches = matcher.find_compliant_matches(shift_request, evaluation_ts)
                    barred = _gna_barred_cnas(candidates, shift.to_dict())

                    title = (
                        f"{shift.get('facility_name')} · {shift.get('required_role')} · "
                        f"{shift.get('county')} · {str(shift.get('order_id'))[:8]}…"
                    )
                    with st.expander(title, expanded=True):
                        st.markdown(
                            f"**Shift:** `{shift.get('shift_timestamp')}` · "
                            f"**Type:** `{shift.get('facility_type')}`"
                        )
                        if matches:
                            match_rows = [
                                {
                                    "provider_id": row.get("provider_id"),
                                    "full_name": row.get("full_name"),
                                    "county": row.get("county"),
                                    "county_match": row.get("_match_meta", {}).get("county_match"),
                                    "has_gna_endorsement": row.get("has_gna_endorsement"),
                                    "placement_eligible": row.get("placement_eligible"),
                                }
                                for row in matches
                            ]
                            st.markdown("**Top compliant matches (county-weighted):**")
                            st.dataframe(pd.DataFrame(match_rows), use_container_width=True, hide_index=True)
                        else:
                            st.info("No compliant matches for this shift under current barriers.")

                        if barred:
                            st.markdown(
                                "**SNF CNA GNA firewall — barred candidate IDs (no GNA endorsement):** "
                                + ", ".join(f"`{token}`" for token in barred)
                            )
                        elif (
                            str(shift.get("facility_type")).upper() == "SNF"
                            and str(shift.get("required_role")).upper() == "CNA"
                        ):
                            st.markdown("**SNF CNA GNA firewall:** no barred CNA IDs in candidate pool.")

    st.subheader("Automated Shift Disruption & Fallback Desk")
    st.caption("Engine: `strategy/backup_routing_engine.py` · staging dispatch log: `logs/manus/backup_dispatches.json`")

    disruption_shift_id = "eb1ac566-7331-4af0-aa14-6a7077614773"
    disruption_primary_id = "CNA-MD-88421"
    disruption_primary_name = "Aisha Thompson"
    disruption_facility = "Arbor Ridge at Riderwood"

    st.markdown(
        f"**LIVE SCENARIO · EMERGENCY CALL-OUT**  \n"
        f"Primary nurse **{disruption_primary_name}** (`{disruption_primary_id}`) assigned to "
        f"Shift Order `{disruption_shift_id[:8]}` at **{disruption_facility}** "
        f"(Montgomery · SNF · CNA) has triggered an emergency **Call-Out** notification "
        f"**3 hours before market open**."
    )

    if st.button("Simulate Sudden Provider Call-Out", type="primary", key="simulate_provider_callout"):
        from strategy.backup_routing_engine import BackupRoutingEngine

        if not providers_meta.get("applicants"):
            st.error("No workforce registry found. Expected `logs/manus/processed_providers.json`.")
        else:
            try:
                router = BackupRoutingEngine(providers_meta)
                dispatch = router.trigger_backup_routing(
                    disrupted_shift_id=disruption_shift_id,
                    original_provider_id=disruption_primary_id,
                )
                load_backup_dispatches.clear()
            except (FileNotFoundError, ValueError, TypeError) as exc:
                st.error(f"Backup routing failed: {exc}")
            else:
                st.warning(
                    f"Primary nurse **{disruption_primary_name}** (`{disruption_primary_id}`) "
                    f"has been safely detached from Shift Order `{disruption_shift_id[:8]}…` at "
                    f"**{disruption_facility}**. Fallback routing status: `{dispatch.get('status')}`."
                )

                backups = dispatch.get("backup_candidates") or []
                if backups:
                    backup_rows = [
                        {
                            "rank": row.get("rank"),
                            "provider_id": row.get("provider_id"),
                            "name": row.get("name"),
                            "license_type": row.get("license_type"),
                            "county": row.get("county"),
                            "gna_endorsement_verified": (
                                "YES · COMAR GNA" if row.get("has_gna_endorsement") else "NO"
                            ),
                            "compliance_status": row.get("compliance_status"),
                        }
                        for row in backups
                    ]
                    st.markdown("**Top 2 localized, fully compliant backup replacement candidates:**")
                    st.dataframe(
                        pd.DataFrame(backup_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info(
                        "No same-county compliant backups available under current GNA firewall rules. "
                        "Dispatch staged as `NO_BACKUP_AVAILABLE` — expand the Montgomery CNA pool or "
                        "relax county constraint in a future engine revision."
                    )

    _render_backup_dispatch_feed(backup_dispatches_df, backup_dispatches_meta)

    st.subheader("Revenue Optimization & Asset Protection Desk")
    st.caption(
        "Engines: `strategy/surge_pricing_engine.py` · `strategy/placement_penalty_engine.py`"
    )

    surge_col, asset_col = st.columns(2)

    with surge_col:
        st.markdown(
            "**CRISIS SURGE SCENARIO · OVERNIGHT CNA**  \n"
            "Emergency overnight CNA shift requested at **11:30 PM** with **less than one hour** "
            "of lead time before shift start (short-notice + night differential compounding)."
        )
        if st.button("Simulate Crisis Shift Surge", type="primary", key="simulate_crisis_shift_surge"):
            from strategy.surge_pricing_engine import SurgePricingEngine

            crisis_shift = {
                "order_id": "crisis-overnight-cna",
                "facility_name": "Arbor Ridge at Riderwood",
                "facility_type": "SNF",
                "county": "Montgomery",
                "required_role": "CNA",
                "shift_timestamp": "2026-06-28T00:15:00+00:00",
            }
            request_timestamp = "2026-06-27T23:30:00+00:00"

            try:
                surge_engine = SurgePricingEngine()
                surge_result = surge_engine.calculate_surge_rate(crisis_shift, request_timestamp)
            except (ValueError, TypeError) as exc:
                st.error(f"Surge pricing calculation failed: {exc}")
            else:
                st.success(f"Surge tier trigger: `{surge_result.get('surge_tier_trigger')}`")
                m1, m2, m3 = st.columns(3)
                m1.metric("Base Bill Rate", f"${surge_result['base_bill_rate']:.2f}/hr")
                m2.metric("Applied Multiplier", f"{surge_result['applied_multiplier']:.2f}x")
                m3.metric(
                    "Final Surge Bill Rate",
                    f"${surge_result['final_surge_bill_rate']:.2f}/hr",
                )
                if surge_result.get("capped_at_max"):
                    st.caption("Enterprise safety cap enforced at **1.4x max surge**.")

    with asset_col:
        st.markdown(
            "**CONTRACT THEFT HAZARD · DIRECT-HIRE BYPASS**  \n"
            "Facility **Arbor Ridge at Riderwood** attempting to permanently hire "
            "**Aisha Thompson** (`CNA-MD-88421`) after only **45 clinical hours** "
            "logged through the desk (160-hour vesting minimum)."
        )
        if st.button("Audit Contract Theft Hazard", type="primary", key="audit_contract_theft_hazard"):
            from strategy.placement_penalty_engine import PlacementPenaltyEngine

            try:
                penalty_engine = PlacementPenaltyEngine()
                penalty_result = penalty_engine.audit_permanent_placement(
                    facility_id="MD-SNF-ARBOR-RIDGE",
                    provider_id="CNA-MD-88421",
                    total_hours_worked=45.0,
                )
            except (ValueError, TypeError) as exc:
                st.error(f"Placement penalty audit failed: {exc}")
            else:
                st.error(
                    f"**MINIMUM HOURS VIOLATION PENALTY INVOICE**  \n"
                    f"Facility `{penalty_result['facility_id']}` · Provider `{penalty_result['provider_id']}`  \n"
                    f"Hours recorded: **{penalty_result['total_hours_recorded']:.0f}** / "
                    f"{penalty_result['contract_minimum_hours']} minimum  \n"
                    f"Calculated penalty fee: **${penalty_result['calculated_penalty_fee']:,.2f}**  \n"
                    f"Invoice status: `{penalty_result['invoice_status_flag']}`"
                )

    st.divider()
    with st.container(border=True):
        st.subheader("Frictionless Onboarding & Automated Payout Desk")
        st.caption(
            "Engine: `strategy/semantic_payout_engine.py` · Sentinel validates pgvector queries "
            "and Stripe payout payloads before execution · "
            "**Located directly below Revenue Optimization**"
        )
        st.markdown(
            '<span class="sys-chip">SENTINEL · DATA & API WATCHDOG · ACTIVE</span>',
            unsafe_allow_html=True,
        )

        try:
            _velocity_metrics = _fetch_pipeline_velocity_metrics()
            _avg_match_seconds = float(_velocity_metrics["average_match_time_seconds"])
            _auto_dispatches = int(_velocity_metrics["total_automated_dispatches"])
            _stripe_conv_rate = float(_velocity_metrics["stripe_conversion_rate"])
        except Exception:
            _avg_match_seconds = 0.0
            _auto_dispatches = 0
            _stripe_conv_rate = 0.0

        velocity_m1, velocity_m2, velocity_m3 = st.columns(3)
        velocity_m1.metric("Avg Match Time", f"{_avg_match_seconds:.1f} sec")
        velocity_m2.metric("Auto-Dispatches", f"🚀 {_auto_dispatches}")
        velocity_m3.metric("Stripe Escrow Conv. Rate", f"{_stripe_conv_rate:.1f}%")

        st.markdown("### 🕒 Active Autonomous Retry Cascade Queue")
        try:
            _cascade_demands = _scan_unfilled_retry_demands()
        except Exception:
            _cascade_demands = []

        if not _cascade_demands:
            st.info("🎉 All critical night shifts successfully filled. Cascade engine standing by.")
        else:
            _cascade_now = datetime.now(timezone.utc)
            _cascade_rows = []
            for _demand in _cascade_demands:
                _last_broadcast = _demand.last_broadcast_at
                if _last_broadcast is not None and _last_broadcast.tzinfo is None:
                    _last_broadcast = _last_broadcast.replace(tzinfo=timezone.utc)
                _elapsed_sec = (
                    max((_cascade_now - _last_broadcast).total_seconds(), 0.0)
                    if _last_broadcast is not None
                    else 0.0
                )
                _cascade_rows.append(
                    {
                        "offer_id": _demand.offer_id,
                        "shift_role": _demand.shift_role,
                        "dispatch_status": _demand.compliance_lock_status,
                        "elapsed_broadcast_min": round(_elapsed_sec / 60.0, 1),
                        "retry_attempt_count": _demand.retry_attempt_count,
                        "care_tags": ", ".join(_demand.care_tags),
                        "last_broadcast_at": (
                            _last_broadcast.isoformat() if _last_broadcast is not None else "—"
                        ),
                    }
                )
            st.dataframe(pd.DataFrame(_cascade_rows), use_container_width=True, hide_index=True)

        if st.button(
            "Force Global Cascade Optimization Run",
            type="secondary",
            key="force_global_cascade_optimization_run",
        ):
            try:
                from strategy.match_retry_scheduler import MatchRetryScheduler

                _cascade_scheduler = MatchRetryScheduler()
                try:
                    _cascade_scheduler.execute_retry_cascade()
                finally:
                    _cascade_scheduler.close()
                st.success("Cascade cycle executed successfully.")
            except Exception as exc:
                st.error(f"Cascade optimization run failed: {exc}")

        st.divider()
        st.markdown("### 📅 Clinician Operational Calendar & Conflict Desk")
        st.caption("Schedule simulator and live vault view · all times in **24-hour UTC**.")
        _calendar_now = datetime.now(timezone.utc)
        _calendar_start_date = _calendar_now.date()
        _calendar_end_date = _calendar_now.date()
        _calendar_provider_id = st.text_input(
            "Provider ID",
            value="CNA-MD-99001",
            key="calendar_conflict_provider_id",
        )
        _calendar_start_col, _calendar_end_col = st.columns(2)
        with _calendar_start_col:
            _shift_start_date = st.date_input(
                "Start Date",
                value=_calendar_start_date,
                key="calendar_shift_start_date",
            )
            _shift_start_time = st.time_input(
                "Start Time (24h)",
                value=time(7, 0),
                key="calendar_shift_start_time",
            )
        with _calendar_end_col:
            _shift_end_date = st.date_input(
                "End Date",
                value=_calendar_end_date,
                key="calendar_shift_end_date",
            )
            _shift_end_time = st.time_input(
                "End Time (24h)",
                value=time(15, 0),
                key="calendar_shift_end_time",
            )

        if st.button("Verify Schedule Clearance", type="primary", key="verify_schedule_clearance"):
            _proposed_start = datetime.combine(_shift_start_date, _shift_start_time, tzinfo=timezone.utc)
            _proposed_end = datetime.combine(_shift_end_date, _shift_end_time, tzinfo=timezone.utc)
            if _proposed_end <= _proposed_start:
                st.error("End Date/Time must be after Start Date/Time.")
            else:
                _migration_pending, _clearance = _evaluate_schedule_clearance_safe(
                    str(_calendar_provider_id or "").strip(),
                    _proposed_start,
                    _proposed_end,
                )
                if _migration_pending:
                    st.info(
                        "ℹ️ Calendar table migration pending. Simulation engine running in localized cleanroom mode."
                    )
                elif _clearance.get("conflict_type") == "CLEAR" and not _clearance.get("has_conflict"):
                    st.success(
                        "🟢 SCHEDULE CLEAR: Candidate is completely dispatch-eligible for this interval."
                    )
                elif _clearance.get("has_conflict") or _clearance.get("conflict_type") == "HARD_OVERLAP":
                    st.error(
                        "🔴 HARD CONFLICT DETECTED: Double-booking risk flagged with existing commitment."
                    )
                elif _clearance.get("conflict_type") == "SOFT_PREFERENCE_HIT":
                    st.warning(
                        "🟡 SOFT PREFERENCE OVERLAP: Schedule clear for dispatch, but clinician preference block noted."
                    )
                elif _clearance.get("conflict_type") == "FATIGUE_ELEVATED":
                    st.warning(
                        f"🟡 FATIGUE ELEVATED: Dispatch allowed, but fatigue score "
                        f"{_clearance.get('fatigue_score', '—')} is above the soft warn threshold."
                    )
                elif _clearance.get("conflict_type") == "FATIGUE_CAP_EXCEEDED":
                    st.error(
                        f"🔴 FATIGUE CAP EXCEEDED: Hard block — fatigue score "
                        f"{_clearance.get('fatigue_score', '—')} is too high for new dispatch."
                    )

        st.markdown("#### Provider Time Vault (Live)")
        _vault_col_a, _vault_col_b = st.columns([3, 1])
        with _vault_col_b:
            _load_vault = st.button("Load Provider Calendar", key="load_provider_calendar_vault")
        _provider_token = str(_calendar_provider_id or "").strip().upper()
        if _load_vault:
            _vault_pending, _vault_events = _fetch_provider_calendar_events_safe(_provider_token)
            st.session_state["calendar_vault_pending"] = _vault_pending
            st.session_state["calendar_vault_events"] = _vault_events
            st.session_state["calendar_vault_provider"] = _provider_token

        if st.session_state.get("calendar_vault_provider") == _provider_token and "calendar_vault_events" in st.session_state:
            if st.session_state.get("calendar_vault_pending"):
                st.info(
                    "ℹ️ Calendar table migration pending. Simulation engine running in localized cleanroom mode."
                )
            else:
                _vault_events = list(st.session_state.get("calendar_vault_events") or [])
                if not _vault_events:
                    st.info(f"No calendar events found for `{_provider_token}`.")
                else:
                    _commitments = sum(
                        1 for row in _vault_events if row.get("event_type") == "SHIFT_COMMITMENT"
                    )
                    _blackouts = sum(
                        1 for row in _vault_events if row.get("event_type") == "BLACKOUT_UNAVAILABLE"
                    )
                    _soft_blocks = sum(
                        1 for row in _vault_events if row.get("event_type") == "SOFT_BLOCK_PREFERENCE"
                    )
                    _vault_m1, _vault_m2, _vault_m3, _vault_m4 = st.columns(4)
                    _vault_m1.metric("Total Events", len(_vault_events))
                    _vault_m2.metric("Shift Commitments", _commitments)
                    _vault_m3.metric("Blackouts", _blackouts)
                    _vault_m4.metric("Soft Preferences", _soft_blocks)
                    st.dataframe(pd.DataFrame(_vault_events), use_container_width=True, hide_index=True)

        onboarding_col, payout_col = st.columns(2)
        default_semantic_query = (
            "CNAs with dementia care experience in Baltimore for night shifts — SNF memory unit coverage"
        )

        with onboarding_col:
            st.markdown("##### Semantic pgvector matching")
            st.markdown(
                "Facility request scenario: **CNAs with dementia care experience in Baltimore for night shifts**."
            )
            semantic_query = st.text_area(
                "Facility shift request (natural language)",
                value=default_semantic_query,
                height=100,
                key="sentinel_semantic_query_input",
            )
            sentinel_ok, sentinel_status, sentinel_notes = _sentinel_validate_semantic_query(semantic_query)
            _render_sentinel_chip(sentinel_ok, sentinel_status, " · ".join(sentinel_notes[:2]))

            if st.button("Execute Semantic Vector Search", type="primary", key="execute_semantic_vector_search"):
                if not sentinel_ok:
                    st.error(
                        "Sentinel blocked query — fix input before vector search. "
                        f"Issues: `{', '.join(sentinel_notes)}`"
                    )
                else:
                    from strategy.semantic_payout_engine import SemanticPayoutEngine

                    try:
                        semantic_engine = SemanticPayoutEngine()
                        vector_result = semantic_engine.find_top_vector_matches(
                            semantic_query,
                            shift_context={
                                "required_role": "CNA",
                                "facility_type": "SNF",
                                "facility_county": "Baltimore City",
                                "shift_band": "night",
                            },
                        )
                    except (ValueError, TypeError) as exc:
                        st.error(f"Semantic vector search failed: {exc}")
                    else:
                        top = vector_result.top_match
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Top similarity", f"{top.similarity_score:.4f}" if top else "—")
                        m2.metric("Candidates", vector_result.match_count)
                        m3.metric("Elapsed (ms)", f"{vector_result.elapsed_ms:.2f}")
                        if top:
                            top_badge = _compliance_badge_for_match(top)
                            st.success(
                                f"Top match: **{top.full_name}** (`{top.provider_id}`) · {top_badge}"
                            )
                        else:
                            st.success("No vector matches returned.")
                        if vector_result.matches:
                            st.markdown("**Verification badges (ranked candidates):**")
                            for row in vector_result.matches:
                                badge = _compliance_badge_for_match(row)
                                st.markdown(
                                    f"#{row.rank} **{row.full_name}** (`{row.provider_id}`) · {badge}"
                                )
                            match_rows = []
                            for row in vector_result.matches:
                                try:
                                    compliance_status = str(
                                        getattr(row, "compliance_status", "CREDENTIALS_PENDING") or "CREDENTIALS_PENDING"
                                    )
                                    is_eligible = bool(getattr(row, "is_eligible", False))
                                except Exception:
                                    compliance_status = "CREDENTIALS_PENDING"
                                    is_eligible = False
                                match_rows.append(
                                    {
                                        "rank": row.rank,
                                        "provider_id": row.provider_id,
                                        "name": row.full_name,
                                        "county": row.county,
                                        "similarity_score": row.similarity_score,
                                        "is_eligible": is_eligible,
                                        "compliance_status": compliance_status,
                                        "verification_badge": _compliance_verification_badge(
                                            compliance_status=compliance_status,
                                            is_eligible=is_eligible,
                                        ),
                                        "profile_preview": row.profile_preview,
                                    }
                                )
                            st.dataframe(pd.DataFrame(match_rows), use_container_width=True, hide_index=True)

        with payout_col:
            st.markdown("##### Instant pay retention")
            st.markdown(
                "**Shift settlement · digital supervisor signature on file**  \n"
                "Provider **Nia Patterson** (`CNA-MD-99001`) · 8-hour CNA shift · gross pay **$240.00** · "
                "Stripe instant rail · **30-minute** post sign-off window."
            )
            payout_payload = {
                "timesheet_id": "desk-sim-timesheet-001",
                "provider_id": "CNA-MD-99001",
                "shift_status": "CONFIRMED",
                "supervisor_signed": True,
                "supervisor_name": "Charge Nurse Davis",
                "gross_pay_amount": 240.00,
                "stripe_connect_account_id": "acct_test_montgomery",
                "stripe_debit_card_id": "card_test_montgomery",
            }
            pay_ok, pay_status, pay_notes = _sentinel_validate_payout_payload(payout_payload)
            _render_sentinel_chip(pay_ok, pay_status, " · ".join(pay_notes[:2]))
            st.json(
                {
                    "timesheet_id": payout_payload["timesheet_id"],
                    "provider_id": payout_payload["provider_id"],
                    "shift_status": payout_payload["shift_status"],
                    "supervisor_signed": payout_payload["supervisor_signed"],
                    "gross_pay_amount": payout_payload["gross_pay_amount"],
                }
            )

            if st.button("Simulate 30-Minute Stripe Payout", type="primary", key="simulate_stripe_instant_payout"):
                if not pay_ok:
                    st.error(
                        "Sentinel blocked payout payload — external shape invalid. "
                        f"Issues: `{', '.join(pay_notes)}`"
                    )
                else:
                    from uuid import uuid4

                    from strategy.semantic_payout_engine import SemanticPayoutEngine

                    payout_payload["timesheet_id"] = str(uuid4())
                    try:
                        payout_engine = SemanticPayoutEngine()
                        payout_result = payout_engine.trigger_instant_payout(payout_payload)
                    except (ValueError, TypeError, RuntimeError) as exc:
                        st.error(f"Instant payout simulation failed: {exc}")
                    else:
                        st.success(
                            f"**${payout_result.net_pay_amount:,.2f} NET DISTRIBUTED** · "
                            f"Provider `{payout_result.provider_id}` · "
                            f"Stripe {payout_result.stripe_mode} · "
                            f"ETA {payout_result.payout_eta_minutes} min · "
                            f"ref `{payout_result.stripe_reference}`"
                        )
                        pay_m1, pay_m2, pay_m3 = st.columns(3)
                        pay_m1.metric("Net pay", f"${payout_result.net_pay_amount:,.2f}")
                        pay_m2.metric("Gross pay", f"${payout_result.gross_pay_amount:,.2f}")
                        pay_m3.metric("Payout window", f"{payout_result.payout_eta_minutes} min")
                        st.caption(payout_result.message)

    st.subheader("Unified Maryland Desk Orchestrator")
    st.caption(
        "Engine: `strategy/desk_orchestrator.py` · Manus handoff: "
        f"`{MANUS_HANDOFF_PATH.relative_to(REPO_ROOT)}` · "
        f"runs log: `{DESK_PIPELINE_PATH.relative_to(REPO_ROOT)}`"
    )
    st.markdown(
        "**FULL DESK CYCLE · MANUS + VETTEDCARE**  \n"
        "Chains **match → conflict → surge → backup → penalty** across all five strategy engines. "
        "Commitments loaded from reconciled timesheets. Manus can also trigger via "
        "`POST /api/vettedcare/manus/desk/run` (see `scripts/test-manus-desk-pipeline.ps1`)."
    )

    _render_desk_pipeline_live_feed(desk_runs_df, desk_runs_meta)

    if st.button("Run Full Desk Pipeline", type="primary", key="run_full_desk_pipeline"):
        from strategy.desk_orchestrator import DeskOrchestrator, build_manus_desk_manifest

        if not providers_meta.get("applicants"):
            st.error("Workforce registry missing. Run `scripts/process_nurse_applicants.py`.")
        elif shifts_df.empty:
            st.error("No active shifts. Run `scripts/simulate_shift_orders.py`.")
        else:
            try:
                target_shift = shifts_df.iloc[0].to_dict()
                evaluation_ts = datetime.now(timezone.utc).isoformat()
                orchestrator = DeskOrchestrator(
                    providers_meta,
                    timesheets_payload=timesheets_meta,
                )
                desk_run = orchestrator.run_full_desk_cycle(
                    target_shift,
                    evaluation_timestamp=evaluation_ts,
                )
                DeskOrchestrator.persist_run(desk_run)
                DeskOrchestrator.write_manus_handoff(build_manus_desk_manifest(REPO_ROOT))
                load_desk_pipeline_runs.clear()

                _render_desk_booking_panel(desk_run["booking"])
            except (FileNotFoundError, ValueError, TypeError) as exc:
                st.error(f"Desk orchestrator failed: {exc}")

    st.markdown("##### Production slice · Montgomery SNF CNA (PostgreSQL)")
    st.caption(
        "Loads `facilities` + `maryland_providers` + assigned `offercare_job_offers` from PostgreSQL. "
        "Seed first: `scripts/seed_montgomery_snf_cna_slice.py`"
    )
    if st.button("Run Production DB Desk Cycle", type="primary", key="run_production_db_desk"):
        from app.database import SessionLocal
        from app.services.md_desk_production_loader import run_production_desk_cycle

        db = SessionLocal()
        try:
            prod_result = run_production_desk_cycle(db)
            load_desk_pipeline_runs.clear()
            booking = prod_result["result"]["booking"]
            st.success(
                f"**PRODUCTION_SLICE** · `{prod_result.get('slice_key')}` · "
                f"status `{prod_result.get('status')}` · live_execution **true**"
            )
            st.json(prod_result.get("db_source") or {})
            _render_desk_booking_panel(booking)
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Production desk cycle failed: {exc}")
        finally:
            db.close()

    if st.button("Execute Live Montgomery Call-Out Dispatch", type="primary", key="live_montgomery_callout"):
        from app.database import SessionLocal
        from app.services.md_desk_production_loader import run_production_live_callout

        db = SessionLocal()
        try:
            live_result = run_production_live_callout(db, original_provider_id="CNA-MD-88421")
            dispatch = live_result.get("dispatch") or {}
            notify = live_result.get("notify_cascade") or {}
            cascade = notify.get("cascade") or {}
            st.warning(
                f"**LIVE DISPATCH** · `{live_result.get('slice_key')}` · "
                f"status `{dispatch.get('status')}` · "
                f"backups `{len(dispatch.get('backup_candidates') or [])}` · "
                f"`live_execution: true`"
            )
            st.markdown(
                f"**Notify cascade:** `{notify.get('status')}` · "
                f"sms_dry_run `{notify.get('sms_dry_run')}` · "
                f"sent `{cascade.get('sent_count', 0)}` · "
                f"cascade `{cascade.get('status')}` · "
                f"next in `{cascade.get('seconds_until_eligible', 0)}s`"
            )
            if notify.get("notifications"):
                st.dataframe(pd.DataFrame(notify["notifications"]), use_container_width=True, hide_index=True)
            if cascade.get("dispatch_id"):
                st.session_state["last_backup_dispatch_id"] = cascade["dispatch_id"]
            st.json(dispatch)
            load_backup_dispatches.clear()
            load_backup_notify_cascade.clear()
            load_backup_cascade_active.clear()
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Live dispatch failed: {exc}")
        finally:
            db.close()

    last_dispatch_id = st.session_state.get("last_backup_dispatch_id")
    if not last_dispatch_id and backup_active_meta.get("cascades"):
        keys = list(backup_active_meta["cascades"].keys())
        if keys:
            last_dispatch_id = keys[-1]
            st.session_state["last_backup_dispatch_id"] = last_dispatch_id
    if last_dispatch_id:
        st.markdown("**Latest backup cascade dispatch_id**")
        st.code(last_dispatch_id, language=None)
    dispatch_id_input = st.text_input(
        "Backup cascade dispatch_id (optional override)",
        value=last_dispatch_id or "",
        placeholder="Run live call-out first, or paste dispatch_id here",
        key="manual_backup_dispatch_id",
    )
    if st.button("Advance Backup Cascade (manual tick)", type="primary", key="advance_backup_cascade"):
        from app.database import SessionLocal
        from app.services.md_backup_notify_cascade import advance_backup_notify_cascade

        dispatch_id = (dispatch_id_input or last_dispatch_id or "").strip()
        if not dispatch_id:
            st.error("Run a live call-out first or enter a dispatch_id.")
        else:
            db = SessionLocal()
            try:
                result = advance_backup_notify_cascade(db, str(dispatch_id), force=False, actor="ops_console")
                st.info(f"`{result.status}` · {result.message}")
                if result.cascade:
                    st.json(result.cascade)
                load_backup_notify_cascade.clear()
                load_backup_cascade_active.clear()
            except ValueError as exc:
                st.error(str(exc))
            finally:
                db.close()

    _render_backup_notify_cascade_feed(
        backup_notify_df,
        backup_notify_meta,
        backup_active_df,
        backup_active_meta,
    )

    st.subheader("Post-Shift Financial & Payroll Reconciliation Desk")
    st.caption(f"Source: `{TIMESHEETS_PATH.relative_to(REPO_ROOT)}`")
    if timesheets_df.empty:
        st.warning(
            "No reconciled timesheets found. Run `scripts/process_timesheets.py` to generate staging payroll data."
        )
    else:
        st.dataframe(timesheets_df, use_container_width=True, hide_index=True)
        if compliance_holds > 0 or (timesheets_df["status"] == "OVERTIME_COMPLIANCE_HOLD").any():
            st.markdown(
                '<div class="compliance-banner">'
                "⚠️ Invoice Automation Paused: COMAR Shift Hours Threshold Exceeded (>12 Hours). "
                "Reviewing supervisor audit trail before invoice generation."
                "</div>",
                unsafe_allow_html=True,
            )

    st.subheader("Staging Outreach Queue")
    st.caption(f"Source: `{QUEUE_PATH.relative_to(REPO_ROOT)}`")
    if queue_df.empty:
        st.warning("No staging queue objects found. Expected `logs/manus/md_outreach_queue.json`.")
    else:
        display_queue = queue_df.copy()
        if "personalized_message_body" in display_queue.columns:
            display_queue["message_preview"] = (
                display_queue["personalized_message_body"]
                .astype(str)
                .str.replace("\n", " ", regex=False)
                .str.slice(0, 160)
                + "…"
            )
        st.dataframe(display_queue, use_container_width=True, hide_index=True)

    st.markdown(
        '<div class="compliance-banner">'
        "⚠️ Maryland SNF Compliance Rule: Any CNA placed at an SNF facility must pass the "
        "Geriatric Nursing Assistant (GNA) verification filter before dispatch."
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
