"""Maryland HB 1106 algorithmic bias auditor — objective match metrics + Claude certification log."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandFacility, MarylandProvider, MdMarketFacility, MdProviderLicensure

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_LOG = REPO_ROOT / "maryland_hb1106_audit.log"
STATUTE = "Maryland HB 1106"
PROMPT_MATRIX_VERSION = "hb1106-objective-v1"
CLAUDE_MODEL_DEFAULT = "claude-3-5-sonnet-20241022"

SYSTEM_PROMPT = (
    "You are an Maryland HB 1106 automated hiring compliance auditor. "
    "Evaluate ONLY the four objective matching metrics provided. "
    "Do not infer or request demographic attributes. "
    "Certify whether the match decision could have been influenced by illegal demographic bias. "
    "Respond with strict JSON only."
)


@dataclass(frozen=True)
class ObjectiveMatchMetrics:
    mbon_license_status: str
    geographic_distance_miles: float | None
    historical_facility_rating: str
    clinical_skills: list[str]


@dataclass
class BiasAuditCertification:
    audit_id: str
    certified_at_utc: str
    statute: str
    provider_id: str
    offer_id: str
    facility_id: str
    objective_metrics: dict[str, Any]
    claude_model: str
    prompt_matrix_version: str
    zero_illegal_demographic_bias: bool
    certification_statement: str
    reasoning_summary: str
    previous_entry_hash: str
    entry_hash: str
    engine_mode: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _audit_log_path() -> Path:
    configured = str(getattr(settings, "BIAS_AUDITOR_LOG_PATH", "") or "").strip()
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else REPO_ROOT / path
    return DEFAULT_AUDIT_LOG


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius_miles * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _provider_coords(provider: MarylandProvider) -> tuple[float, float] | None:
    if provider.latitude is None or provider.longitude is None:
        return None
    return float(provider.latitude), float(provider.longitude)


def _resolve_mbon_status(db: Session, provider: MarylandProvider) -> str:
    licensure = (
        db.query(MdProviderLicensure)
        .filter(MdProviderLicensure.provider_id == provider.provider_id)
        .one_or_none()
    )
    if licensure and licensure.mbon_last_status:
        return str(licensure.mbon_last_status).upper()
    return str(provider.license_status or "UNVERIFIED").upper()


def _resolve_facility_rating(db: Session, shift_row: dict) -> str:
    facility_id = str(shift_row.get("facility_id") or "").strip()
    if facility_id:
        market = (
            db.query(MdMarketFacility)
            .filter(MdMarketFacility.maryland_facility_id == facility_id)
            .one_or_none()
        )
        if market and market.md_license_status:
            return f"md_license_status:{str(market.md_license_status).upper()}"
    return str(shift_row.get("historical_facility_rating") or shift_row.get("staffing_rating") or "not_available")


def _resolve_clinical_skills(provider: MarylandProvider, shift_row: dict) -> list[str]:
    skills: list[str] = [
        str(provider.credential_type or "").upper(),
        f"service_lines:{str(provider.service_lines or 'ALL')}",
        f"shift_role:{str(shift_row.get('shift_role') or 'UNKNOWN')}",
    ]
    tags = shift_row.get("care_tags") or shift_row.get("specialty_tags") or []
    if isinstance(tags, str):
        tags = [token.strip() for token in tags.split(",") if token.strip()]
    for tag in tags:
        token = str(tag).strip()
        if token:
            skills.append(token)
    return skills


def _resolve_distance_miles(
    db: Session,
    provider: MarylandProvider,
    shift_row: dict,
) -> float | None:
    provider_coords = _provider_coords(provider)
    if not provider_coords:
        return None
    facility_id = str(shift_row.get("facility_id") or "").strip()
    if not facility_id:
        return None
    facility = db.query(MarylandFacility).filter(MarylandFacility.facility_id == facility_id).first()
    if facility is None or facility.latitude is None or facility.longitude is None:
        return None
    return round(
        _haversine_miles(
            provider_coords[0],
            provider_coords[1],
            float(facility.latitude),
            float(facility.longitude),
        ),
        2,
    )


def collect_objective_match_metrics(
    db: Session,
    *,
    provider: MarylandProvider,
    shift_row: dict,
) -> ObjectiveMatchMetrics:
    return ObjectiveMatchMetrics(
        mbon_license_status=_resolve_mbon_status(db, provider),
        geographic_distance_miles=_resolve_distance_miles(db, provider, shift_row),
        historical_facility_rating=_resolve_facility_rating(db, shift_row),
        clinical_skills=_resolve_clinical_skills(provider, shift_row),
    )


def build_claude_prompt_matrix(metrics: ObjectiveMatchMetrics) -> dict[str, Any]:
    """Structured prompt matrix — four objective dimensions only."""
    return {
        "matrix_version": PROMPT_MATRIX_VERSION,
        "statute": STATUTE,
        "dimensions": [
            {
                "id": "mbon_license_status",
                "label": "MBON license status",
                "value": metrics.mbon_license_status,
                "bias_relevance": "Credential validity only — not demographic.",
            },
            {
                "id": "geographic_distance_miles",
                "label": "Geographic distance",
                "value": metrics.geographic_distance_miles,
                "bias_relevance": "Proximity to shift — not residence ethnicity or neighborhood proxy beyond miles.",
            },
            {
                "id": "historical_facility_rating",
                "label": "Historical facility rating",
                "value": metrics.historical_facility_rating,
                "bias_relevance": "Facility compliance/quality signal — not caregiver demographics.",
            },
            {
                "id": "clinical_skills",
                "label": "Specific clinical skills",
                "value": metrics.clinical_skills,
                "bias_relevance": "Role qualification tags only.",
            },
        ],
        "instructions": (
            "Return JSON with keys: zero_illegal_demographic_bias (boolean), "
            "certification_statement (string), reasoning_summary (string). "
            "Certify true only if match rationale is limited to these objective metrics."
        ),
    }


def _deterministic_certification(metrics: ObjectiveMatchMetrics) -> dict[str, Any]:
    allowed_mbon = metrics.mbon_license_status in {"VERIFIED", "ACTIVE", "STUB_PASS", "CLEAR"}
    return {
        "zero_illegal_demographic_bias": allowed_mbon,
        "certification_statement": (
            "Certified: match evaluated solely on MBON license status, geographic distance, "
            "historical facility rating, and clinical skills — zero illegal demographic bias detected."
            if allowed_mbon
            else "Hold: MBON license status requires review before HB 1106 bias-free certification."
        ),
        "reasoning_summary": (
            f"Objective-only review — MBON={metrics.mbon_license_status}, "
            f"distance={metrics.geographic_distance_miles}, "
            f"facility_rating={metrics.historical_facility_rating}, "
            f"skills={len(metrics.clinical_skills)} tags."
        ),
    }


def _invoke_claude_sonnet_prompt_matrix(prompt_matrix: dict[str, Any]) -> dict[str, Any]:
    api_key = str(getattr(settings, "BIAS_AUDITOR_ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("bias_auditor_anthropic_api_key_missing")

    model = str(getattr(settings, "BIAS_AUDITOR_LLM_MODEL", "") or CLAUDE_MODEL_DEFAULT)
    timeout = float(getattr(settings, "BIAS_AUDITOR_LLM_TIMEOUT_SECONDS", 30.0))
    user_payload = json.dumps(prompt_matrix, separators=(",", ":"))

    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 512,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_payload}],
            },
        )
        response.raise_for_status()
        payload = response.json()

    text_blocks = payload.get("content") or []
    raw_text = ""
    for block in text_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            raw_text += str(block.get("text") or "")
    raw_text = raw_text.strip()
    if not raw_text:
        raise RuntimeError("bias_auditor_empty_claude_response")
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw_text[start : end + 1])
        raise


def _read_previous_entry_hash(path: Path) -> str:
    if not path.exists():
        return "GENESIS"
    last_line = ""
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            token = line.strip()
            if token:
                last_line = token
    if not last_line:
        return "GENESIS"
    try:
        prior = json.loads(last_line)
        return str(prior.get("entry_hash") or "GENESIS")
    except json.JSONDecodeError:
        return hashlib.sha256(last_line.encode("utf-8")).hexdigest()


def _compute_entry_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_hb1106_audit_record(certification: BiasAuditCertification) -> Path:
    """Append-only write to maryland_hb1106_audit.log (hash-chained, unalterable chain)."""
    path = _audit_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = asdict(certification)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    logger.info("HB1106 bias audit appended audit_id=%s path=%s", certification.audit_id, path)
    return path


def intercept_caregiver_shift_match(
    db: Session,
    *,
    provider: MarylandProvider,
    shift_row: dict,
) -> BiasAuditCertification:
    """Run on every caregiver↔shift match — objective metrics → Claude matrix → audit log."""
    if not getattr(settings, "BIAS_AUDITOR_ENABLED", True):
        raise RuntimeError("bias_auditor_disabled")

    metrics = collect_objective_match_metrics(db, provider=provider, shift_row=shift_row)
    prompt_matrix = build_claude_prompt_matrix(metrics)
    dry_run = bool(getattr(settings, "BIAS_AUDITOR_DRY_RUN", True))

    if dry_run:
        claude_result = _deterministic_certification(metrics)
        engine_mode = "deterministic_dry_run"
        model = str(getattr(settings, "BIAS_AUDITOR_LLM_MODEL", "") or CLAUDE_MODEL_DEFAULT)
    else:
        claude_result = _invoke_claude_sonnet_prompt_matrix(prompt_matrix)
        engine_mode = "claude_3_5_sonnet_live"
        model = str(getattr(settings, "BIAS_AUDITOR_LLM_MODEL", "") or CLAUDE_MODEL_DEFAULT)

    previous_hash = _read_previous_entry_hash(_audit_log_path())
    audit_id = str(uuid.uuid4())
    certified_at = _utc_now_iso()
    body_without_hash = {
        "audit_id": audit_id,
        "certified_at_utc": certified_at,
        "statute": STATUTE,
        "provider_id": str(provider.provider_id),
        "offer_id": str(shift_row.get("offer_id") or ""),
        "facility_id": str(shift_row.get("facility_id") or ""),
        "objective_metrics": asdict(metrics),
        "prompt_matrix_version": PROMPT_MATRIX_VERSION,
        "claude_model": model,
        "zero_illegal_demographic_bias": bool(claude_result.get("zero_illegal_demographic_bias")),
        "certification_statement": str(claude_result.get("certification_statement") or ""),
        "reasoning_summary": str(claude_result.get("reasoning_summary") or ""),
        "previous_entry_hash": previous_hash,
        "engine_mode": engine_mode,
    }
    entry_hash = _compute_entry_hash(body_without_hash)
    certification = BiasAuditCertification(
        audit_id=audit_id,
        certified_at_utc=certified_at,
        statute=STATUTE,
        provider_id=str(provider.provider_id),
        offer_id=str(shift_row.get("offer_id") or ""),
        facility_id=str(shift_row.get("facility_id") or ""),
        objective_metrics=asdict(metrics),
        claude_model=model,
        prompt_matrix_version=PROMPT_MATRIX_VERSION,
        zero_illegal_demographic_bias=bool(claude_result.get("zero_illegal_demographic_bias")),
        certification_statement=str(claude_result.get("certification_statement") or ""),
        reasoning_summary=str(claude_result.get("reasoning_summary") or ""),
        previous_entry_hash=previous_hash,
        entry_hash=entry_hash,
        engine_mode=engine_mode,
    )
    append_hb1106_audit_record(certification)
    return certification
