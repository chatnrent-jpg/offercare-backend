from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.payroll_tax_intercept_bridge import (
    apply_instant_payout_tax_intercept,
    build_stripe_instant_payout_payload,
    load_payroll_endpoint_routes,
)


def test_load_payroll_endpoint_routes_from_docs() -> None:
    routes = load_payroll_endpoint_routes()
    assert routes
    providers = {route.provider for route in routes}
    assert "gusto" in providers
    assert "checkhq" in providers
    assert any("federal_taxes" in route.path for route in routes)


def test_tier1_county_override_reduces_net_pay() -> None:
    net_pay, breakdown = apply_instant_payout_tax_intercept(
        Decimal("240.00"),
        provider_id=None,
        maryland_residence_county="Montgomery",
    )
    assert breakdown is not None
    assert breakdown.maryland_residence_county == "Montgomery County"
    assert breakdown.total_withholding > Decimal("0")
    assert net_pay < Decimal("240.00")
    assert breakdown.net_pay_amount == net_pay


def test_non_w2_worker_passes_gross_through() -> None:
    net_pay, breakdown = apply_instant_payout_tax_intercept(
        Decimal("180.00"),
        provider_id="not-a-tier1-profile",
    )
    assert breakdown is None
    assert net_pay == Decimal("180.00")


def test_stripe_payload_uses_net_amount_cents() -> None:
    payload = build_stripe_instant_payout_payload(
        gross_pay_amount=Decimal("200.00"),
        provider_id="demo-provider",
        maryland_residence_county="Howard",
    )
    assert payload["gross_pay_amount"] == 200.00
    assert payload["net_pay_amount"] < 200.00
    assert payload["amount_cents"] == int(Decimal(str(payload["net_pay_amount"])) * 100)
    assert payload["tax_withholding"]["maryland_residence_county"] == "Howard County"


def test_semantic_engine_applies_tax_intercept_before_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRIPE_INSTANT_PAYOUT_DRY_RUN", "true")
    from strategy.semantic_payout_engine import SemanticPayoutEngine

    engine = SemanticPayoutEngine(prefer_live_db=False)
    result = engine.trigger_instant_payout(
        {
            "timesheet_id": "44444444-4444-4444-4444-444444444444",
            "provider_id": "CNA-MD-99002",
            "shift_status": "CONFIRMED",
            "supervisor_signed": True,
            "gross_pay_amount": 300.00,
            "maryland_residence_county": "Prince George's",
            "stripe_connect_account_id": "acct_test",
            "stripe_debit_card_id": "card_test",
        }
    )
    assert result.net_pay_amount < result.gross_pay_amount
    assert result.tax_withholding is not None
    assert result.tax_withholding["maryland_county_tax"] > 0
