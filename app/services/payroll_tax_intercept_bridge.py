"""Payroll tax intercept bridge — W-2 Tier 1 gross-to-net before Stripe instant payout.

Reads mirrored Gusto / Check HQ endpoint routes from docs/payroll, resolves Maryland
county residence for Tier 1 W-2 caregivers, computes federal + MD localized withholding,
and returns net pay for the Stripe debit-card payload.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    EMPLOYMENT_TIER_W2,
    CaregiverProfile,
    CaregiverW2EmployeeAccount,
)
from app.services.caregiver_accounts import (
    get_w2_employee_account,
    normalize_maryland_residence_county,
)

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PAYROLL_DOCS_ROOT = _REPO_ROOT / "docs" / "payroll"
_ENDPOINT_REFERENCE = _PAYROLL_DOCS_ROOT / "W2-MARYLAND-WITHHOLDING-ENDPOINTS.md"

# MD county piggyback rate applied to MD state tax liability (Comptroller/Gusto model).
_MD_COUNTY_RATE_ON_STATE_TAX: dict[str, Decimal] = {
    "ANNE ARUNDEL": Decimal("0.0281"),
    "BALTIMORE CITY": Decimal("0.0320"),
    "BALTIMORE": Decimal("0.0320"),
    "CALVERT": Decimal("0.0300"),
    "CARROLL": Decimal("0.0303"),
    "CECIL": Decimal("0.0300"),
    "CHARLES": Decimal("0.0303"),
    "FREDERICK": Decimal("0.0296"),
    "HARFORD": Decimal("0.0306"),
    "HOWARD": Decimal("0.0320"),
    "MONTGOMERY": Decimal("0.0320"),
    "PRINCE GEORGE'S": Decimal("0.0320"),
    "PRINCE GEORGES": Decimal("0.0320"),
    "QUEEN ANNE'S": Decimal("0.0320"),
    "ST. MARY'S": Decimal("0.0300"),
    "WASHINGTON": Decimal("0.0320"),
    "DEFAULT": Decimal("0.0250"),
}

_FICA_EMPLOYEE_RATE = Decimal("0.0765")


@dataclass(frozen=True)
class PayrollEndpointRoute:
    provider: str
    purpose: str
    method: str
    path: str
    doc_file: str


@dataclass(frozen=True)
class WithholdingBreakdown:
    gross_pay_amount: Decimal
    federal_fica: Decimal
    federal_income_tax: Decimal
    maryland_state_tax: Decimal
    maryland_county_tax: Decimal
    total_withholding: Decimal
    net_pay_amount: Decimal
    maryland_residence_county: str | None
    calculation_mode: str
    payroll_provider: str
    doc_reference: str
    endpoint_routes: tuple[PayrollEndpointRoute, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["endpoint_routes"] = [asdict(route) for route in self.endpoint_routes]
        for key in (
            "gross_pay_amount",
            "federal_fica",
            "federal_income_tax",
            "maryland_state_tax",
            "maryland_county_tax",
            "total_withholding",
            "net_pay_amount",
        ):
            payload[key] = float(payload[key])
        return payload


def _money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _county_key(county: str) -> str:
    normalized = (
        str(county or "")
        .upper()
        .replace(" COUNTY", "")
        .replace(".", "")
        .strip()
    )
    return normalized or "DEFAULT"


def _county_piggyback_rate(county: str) -> Decimal:
    key = _county_key(county)
    if key in _MD_COUNTY_RATE_ON_STATE_TAX:
        return _MD_COUNTY_RATE_ON_STATE_TAX[key]
    for token in key.split():
        if token in _MD_COUNTY_RATE_ON_STATE_TAX:
            return _MD_COUNTY_RATE_ON_STATE_TAX[token]
    return _MD_COUNTY_RATE_ON_STATE_TAX["DEFAULT"]


def load_payroll_endpoint_routes() -> tuple[PayrollEndpointRoute, ...]:
    """Parse W-2 withholding endpoint map from docs/payroll."""
    if not _ENDPOINT_REFERENCE.is_file():
        return ()

    text = _ENDPOINT_REFERENCE.read_text(encoding="utf-8")
    routes: list[PayrollEndpointRoute] = []
    current_provider = "unknown"
    for line in text.splitlines():
        if line.startswith("## Gusto"):
            current_provider = "gusto"
        elif line.startswith("## Check HQ"):
            current_provider = "checkhq"
        match = re.match(
            r"\|\s*([^|]+?)\s*\|\s*`(GET|PUT|POST|PATCH)`\s*\|\s*`([^`]+)`\s*\|\s*[^|]*\|\s*`([^`]+)`\s*\|",
            line,
        )
        if not match:
            match = re.match(
                r"\|\s*([^|]+?)\s*\|\s*`(GET|PUT|POST|PATCH)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|",
                line,
            )
        if not match:
            continue
        purpose, method, path, doc_file = match.groups()
        routes.append(
            PayrollEndpointRoute(
                provider=current_provider,
                purpose=purpose.strip(),
                method=method.strip(),
                path=path.strip(),
                doc_file=doc_file.strip(),
            )
        )
    return tuple(routes)


def _resolve_payroll_provider() -> str:
    configured = str(settings.PAYROLL_TAX_PROVIDER or "").strip().lower()
    if configured in {"gusto", "checkhq", "local"}:
        return configured
    if str(settings.CHECKHQ_API_KEY or "").strip():
        return "checkhq"
    if str(settings.GUSTO_API_TOKEN or "").strip():
        return "gusto"
    return "local"


def _route_for(routes: tuple[PayrollEndpointRoute, ...], provider: str, needle: str) -> PayrollEndpointRoute | None:
    for route in routes:
        if route.provider != provider:
            continue
        if needle.lower() in route.purpose.lower() or needle.lower() in route.path.lower():
            return route
    return None


def get_tier1_w2_context(
    db: Session | None,
    *,
    provider_id: UUID | str | None,
    maryland_residence_county: str | None = None,
) -> dict[str, Any] | None:
    """Resolve Tier 1 W-2 caregiver tax context from DB or explicit county override."""
    if maryland_residence_county:
        county = normalize_maryland_residence_county(maryland_residence_county)
        return {
            "employment_tier": EMPLOYMENT_TIER_W2,
            "maryland_residence_county": county,
            "provider_id": str(provider_id) if provider_id else None,
            "source": "payload_override",
        }

    if db is None or not provider_id:
        return None

    try:
        provider_uuid = UUID(str(provider_id))
    except ValueError:
        return None

    profile = (
        db.query(CaregiverProfile)
        .filter(CaregiverProfile.provider_id == provider_uuid)
        .filter(CaregiverProfile.employment_tier == EMPLOYMENT_TIER_W2)
        .first()
    )
    if profile is None:
        return None

    w2 = get_w2_employee_account(db, profile.caregiver_profile_id)
    if w2 is None:
        return None

    return {
        "employment_tier": EMPLOYMENT_TIER_W2,
        "caregiver_profile_id": str(profile.caregiver_profile_id),
        "maryland_residence_county": w2.maryland_residence_county,
        "local_tax_jurisdiction_code": w2.local_tax_jurisdiction_code,
        "provider_id": str(provider_uuid),
        "source": "caregiver_w2_employee_accounts",
    }


def _doc_guided_withholding(
    gross: Decimal,
    *,
    maryland_residence_county: str,
    payroll_provider: str,
    routes: tuple[PayrollEndpointRoute, ...],
) -> WithholdingBreakdown:
    """Localized estimate aligned with docs/payroll MD county + federal W-2 model."""
    federal_fica = _money(gross * _FICA_EMPLOYEE_RATE)
    federal_income = _money(gross * Decimal(str(settings.INSTANT_PAY_FEDERAL_INCOME_EFFECTIVE_RATE)))
    md_state = _money(gross * Decimal(str(settings.INSTANT_PAY_MD_STATE_EFFECTIVE_RATE)))
    county_rate = _county_piggyback_rate(maryland_residence_county)
    md_county = _money(md_state * county_rate)
    total = _money(federal_fica + federal_income + md_state + md_county)
    net = _money(gross - total)
    if net < Decimal("0.01"):
        net = Decimal("0.01")

    calc_route = _route_for(routes, payroll_provider, "calculate") or _route_for(
        routes, payroll_provider, "preview"
    )
    doc_ref = calc_route.doc_file if calc_route else "W2-MARYLAND-WITHHOLDING-ENDPOINTS.md"

    return WithholdingBreakdown(
        gross_pay_amount=gross,
        federal_fica=federal_fica,
        federal_income_tax=federal_income,
        maryland_state_tax=md_state,
        maryland_county_tax=md_county,
        total_withholding=total,
        net_pay_amount=net,
        maryland_residence_county=maryland_residence_county,
        calculation_mode="doc_guided_localized",
        payroll_provider=payroll_provider,
        doc_reference=doc_ref,
        endpoint_routes=routes,
    )


def _fetch_checkhq_withholding(
    gross: Decimal,
    *,
    employee_external_id: str,
    maryland_residence_county: str,
    routes: tuple[PayrollEndpointRoute, ...],
) -> WithholdingBreakdown | None:
    api_key = str(settings.CHECKHQ_API_KEY or "").strip()
    if not api_key:
        return None

    base = str(settings.CHECKHQ_API_BASE or "https://sandbox.checkhq.com").rstrip("/")
    list_route = _route_for(routes, "checkhq", "List employee tax parameters")
    path = (list_route.path if list_route else "/employee_tax_params/{employee_id}").format(
        employee_id=employee_external_id
    )
    url = f"{base}{path}?jurisdiction=md"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
        if response.status_code >= 400:
            logger.warning("Check HQ tax params fetch failed status=%s", response.status_code)
            return None
        body = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Check HQ tax params fetch error: %s", exc)
        return None

    # Check returns setup params, not computed shift tax — combine with doc-guided math.
    breakdown = _doc_guided_withholding(
        gross,
        maryland_residence_county=maryland_residence_county,
        payroll_provider="checkhq",
        routes=routes,
    )
    return WithholdingBreakdown(
        gross_pay_amount=breakdown.gross_pay_amount,
        federal_fica=breakdown.federal_fica,
        federal_income_tax=breakdown.federal_income_tax,
        maryland_state_tax=breakdown.maryland_state_tax,
        maryland_county_tax=breakdown.maryland_county_tax,
        total_withholding=breakdown.total_withholding,
        net_pay_amount=breakdown.net_pay_amount,
        maryland_residence_county=breakdown.maryland_residence_county,
        calculation_mode="checkhq_api_params_plus_doc_guided",
        payroll_provider="checkhq",
        doc_reference=(list_route.doc_file if list_route else "checkhq/checkhq-list-employee-tax-parameters.md"),
        endpoint_routes=routes,
    )


def _fetch_gusto_withholding(
    gross: Decimal,
    *,
    employee_uuid: str,
    maryland_residence_county: str,
    routes: tuple[PayrollEndpointRoute, ...],
) -> WithholdingBreakdown | None:
    token = str(settings.GUSTO_API_TOKEN or "").strip()
    company_id = str(settings.GUSTO_COMPANY_ID or "").strip()
    if not token or not company_id:
        return None

    base = str(settings.GUSTO_API_BASE or "https://api.gusto-demo.com").rstrip("/")
    federal_route = _route_for(routes, "gusto", "federal")
    state_route = _route_for(routes, "gusto", "state")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "X-Gusto-API-Version": str(settings.GUSTO_API_VERSION or "2024-04-01"),
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            federal_resp = client.get(
                f"{base}/v1/employees/{employee_uuid}/federal_taxes",
                headers=headers,
            )
            state_resp = client.get(
                f"{base}/v1/employees/{employee_uuid}/state_taxes",
                headers=headers,
            )
        if federal_resp.status_code >= 400 or state_resp.status_code >= 400:
            logger.warning(
                "Gusto tax fetch failed federal=%s state=%s",
                federal_resp.status_code,
                state_resp.status_code,
            )
            return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gusto tax fetch error: %s", exc)
        return None

    breakdown = _doc_guided_withholding(
        gross,
        maryland_residence_county=maryland_residence_county,
        payroll_provider="gusto",
        routes=routes,
    )
    federal_doc = federal_route.doc_file if federal_route else "gusto/gusto-get-employee-federal-taxes.md"
    state_doc = state_route.doc_file if state_route else "gusto/gusto-get-employee-state-taxes.md"
    return WithholdingBreakdown(
        gross_pay_amount=breakdown.gross_pay_amount,
        federal_fica=breakdown.federal_fica,
        federal_income_tax=breakdown.federal_income_tax,
        maryland_state_tax=breakdown.maryland_state_tax,
        maryland_county_tax=breakdown.maryland_county_tax,
        total_withholding=breakdown.total_withholding,
        net_pay_amount=breakdown.net_pay_amount,
        maryland_residence_county=breakdown.maryland_residence_county,
        calculation_mode="gusto_api_w4_plus_doc_guided_md_county",
        payroll_provider="gusto",
        doc_reference=f"{federal_doc}; {state_doc}",
        endpoint_routes=routes,
    )


def calculate_tier1_w2_withholding(
    gross_pay_amount: Decimal | float,
    *,
    db: Session | None = None,
    provider_id: UUID | str | None = None,
    maryland_residence_county: str | None = None,
    employee_external_id: str | None = None,
) -> WithholdingBreakdown | None:
    """Compute W-2 Tier 1 withholding; returns None when worker is not Tier 1 W-2."""
    if not settings.PAYROLL_TAX_INTERCEPT_ENABLED:
        return None

    gross = _money(gross_pay_amount)
    if gross <= 0:
        raise ValueError("gross_pay_amount_must_be_positive")

    tier1 = get_tier1_w2_context(
        db,
        provider_id=provider_id,
        maryland_residence_county=maryland_residence_county,
    )
    if tier1 is None:
        return None

    county = str(tier1["maryland_residence_county"])
    routes = load_payroll_endpoint_routes()
    payroll_provider = _resolve_payroll_provider()

    if payroll_provider == "checkhq":
        external_id = employee_external_id or str(provider_id or "")
        live = _fetch_checkhq_withholding(
            gross,
            employee_external_id=external_id,
            maryland_residence_county=county,
            routes=routes,
        )
        if live is not None:
            return live
    elif payroll_provider == "gusto":
        employee_uuid = employee_external_id or str(provider_id or "")
        live = _fetch_gusto_withholding(
            gross,
            employee_uuid=employee_uuid,
            maryland_residence_county=county,
            routes=routes,
        )
        if live is not None:
            return live

    return _doc_guided_withholding(
        gross,
        maryland_residence_county=county,
        payroll_provider=payroll_provider,
        routes=routes,
    )


def apply_instant_payout_tax_intercept(
    gross_pay_amount: Decimal | float,
    *,
    db: Session | None = None,
    provider_id: UUID | str | None = None,
    maryland_residence_county: str | None = None,
    employee_external_id: str | None = None,
) -> tuple[Decimal, WithholdingBreakdown | None]:
    """Return (net_pay_for_stripe, breakdown). Non-W-2 workers pass gross through unchanged."""
    breakdown = calculate_tier1_w2_withholding(
        gross_pay_amount,
        db=db,
        provider_id=provider_id,
        maryland_residence_county=maryland_residence_county,
        employee_external_id=employee_external_id,
    )
    if breakdown is None:
        return _money(gross_pay_amount), None
    return breakdown.net_pay_amount, breakdown


def build_stripe_instant_payout_payload(
    *,
    gross_pay_amount: Decimal | float,
    provider_id: UUID | str,
    db: Session | None = None,
    maryland_residence_county: str | None = None,
    employee_external_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Stripe instant payout payload with net pay after tax intercept."""
    net_pay, breakdown = apply_instant_payout_tax_intercept(
        gross_pay_amount,
        db=db,
        provider_id=provider_id,
        maryland_residence_county=maryland_residence_county,
        employee_external_id=employee_external_id,
    )
    payload: dict[str, Any] = {
        "provider_id": str(provider_id),
        "gross_pay_amount": float(_money(gross_pay_amount)),
        "net_pay_amount": float(net_pay),
        "amount_cents": int(net_pay * 100),
        "currency": "usd",
        "method": "instant",
    }
    if breakdown is not None:
        payload["tax_withholding"] = breakdown.to_dict()
    if extra:
        payload.update(extra)
    return payload
