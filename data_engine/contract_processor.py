"""Facility MSA / staffing agreement parser — deterministic regex + optional PDF/DOCX."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import FacilityContract, MarylandFacility

MD_STAFFING_ROLES = ("LPN", "CNA", "GNA")

ROLE_BILL_RATE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "LPN": (
        re.compile(r"LPN\s+bill(?:ing)?\s+rate[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),
        re.compile(r"Licensed Practical Nurse[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),
    ),
    "CNA": (
        re.compile(r"CNA\s+bill(?:ing)?\s+rate[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),
        re.compile(r"Certified Nursing Assistant[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),
    ),
    "GNA": (
        re.compile(r"GNA\s+bill(?:ing)?\s+rate[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),
        re.compile(r"Geriatric Nursing Assistant[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),
    ),
}
ROLE_PAY_RATE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "LPN": (re.compile(r"LPN\s+pay(?:\s+rate)?[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),),
    "CNA": (re.compile(r"CNA\s+pay(?:\s+rate)?[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),),
    "GNA": (re.compile(r"GNA\s+pay(?:\s+rate)?[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),),
}

BILL_RATE_PATTERNS = (
    re.compile(r"bill(?:ing)?\s+rate[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),
    re.compile(r"client\s+rate[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),
)
PAY_RATE_PATTERNS = (
    re.compile(r"pay(?:\s+rate)?[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),
    re.compile(r"clinician\s+rate[^\d$]*\$?\s*(\d+(?:\.\d{1,2})?)", re.I),
)
CANCEL_HOURS_PATTERN = re.compile(
    r"(?:notify|cancellation|cancel(?:lation)?)[^\d]{0,40}(\d+)\s*hours?\s*(?:prior|before|notice)",
    re.I,
)
CREDENTIAL_PATTERNS = {
    "BLS": re.compile(r"\bBLS\b|\bCPR\b|\bBasic Life Support\b", re.I),
    "ACLS": re.compile(r"\bACLS\b|\bAdvanced Cardiac Life Support\b", re.I),
    "PALS": re.compile(r"\bPALS\b", re.I),
    "ICU_YEARS": re.compile(r"(\d+)\s*(?:\+?\s*)?years?\s*(?:of\s*)?(?:ICU|critical care)", re.I),
}


@dataclass
class ContractExtraction:
    facility_name: str | None = None
    bill_rate_hourly: float | None = None
    pay_rate_hourly: float | None = None
    margin_dollars: float | None = None
    margin_pct: float | None = None
    cancellation_policy_text: str | None = None
    cancellation_notice_hours: int | None = None
    credential_requirements: dict[str, Any] = field(default_factory=dict)
    review_status: str = "ACTIVE"
    dispatch_halted: bool = False
    review_reason: str | None = None
    staffing_role: str | None = None
    md_regional_bill_floor: float | None = None
    source_filename: str = ""
    raw_text_excerpt: str = ""


def _read_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Install pypdf to parse PDF contracts: pip install pypdf") from exc
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if suffix in {".docx", ".doc"}:
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("Install python-docx to parse DOCX contracts: pip install python-docx") from exc
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)

    raise ValueError(f"Unsupported contract file type: {suffix}")


def _first_rate(patterns: tuple[re.Pattern[str], ...], text: str) -> float | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            try:
                return float(match.group(1))
            except (TypeError, ValueError, InvalidOperation):
                continue
    return None


def _detect_staffing_role(text: str) -> str | None:
    upper = text.upper()
    for role in ("GNA", "CNA", "LPN"):
        if role in upper:
            return role
    return None


def _md_bill_floor(role: str | None) -> float | None:
    if role == "LPN":
        return float(settings.MD_LPN_MIN_BILL_RATE)
    if role == "CNA":
        return float(settings.MD_CNA_MIN_BILL_RATE)
    if role == "GNA":
        return float(settings.MD_GNA_MIN_BILL_RATE)
    return None


def _md_min_margin_pct(role: str | None) -> float:
    if role == "LPN":
        return float(settings.MD_LPN_MIN_MARGIN_PCT)
    if role in {"CNA", "GNA"}:
        return float(settings.MD_CNA_MIN_MARGIN_PCT if role == "CNA" else settings.MD_GNA_MIN_MARGIN_PCT)
    return float(settings.CONTRACT_MIN_MARGIN_PCT)


def extract_contract_terms(text: str, *, source_filename: str = "") -> ContractExtraction:
    cleaned = re.sub(r"\s+", " ", text).strip()
    extraction = ContractExtraction(
        source_filename=source_filename,
        raw_text_excerpt=cleaned[:4000],
    )

    facility_match = re.search(
        r"(?:facility|client|hospital|nursing home|skilled nursing|assisted living|home health)"
        r"\s*(?:name)?\s*[:\-]\s*([A-Za-z0-9&\-\.,' ]{4,120})",
        cleaned,
        re.I,
    )
    if facility_match:
        extraction.facility_name = facility_match.group(1).strip(" .,")

    extraction.staffing_role = _detect_staffing_role(cleaned)
    role = extraction.staffing_role

    role_bill = _first_rate(ROLE_BILL_RATE_PATTERNS.get(role or "", ()), cleaned) if role else None
    role_pay = _first_rate(ROLE_PAY_RATE_PATTERNS.get(role or "", ()), cleaned) if role else None
    extraction.bill_rate_hourly = role_bill or _first_rate(BILL_RATE_PATTERNS, cleaned)
    extraction.pay_rate_hourly = role_pay or _first_rate(PAY_RATE_PATTERNS, cleaned)
    extraction.md_regional_bill_floor = _md_bill_floor(role)

    cancel_match = CANCEL_HOURS_PATTERN.search(cleaned)
    if cancel_match:
        extraction.cancellation_notice_hours = int(cancel_match.group(1))
        extraction.cancellation_policy_text = cancel_match.group(0)[:500]

    creds: dict[str, Any] = {}
    for key, pattern in CREDENTIAL_PATTERNS.items():
        hit = pattern.search(cleaned)
        if not hit:
            continue
        creds[key] = int(hit.group(1)) if key == "ICU_YEARS" and hit.groups() else True
    extraction.credential_requirements = creds

    bill = extraction.bill_rate_hourly
    pay = extraction.pay_rate_hourly
    if bill is not None and pay is not None and bill > 0:
        extraction.margin_dollars = round(bill - pay, 2)
        extraction.margin_pct = round((bill - pay) / bill, 4)

    _apply_margin_safety(extraction)
    return extraction


def _apply_margin_safety(extraction: ContractExtraction) -> None:
    """Halt dispatch when bill rate fails Maryland regional margin guardrails."""
    role = extraction.staffing_role
    min_margin_pct = _md_min_margin_pct(role)
    baseline_pay = float(settings.CONTRACT_BASELINE_MIN_PAY_RATE)
    bill_floor = extraction.md_regional_bill_floor

    bill = extraction.bill_rate_hourly
    pay = extraction.pay_rate_hourly

    if bill is None or pay is None:
        extraction.review_status = "PENDING_EXECUTIVE_REVIEW"
        extraction.dispatch_halted = True
        extraction.review_reason = "Missing bill or pay rate — manual review required"
        return

    if bill_floor is not None and bill < bill_floor:
        extraction.review_status = "REVIEW_MARGINS"
        extraction.dispatch_halted = True
        extraction.review_reason = (
            f"{role or 'Staff'} bill rate ${bill:.2f}/hr below Maryland regional floor "
            f"${bill_floor:.2f}/hr"
        )
        return

    if bill < baseline_pay:
        extraction.review_status = "REVIEW_MARGINS"
        extraction.dispatch_halted = True
        extraction.review_reason = (
            f"Bill rate ${bill:.2f}/hr below baseline minimum pay ${baseline_pay:.2f}/hr"
        )
        return

    if pay >= bill:
        extraction.review_status = "REVIEW_MARGINS"
        extraction.dispatch_halted = True
        extraction.review_reason = "Pay rate meets or exceeds bill rate — negative margin"
        return

    margin_pct = (bill - pay) / bill if bill > 0 else 0.0
    extraction.margin_dollars = round(bill - pay, 2)
    extraction.margin_pct = round(margin_pct, 4)

    if margin_pct < min_margin_pct:
        extraction.review_status = "REVIEW_MARGINS"
        extraction.dispatch_halted = True
        extraction.review_reason = (
            f"Margin {margin_pct * 100:.1f}% below Maryland {role or 'contract'} minimum "
            f"{min_margin_pct * 100:.1f}%"
        )
        return

    extraction.review_status = "ACTIVE"
    extraction.dispatch_halted = False
    extraction.review_reason = None


def parse_contract_file(path: Path) -> ContractExtraction:
    text = _read_document_text(path)
    return extract_contract_terms(text, source_filename=path.name)


def resolve_facility_id(db: Session, extraction: ContractExtraction) -> uuid.UUID | None:
    if not extraction.facility_name:
        return None
    from app.models import MarylandFacility
    from app.services.job_board_crisis_scraper import match_facility_name

    candidates = db.query(MarylandFacility).all()
    matched = match_facility_name(extraction.facility_name, candidates)
    if matched is None:
        return None
    return matched.facility_id


def save_contract_extraction(
    db: Session,
    *,
    facility_id: uuid.UUID,
    extraction: ContractExtraction,
    vms_source: str = "MSA_UPLOAD",
    external_contract_id: str | None = None,
) -> FacilityContract:
    ext_id = external_contract_id or f"msa:{extraction.source_filename}"
    existing = (
        db.query(FacilityContract)
        .filter(
            FacilityContract.facility_id == facility_id,
            FacilityContract.external_contract_id == ext_id,
        )
        .first()
    )
    if existing:
        row = existing
    else:
        row = FacilityContract(
            contract_id=uuid.uuid4(),
            facility_id=facility_id,
            external_contract_id=ext_id,
        )
        db.add(row)

    row.vms_source = vms_source
    row.contract_name = extraction.facility_name or extraction.source_filename
    row.source_filename = extraction.source_filename
    row.bill_rate_hourly = _decimal_or_none(extraction.bill_rate_hourly)
    row.pay_rate_hourly = _decimal_or_none(extraction.pay_rate_hourly)
    row.margin_dollars = _decimal_or_none(extraction.margin_dollars)
    row.margin_pct = _decimal_or_none(extraction.margin_pct)
    row.cancellation_policy_text = extraction.cancellation_policy_text
    row.cancellation_notice_hours = extraction.cancellation_notice_hours
    row.credential_requirements_json = json.dumps(extraction.credential_requirements)
    row.review_status = extraction.review_status
    row.dispatch_halted = "true" if extraction.dispatch_halted else "false"
    row.review_reason = extraction.review_reason
    row.staffing_role = extraction.staffing_role
    row.md_regional_bill_floor = _decimal_or_none(extraction.md_regional_bill_floor)
    row.raw_text_excerpt = extraction.raw_text_excerpt
    row.parsed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def _decimal_or_none(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(float(value), 2)))


def process_incoming_contract(
    db: Session,
    path: Path,
    *,
    facility_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    extraction = parse_contract_file(path)
    resolved_facility_id = facility_id or resolve_facility_id(db, extraction)
    if resolved_facility_id is None:
        return {
            "ok": False,
            "error": "facility_not_matched",
            "extraction": asdict(extraction),
            "source": str(path),
        }

    row = save_contract_extraction(db, facility_id=resolved_facility_id, extraction=extraction)
    return {
        "ok": True,
        "contract_id": str(row.contract_id),
        "facility_id": str(row.facility_id),
        "review_status": row.review_status,
        "dispatch_halted": row.dispatch_halted == "true",
        "extraction": asdict(extraction),
    }


def process_incoming_contracts_dir(db: Session) -> list[dict[str, Any]]:
    from data_engine.paths import INCOMING_CONTRACTS_DIR, PROCESSED_DIR, ensure_data_engine_dirs

    ensure_data_engine_dirs()
    results: list[dict[str, Any]] = []
    for path in sorted(INCOMING_CONTRACTS_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".pdf", ".docx", ".doc", ".txt", ".md"}:
            continue
        results.append(process_incoming_contract(db, path))
        dest = PROCESSED_DIR / "contracts" / path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        path.replace(dest)
    return results
