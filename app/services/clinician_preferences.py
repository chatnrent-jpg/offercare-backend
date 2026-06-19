"""Clinician portal shift-matching preferences."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import MarylandProvider
from app.services.care_taxonomy import normalize_service_lines, service_line_options
from app.services.ops_metrics import log_ops_event


def clinician_preferences_snapshot(provider: MarylandProvider) -> dict:
    return {
        "min_hourly_rate": float(provider.min_hourly_rate or 0),
        "service_lines": str(provider.service_lines or "ALL"),
        "service_line_options": service_line_options(),
    }


def update_clinician_preferences(
    db: Session,
    provider_id: UUID,
    *,
    min_hourly_rate: float | None = None,
    service_lines: str | list[str] | None = None,
) -> MarylandProvider:
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.provider_id == provider_id)
        .first()
    )
    if provider is None:
        raise ValueError("provider_not_found")

    updated_fields: list[str] = []
    if min_hourly_rate is not None:
        provider.min_hourly_rate = float(min_hourly_rate)
        updated_fields.append("min_hourly_rate")
    if service_lines is not None:
        provider.service_lines = normalize_service_lines(service_lines)
        updated_fields.append("service_lines")

    if not updated_fields:
        raise ValueError("no_preference_fields")

    db.commit()
    db.refresh(provider)
    log_ops_event(
        db,
        event_type="CLINICIAN_PREFERENCES",
        actor=provider.full_name,
        entity_type="provider",
        entity_id=provider.provider_id,
        summary=f"Updated shift preferences: {', '.join(updated_fields)}",
        metadata={
            "min_hourly_rate": float(provider.min_hourly_rate or 0),
            "service_lines": str(provider.service_lines or "ALL"),
        },
    )
    return provider
