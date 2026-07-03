"""Sentinel input guardrails — structured Pydantic V2 validation for external payloads."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

_UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_TIMESHEET_TOKEN_PATTERN = re.compile(r"^ts_[A-Za-z0-9_-]{8,128}$")


class SentinelValidationHardStop(RuntimeError):
    """Hive halt — sentinel validation module import or compile failure."""


def _import_compliance_audit_ledger() -> Any:
    try:
        from app.models.compliance_audit_ledger import ComplianceAuditLedger

        return ComplianceAuditLedger
    except ImportError:
        import importlib.util

        module_path = Path(__file__).resolve().parent.parent / "models" / "compliance_audit_ledger.py"
        spec = importlib.util.spec_from_file_location("compliance_audit_ledger", module_path)
        if spec is None or spec.loader is None:
            raise SentinelValidationHardStop("compliance_audit_ledger_import_failed") from None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.ComplianceAuditLedger


def _persist_sentinel_block_to_ledger(
    block: dict[str, Any],
    *,
    provider_id: str | None = None,
    timesheet_token: str | None = None,
    source_payload: dict[str, Any] | None = None,
) -> None:
    """Lazy persistence — never blocks Sentinel rejection if DB is unavailable."""
    try:
        ledger_cls = _import_compliance_audit_ledger()
        from app.database import SessionLocal

        payload_context = dict(source_payload or {})
        resolved_provider_id = str(provider_id or payload_context.get("provider_id") or "").strip() or None
        resolved_timesheet_token = (
            str(timesheet_token or payload_context.get("timesheet_token") or "").strip() or None
        )
        raw_payload = {
            "sentinel_block": block,
            "source_payload": payload_context,
        }

        db = SessionLocal()
        try:
            row = ledger_cls(
                provider_id=resolved_provider_id,
                timesheet_token=resolved_timesheet_token,
                compliance_status="SENTINEL_BLOCK",
                is_eligible=False,
                raw_payload_json=json.dumps(raw_payload, default=str),
            )
            db.add(row)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Sentinel audit ledger persist skipped: %s", exc)


def format_sentinel_validation_error(
    exc: ValidationError,
    *,
    provider_id: str | None = None,
    timesheet_token: str | None = None,
    source_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured validation envelope for Hive Supervisor logging console routing."""
    block = {
        "ok": False,
        "sentinel": "VALIDATION_BLOCK",
        "error_count": exc.error_count(),
        "errors": [
            {
                "field": ".".join(str(part) for part in err.get("loc", ())),
                "message": err.get("msg"),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ],
    }
    _persist_sentinel_block_to_ledger(
        block,
        provider_id=provider_id,
        timesheet_token=timesheet_token,
        source_payload=source_payload,
    )
    return block


def _validate_timesheet_token_value(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise ValueError("timesheet_token must not be empty")

    if _TIMESHEET_TOKEN_PATTERN.fullmatch(token):
        return token

    if _UUID_V4_PATTERN.fullmatch(token):
        try:
            parsed = UUID(token)
        except ValueError as exc:
            raise ValueError("timesheet_token must be a valid UUIDv4 or ts_ system token") from exc
        if parsed.version != 4:
            raise ValueError("timesheet_token UUID must be version 4 (UUIDv4)")
        return token.lower()

    raise ValueError(
        "timesheet_token must match UUIDv4 format or strict system prefix ts_<token>"
    )


class StripeWebhookMetadataValidator(BaseModel):
    """Stripe webhook metadata guard — binds escrow events to dispatch routes."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    timesheet_token: str = Field(
        ...,
        description="UUIDv4 or ts_ prefixed system timesheet token",
        min_length=8,
        max_length=128,
    )
    provider_id: str = Field(
        ...,
        description="Non-empty provider identifier bound to autonomous dispatch",
        min_length=1,
        max_length=128,
    )

    @field_validator("timesheet_token")
    @classmethod
    def validate_timesheet_token(cls, value: str) -> str:
        return _validate_timesheet_token_value(value)

    @field_validator("provider_id")
    @classmethod
    def validate_provider_id(cls, value: str) -> str:
        token = str(value or "").strip()
        if not token:
            raise ValueError("provider_id must not be null or empty — dispatch route binding required")
        if token.lower() in {"null", "none", "undefined"}:
            raise ValueError("provider_id must be a firm autonomous dispatch binding, not a placeholder")
        return token


class FacilityGeoInputValidator(BaseModel):
    """Facility geo-query guard — protects pgvector/geo cluster from malformed scans."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Facility latitude in decimal degrees",
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Facility longitude in decimal degrees",
    )
    search_radius_miles: float = Field(
        ...,
        ge=1.0,
        le=100.0,
        description="Geo search radius — bounded to prevent memory-exhaustion table scans",
    )

    @field_validator("latitude")
    @classmethod
    def validate_latitude_bounds(cls, value: float) -> float:
        if value < -90.0 or value > 90.0:
            raise ValueError("latitude must be between -90.0 and 90.0 inclusive")
        return float(value)

    @field_validator("longitude")
    @classmethod
    def validate_longitude_bounds(cls, value: float) -> float:
        if value < -180.0 or value > 180.0:
            raise ValueError("longitude must be between -180.0 and 180.0 inclusive")
        return float(value)

    @field_validator("search_radius_miles")
    @classmethod
    def validate_search_radius(cls, value: float) -> float:
        radius = float(value)
        if radius < 1.0:
            raise ValueError("search_radius_miles must be at least 1.0 mile")
        if radius > 100.0:
            raise ValueError("search_radius_miles must not exceed 100.0 miles")
        return radius


class SentinelValidationSuite:
    """Grouped Sentinel validators for Hive Supervisor routing."""

    StripeWebhookMetadata = StripeWebhookMetadataValidator
    FacilityGeoInput = FacilityGeoInputValidator

    @staticmethod
    def validate_stripe_webhook_metadata(payload: dict[str, Any]) -> StripeWebhookMetadataValidator:
        return StripeWebhookMetadataValidator.model_validate(payload)

    @staticmethod
    def validate_facility_geo_input(payload: dict[str, Any]) -> FacilityGeoInputValidator:
        return FacilityGeoInputValidator.model_validate(payload)


if __name__ == "__main__":
    print("COMPILE_OK sentinel_validation")
