"""Portal step 17 — demo lockable shift repair and pre-lock confirmation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, SAMPLE_DEMO_PORTAL_EMAIL
from app.services.demo_portal_lockable import ensure_demo_portal_lockable_shift
from app.main import PORTAL_BUILD_ID


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_nj_demo_seed_uses_cna_role_for_portal_cna() -> None:
    from pathlib import Path

    text = Path("app/seed.py").read_text(encoding="utf-8")
    block_start = text.index("def seed_nj_nursing_home_demo")
    block_end = text.index("def seed_home_health_demo", block_start)
    block = text[block_start:block_end]
    assert 'shift_role="CNA"' in block
    assert 'email": "nj.snf.cna.a@offercare.demo"' in block


def test_demo_cna_has_lockable_shift_after_broker_bypass(db: Session) -> None:
    from app.services.demo_portal_lockable import ensure_demo_portal_lockable_shift
    from app.services.demo_portal_accounts import SAMPLE_DEMO_PORTAL_EMAIL
    from app.services.shift_matching import list_matched_shifts_for_provider

    ensure_demo_portal_lockable_shift(db)
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == SAMPLE_DEMO_PORTAL_EMAIL)
        .first()
    )
    if provider is None:
        pytest.skip("demo CNA unavailable")
    matched = list_matched_shifts_for_provider(db, provider, limit=10)
    assert len(matched) >= 1


def test_portal_step17_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    shifts_js = client.get("/portal/shifts.js").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert "/portal/shifts.js" in html
    assert "applyDemoClientLockHints" in shifts_js
    assert "lock-precheck-modal" in html
    assert "beginLockShift" in js
    assert "showLockPrecheckModal" in js


def test_legacy_demo_login_still_works(client: TestClient) -> None:
    response = client.post(
        "/api/clinicians/login",
        json={"email": SAMPLE_DEMO_PORTAL_EMAIL, "password": DEMO_PORTAL_PASSWORD},
    )
    if response.status_code == 401:
        pytest.skip("demo login unavailable in this database")
    assert response.status_code == 200
    assert response.json()["provider"]["email"] == SAMPLE_DEMO_PORTAL_EMAIL
