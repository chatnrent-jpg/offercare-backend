"""Semantic vector match + Stripe instant payout gateway — isolated strategy engine (terminal-testable)."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EMBEDDING_DIM = 1536
_TOP_K = 5
_INSTANT_PAY_WINDOW_MINUTES = 30

logger = logging.getLogger(__name__)

# Montgomery SNF CNA slice — three compliant provider profiles for mock pgvector search.
_MOCK_COMPLIANT_PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "provider_id": "CNA-MD-88421",
        "full_name": "Aisha Thompson",
        "role": "CNA",
        "county": "Montgomery",
        "has_gna_endorsement": True,
        "compliant": True,
        "profile_text": (
            "CNA GNA Montgomery SNF skilled nursing verified compliant "
            "day shift med-surg floor stable patients"
        ),
    },
    {
        "provider_id": "CNA-MD-99001",
        "full_name": "Nia Patterson",
        "role": "CNA",
        "county": "Montgomery",
        "has_gna_endorsement": True,
        "compliant": True,
        "profile_text": (
            "CNA GNA Montgomery SNF dementia care memory unit night shift "
            "Baltimore corridor behavioral support verified compliant"
        ),
    },
    {
        "provider_id": "CNA-MD-99002",
        "full_name": "Jordan Ellis",
        "role": "CNA",
        "county": "Montgomery",
        "has_gna_endorsement": True,
        "compliant": True,
        "profile_text": (
            "CNA GNA Montgomery SNF rehabilitation post-acute evening shift "
            "ADL support verified compliant"
        ),
    },
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_dotenv() -> None:
    env_path = _REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        token = line.strip()
        if not token or token.startswith("#") or "=" not in token:
            continue
        key, value = token.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _import_sentinel_validation() -> tuple[Any, Any]:
    try:
        from app.schemas.sentinel_validation import (  # type: ignore[import-not-found]
            SentinelValidationSuite,
            format_sentinel_validation_error,
        )

        return SentinelValidationSuite, format_sentinel_validation_error
    except ImportError:
        import importlib.util

        module_path = _REPO_ROOT / "app" / "schemas" / "sentinel_validation.py"
        spec = importlib.util.spec_from_file_location("sentinel_validation", module_path)
        if spec is None or spec.loader is None:
            raise ImportError("sentinel_validation module unavailable") from None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.SentinelValidationSuite, module.format_sentinel_validation_error


def _geo_keys_in_context(context: dict[str, Any]) -> bool:
    geo_keys = {
        "latitude",
        "lat",
        "longitude",
        "lng",
        "lon",
        "search_radius_miles",
        "radius_miles",
        "search_radius",
    }
    return any(key in context for key in geo_keys)


def _extract_facility_geo_payload(context: dict[str, Any]) -> dict[str, float]:
    latitude = context.get("latitude", context.get("lat"))
    longitude = context.get("longitude", context.get("lng", context.get("lon")))
    search_radius_miles = context.get(
        "search_radius_miles",
        context.get("radius_miles", context.get("search_radius")),
    )
    missing = [
        name
        for name, value in (
            ("latitude", latitude),
            ("longitude", longitude),
            ("search_radius_miles", search_radius_miles),
        )
        if value is None
    ]
    if missing:
        block = {
            "ok": False,
            "sentinel": "VALIDATION_BLOCK",
            "error_count": len(missing),
            "errors": [
                {
                    "field": field,
                    "message": f"{field} is required when facility geo search parameters are supplied",
                    "type": "sentinel.geo.missing",
                }
                for field in missing
            ],
        }
        raise ValueError(f"SENTINEL_BLOCK:{json.dumps(block)}")
    return {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "search_radius_miles": float(search_radius_miles),
    }


def _sentinel_validate_facility_geo(shift_context: dict[str, Any] | None) -> None:
    """Intercept malformed facility geo queries before pgvector / DB scan."""
    context = dict(shift_context or {})
    if not _geo_keys_in_context(context):
        return

    from pydantic import ValidationError

    suite_cls, format_error = _import_sentinel_validation()
    geo_payload = _extract_facility_geo_payload(context)
    try:
        suite_cls.validate_facility_geo_input(geo_payload)
    except ValidationError as exc:
        block = format_error(exc)
        raise ValueError(f"SENTINEL_BLOCK:{json.dumps(block)}") from exc


def _import_credential_check_engine() -> Any:
    try:
        from strategy.credential_check_engine import CredentialCheckEngine

        return CredentialCheckEngine
    except ImportError:
        import importlib.util

        module_path = _REPO_ROOT / "strategy" / "credential_check_engine.py"
        spec = importlib.util.spec_from_file_location("credential_check_engine", module_path)
        if spec is None or spec.loader is None:
            raise ImportError("credential_check_engine module unavailable") from None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.CredentialCheckEngine


def _screen_matches_with_credentials(
    matches: tuple["VectorMatchResult", ...],
) -> tuple["VectorMatchResult", ...]:
    """Attach dispatch compliance attributes without blocking the vector match pipeline."""
    if not matches:
        return matches

    engine_cls = _import_credential_check_engine()
    checker = engine_cls()
    screened: list[VectorMatchResult] = []
    try:
        for row in matches:
            try:
                evaluation = checker.evaluate_dispatch_compliance(provider_id=row.provider_id)
                screened.append(
                    replace(
                        row,
                        is_eligible=bool(evaluation.is_eligible),
                        compliance_status=str(evaluation.compliance_status),
                    )
                )
            except ValueError as exc:
                logger.warning(
                    "credential screening pending provider=%s error=%s",
                    row.provider_id,
                    exc,
                )
                screened.append(
                    replace(
                        row,
                        is_eligible=False,
                        compliance_status="CREDENTIALS_PENDING",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "credential screening fault provider=%s error=%s",
                    row.provider_id,
                    exc,
                )
                screened.append(
                    replace(
                        row,
                        is_eligible=False,
                        compliance_status="CREDENTIALS_PENDING",
                    )
                )
    finally:
        checker.close()
    return tuple(screened)


def _token_set(text: str) -> set[str]:
    return {token for token in str(text or "").lower().replace(",", " ").split() if len(token) > 2}


def _lexical_boost(query_text: str, profile_text: str) -> float:
    query_tokens = _token_set(query_text)
    profile_tokens = _token_set(profile_text)
    if not query_tokens or not profile_tokens:
        return 0.0
    overlap = len(query_tokens & profile_tokens)
    return overlap / max(len(query_tokens), 1)


def _mock_embed_text(text: str, *, dimensions: int = _EMBEDDING_DIM) -> list[float]:
    """Deterministic pseudo-embedding simulating text-embedding-3-small (1536-dim)."""
    seed = hashlib.sha256(str(text or "").strip().lower().encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dimensions:
        block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
        for byte in block:
            values.append((byte / 127.5) - 1.0)
            if len(values) >= dimensions:
                break
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding_dimension_mismatch")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (left_norm * right_norm)


@dataclass(frozen=True)
class VectorMatchResult:
    provider_id: str
    full_name: str
    role: str
    county: str
    similarity_score: float
    rank: int
    profile_preview: str
    is_eligible: bool = True
    compliance_status: str = "CREDENTIALS_PASSED"


@dataclass(frozen=True)
class VectorMatchResponse:
    ok: bool
    query_text: str
    engine: str
    embedding_dimensions: int
    elapsed_ms: float
    match_count: int
    top_match: VectorMatchResult | None
    matches: tuple[VectorMatchResult, ...]


@dataclass(frozen=True)
class InstantPayoutResponse:
    ok: bool
    payout_id: str
    provider_id: str
    timesheet_id: str
    gross_pay_amount: float
    net_pay_amount: float
    stripe_mode: str
    stripe_reference: str | None
    payout_eta_minutes: int
    message: str
    tax_withholding: dict[str, Any] | None = None


class SemanticPayoutEngine:
    """High-margin semantic match + instant payout gateway (live pgvector with mock fallback)."""

    def __init__(
        self,
        *,
        providers: tuple[dict[str, Any], ...] | None = None,
        embedding_dimensions: int = _EMBEDDING_DIM,
        instant_pay_window_minutes: int = _INSTANT_PAY_WINDOW_MINUTES,
        prefer_live_db: bool = True,
    ) -> None:
        self.embedding_dimensions = int(embedding_dimensions)
        self.instant_pay_window_minutes = int(instant_pay_window_minutes)
        self.prefer_live_db = bool(prefer_live_db)
        self.providers = tuple(providers or _MOCK_COMPLIANT_PROVIDERS)
        self._provider_embeddings = {
            str(row["provider_id"]): _mock_embed_text(str(row.get("profile_text") or ""), dimensions=self.embedding_dimensions)
            for row in self.providers
        }

    def _apply_compliance_screening(self, response: VectorMatchResponse) -> VectorMatchResponse:
        screened_matches = _screen_matches_with_credentials(response.matches)
        top_match = screened_matches[0] if screened_matches else None
        return replace(
            response,
            matches=screened_matches,
            top_match=top_match,
            match_count=len(screened_matches),
        )

    def _live_vector_search(
        self,
        query: str,
        *,
        top_k: int,
        shift_context: dict[str, Any] | None,
    ) -> VectorMatchResponse | None:
        try:
            from fastapi import HTTPException

            from api.vector_match_engine import SemanticMatchQueryIn, search_semantic_matches
            from app.database import SessionLocal
        except ImportError:
            return None

        context = dict(shift_context or {})
        db = SessionLocal()
        started = time.perf_counter()
        try:
            payload = SemanticMatchQueryIn(
                query=query,
                required_role=context.get("required_role"),
                facility_type=context.get("facility_type"),
                facility_county=context.get("facility_county"),
                shift_context=context,
            )
            live = search_semantic_matches(db, payload)
        except HTTPException:
            return None
        except Exception:
            return None
        finally:
            db.close()

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        ranked = tuple(
            VectorMatchResult(
                provider_id=str(candidate.provider_id),
                full_name=candidate.full_name,
                role=str(candidate.credential_type or ""),
                county=str(candidate.county or ""),
                similarity_score=float(candidate.similarity_score),
                rank=int(candidate.rank),
                profile_preview=str(candidate.profile_preview),
            )
            for candidate in live.candidates[:top_k]
        )
        return VectorMatchResponse(
            ok=True,
            query_text=query,
            engine="postgresql_pgvector_cosine",
            embedding_dimensions=self.embedding_dimensions,
            elapsed_ms=round(elapsed_ms, 3),
            match_count=len(ranked),
            top_match=ranked[0] if ranked else None,
            matches=ranked,
        )

    def find_top_vector_matches(
        self,
        query_text: str,
        *,
        top_k: int = _TOP_K,
        use_live_db: bool | None = None,
        shift_context: dict[str, Any] | None = None,
    ) -> VectorMatchResponse:
        _sentinel_validate_facility_geo(shift_context)
        query = str(query_text or "").strip()
        if len(query) < 8:
            raise ValueError("query_text must be at least 8 characters")

        live_enabled = self.prefer_live_db if use_live_db is None else bool(use_live_db)
        if live_enabled:
            live_result = self._live_vector_search(query, top_k=top_k, shift_context=shift_context)
            if live_result is not None:
                return self._apply_compliance_screening(live_result)

        started = time.perf_counter()
        query_vector = _mock_embed_text(query, dimensions=self.embedding_dimensions)
        scored: list[VectorMatchResult] = []

        for provider in self.providers:
            if not bool(provider.get("compliant")):
                continue
            provider_id = str(provider["provider_id"])
            provider_vector = self._provider_embeddings[provider_id]
            score = _cosine_similarity(query_vector, provider_vector)
            score += _lexical_boost(query, str(provider.get("profile_text") or "")) * 0.35
            score = round(min(score, 1.0), 6)
            scored.append(
                VectorMatchResult(
                    provider_id=provider_id,
                    full_name=str(provider.get("full_name") or provider_id),
                    role=str(provider.get("role") or ""),
                    county=str(provider.get("county") or ""),
                    similarity_score=round(score, 6),
                    rank=0,
                    profile_preview=str(provider.get("profile_text") or "")[:120] + "…",
                )
            )

        scored.sort(key=lambda row: row.similarity_score, reverse=True)
        ranked = tuple(
            VectorMatchResult(
                provider_id=row.provider_id,
                full_name=row.full_name,
                role=row.role,
                county=row.county,
                similarity_score=row.similarity_score,
                rank=index,
                profile_preview=row.profile_preview,
            )
            for index, row in enumerate(scored[:top_k], start=1)
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        return self._apply_compliance_screening(
            VectorMatchResponse(
                ok=True,
                query_text=query,
                engine="mock_pgvector_cosine_fallback",
                embedding_dimensions=self.embedding_dimensions,
                elapsed_ms=round(elapsed_ms, 3),
                match_count=len(ranked),
                top_match=ranked[0] if ranked else None,
                matches=ranked,
            )
        )

    def trigger_instant_payout(self, signed_timesheet: dict[str, Any]) -> InstantPayoutResponse:
        _load_dotenv()

        timesheet_id = str(signed_timesheet.get("timesheet_id") or "").strip()
        provider_id = str(signed_timesheet.get("provider_id") or "").strip()
        shift_status = str(signed_timesheet.get("shift_status") or "").strip().upper()
        supervisor_signed = bool(signed_timesheet.get("supervisor_signed"))
        gross_pay_amount = float(signed_timesheet.get("gross_pay_amount") or 0.0)

        if not timesheet_id or not provider_id:
            raise ValueError("timesheet_id and provider_id are required")
        if shift_status != "CONFIRMED":
            raise ValueError("shift_status must be CONFIRMED for instant payout")
        if not supervisor_signed:
            raise ValueError("supervisor_signed must be true")
        if gross_pay_amount <= 0:
            raise ValueError("gross_pay_amount must be positive")

        from app.services.payroll_tax_intercept_bridge import apply_instant_payout_tax_intercept

        net_pay_decimal, tax_breakdown = apply_instant_payout_tax_intercept(
            gross_pay_amount,
            db=None,
            provider_id=provider_id,
            maryland_residence_county=signed_timesheet.get("maryland_residence_county"),
            employee_external_id=signed_timesheet.get("employee_external_id"),
        )
        net_pay_amount = float(net_pay_decimal)
        tax_payload = tax_breakdown.to_dict() if tax_breakdown else None

        dry_run = str(os.getenv("STRIPE_INSTANT_PAYOUT_DRY_RUN", "true")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        stripe_secret = str(os.getenv("STRIPE_SECRET_KEY", "") or "").strip()

        payout_id = f"instant-{timesheet_id[:8]}-{_utc_now().strftime('%Y%m%d%H%M%S')}"
        stripe_mode = "DRY_RUN"
        stripe_reference: str | None = None

        if dry_run or not stripe_secret:
            stripe_reference = f"sim_stripe_instant_{payout_id}"
        else:
            stripe_mode, stripe_reference = self._stripe_instant_network_call(
                amount_cents=int(round(net_pay_amount * 100)),
                provider_id=provider_id,
                stripe_secret=stripe_secret,
                debit_card_id=str(signed_timesheet.get("stripe_debit_card_id") or ""),
                connect_account_id=str(signed_timesheet.get("stripe_connect_account_id") or ""),
            )

        signed_at = _utc_now()
        eligible_at = signed_at + timedelta(minutes=self.instant_pay_window_minutes)
        message = (
            f"Instant payout staged for {provider_id}: ${net_pay_amount:,.2f} net pay "
            f"(gross ${gross_pay_amount:,.2f}"
            + (
                f", withheld ${tax_breakdown.total_withholding:,.2f} "
                f"MD county {tax_breakdown.maryland_residence_county}"
                if tax_breakdown
                else ""
            )
            + f") via {stripe_mode}. Funds routed to registered debit card; "
            f"ETA {self.instant_pay_window_minutes} minutes after supervisor sign-off "
            f"(eligible at {eligible_at.isoformat()})."
        )

        return InstantPayoutResponse(
            ok=True,
            payout_id=payout_id,
            provider_id=provider_id,
            timesheet_id=timesheet_id,
            gross_pay_amount=gross_pay_amount,
            net_pay_amount=net_pay_amount,
            stripe_mode=stripe_mode,
            stripe_reference=stripe_reference,
            payout_eta_minutes=self.instant_pay_window_minutes,
            message=message,
            tax_withholding=tax_payload,
        )

    def _stripe_instant_network_call(
        self,
        *,
        amount_cents: int,
        provider_id: str,
        stripe_secret: str,
        debit_card_id: str,
        connect_account_id: str,
    ) -> tuple[str, str]:
        if not debit_card_id or not connect_account_id:
            raise RuntimeError("stripe_payout_destination_not_configured")

        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx_required_for_live_stripe_instant_payout") from exc

        # Simulated secure network route — production swaps host for live Stripe Connect instant rail.
        endpoint = os.getenv(
            "STRIPE_INSTANT_PAYOUT_SIM_URL",
            "https://api.stripe.com/v1/payouts",
        )
        payload = {
            "amount": amount_cents,
            "currency": "usd",
            "method": "instant",
            "destination": debit_card_id,
            "metadata[provider_id]": provider_id,
        }
        headers = {
            "Authorization": f"Bearer {stripe_secret}",
            "Stripe-Account": connect_account_id,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        with httpx.Client(timeout=20.0) as client:
            response = client.post(endpoint, data=payload, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"stripe_instant_payout_failed:{response.status_code}:{response.text[:180]}")
        body = response.json()
        return "STRIPE", str(body.get("id") or "stripe_payout_ok")


def _print_vector_response(response: VectorMatchResponse) -> None:
    print("SEMANTIC VECTOR MATCH — mock pgvector cosine")
    print(f"  query: {response.query_text}")
    print(f"  elapsed_ms: {response.elapsed_ms}")
    if response.top_match is None:
        print("  top_match: none")
        return
    top = response.top_match
    print(
        f"  top_match: #{top.rank} {top.full_name} ({top.provider_id}) "
        f"score={top.similarity_score}"
    )
    for row in response.matches:
        print(
            f"    rank #{row.rank} {row.full_name} ({row.provider_id}) "
            f"score={row.similarity_score} county={row.county}"
        )


def _print_payout_response(response: InstantPayoutResponse) -> None:
    print("STRIPE INSTANT PAYOUT — gateway simulation")
    print(f"  payout_id: {response.payout_id}")
    print(f"  provider_id: {response.provider_id}")
    print(f"  net_pay: ${response.net_pay_amount:,.2f}")
    print(f"  stripe_mode: {response.stripe_mode}")
    print(f"  stripe_reference: {response.stripe_reference}")
    print(f"  message: {response.message}")


if __name__ == "__main__":
    import sys

    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))

    engine = SemanticPayoutEngine()

    vector_result = engine.find_top_vector_matches(
        "Dementia care, Baltimore, Night Shift — SNF memory unit coverage",
        shift_context={"required_role": "CNA", "facility_type": "SNF", "facility_county": "Montgomery"},
    )
    _print_vector_response(vector_result)
    print(f"  engine: {vector_result.engine}")

    payout_result = engine.trigger_instant_payout(
        {
            "timesheet_id": "33333333-3333-3333-3333-333333333333",
            "provider_id": "CNA-MD-99001",
            "shift_status": "CONFIRMED",
            "supervisor_signed": True,
            "supervisor_name": "Charge Nurse Davis",
            "gross_pay_amount": 240.00,
            "maryland_residence_county": "Montgomery",
            "stripe_connect_account_id": "acct_test_montgomery",
            "stripe_debit_card_id": "card_test_montgomery",
        }
    )
    _print_payout_response(payout_result)

    print("")
    print("SELF-TEST OK — semantic_payout_engine.py")
