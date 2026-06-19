from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import OfferCareJobOffer
from app.seed import seed_saint_judes_demo
from app.services.deploy_walkthrough import build_deploy_checklist
from app.services.ops_metrics import get_ops_metrics

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_lock_rate_never_exceeds_one(db: Session) -> None:
    metrics = get_ops_metrics(db)
    assert 0.0 <= metrics["lock_rate"] <= 1.0


def test_lock_rate_caps_when_placements_exceed_sms() -> None:
    raw_lock_rate = 5 / 1
    lock_rate = round(min(1.0, raw_lock_rate), 4)
    assert lock_rate == 1.0


def test_seed_resets_assigned_provider_when_rebroadcasting(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer = (
        db.query(OfferCareJobOffer)
        .filter(OfferCareJobOffer.offer_id == UUID(seeded["offer_id"]))
        .one()
    )
    provider_id = UUID(seeded["provider_ids"].split(",")[0])
    offer.compliance_lock_status = "LOCKED"
    offer.assigned_provider_id = provider_id
    db.commit()

    seed_saint_judes_demo(db)
    db.refresh(offer)
    assert offer.compliance_lock_status == "BROADCASTING"
    assert offer.assigned_provider_id is None


def test_deploy_checklist_includes_hardening_items(client: TestClient) -> None:
    response = client.get("/api/deploy/checklist")
    assert response.status_code == 200
    body = response.json()
    ids = {row["id"] for row in body["items"]}
    assert "email_smtp" in ids
    assert "push_vapid" in ids
    assert "portal_pwa" in ids
    assert "supported_states" in ids
    assert body["portal_steps"]


def test_deploy_checklist_portal_pwa_ready(db: Session) -> None:
    snapshot = build_deploy_checklist(db)
    portal_item = next(row for row in snapshot["items"] if row["id"] == "portal_pwa")
    assert portal_item["status"] == "ready"


def test_deploy_checklist_supported_states_ready(db: Session) -> None:
    snapshot = build_deploy_checklist(db)
    states_item = next(row for row in snapshot["items"] if row["id"] == "supported_states")
    assert states_item["status"] == "ready"
    assert "NJ" in states_item["detail"]


def test_env_example_documents_production_hardening() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "RATE_LIMIT_ENABLED" in text
    assert "SECURITY_HEADERS_ENABLED" in text
    assert "VAPID_PUBLIC_KEY" in text
    assert "SUPPORTED_STATES" in text
