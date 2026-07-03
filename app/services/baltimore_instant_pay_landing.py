"""Baltimore instant-pay CNA landing — delegates to localized route manifest (baltimore × cna)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas import BaltimoreInstantPayTextApplyRequest
from app.services.localized_instant_pay_landing import (
    build_localized_instant_pay_page,
    queue_localized_text_apply,
)

LANDING_SLUG = "baltimore-instant-pay-cna"
REGION_SLUG = "baltimore"
LICENSE_SLUG = "cna"


def build_baltimore_instant_pay_landing_page() -> dict:
    return build_localized_instant_pay_page(REGION_SLUG, LICENSE_SLUG)


def queue_baltimore_text_apply(
    db: Session,
    payload: BaltimoreInstantPayTextApplyRequest,
    *,
    client_ip: str | None = None,
) -> dict:
    return queue_localized_text_apply(
        db,
        REGION_SLUG,
        LICENSE_SLUG,
        payload,
        client_ip=client_ip,
    )
