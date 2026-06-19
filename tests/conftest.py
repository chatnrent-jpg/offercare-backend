import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal, engine
from app.migrations import run_migrations
from app.main import app
from tests.pollution_cleanup import (
    purge_lock_test_pollution,
    purge_matched_shift_test_pollution,
    purge_post_acute_demo_pollution,
)

TEST_ADMIN_KEY = "offercare-test-admin-key"


@pytest.fixture(scope="session", autouse=True)
def _apply_db_patches() -> None:
    run_migrations(engine)


@pytest.fixture(scope="session", autouse=True)
def _purge_committed_test_pollution() -> None:
    session = SessionLocal()
    try:
        purge_lock_test_pollution(session)
        purge_post_acute_demo_pollution(session)
        purge_matched_shift_test_pollution(session)
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _purge_matched_shift_pollution_before_test() -> None:
    session = SessionLocal()
    try:
        purge_matched_shift_test_pollution(session)
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _disable_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)


@pytest.fixture(autouse=True)
def _disable_cascade_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SNIPER_CASCADE_WORKER_ENABLED", False)


@pytest.fixture(autouse=True)
def _disable_staffing_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STAFFING_VMS_WORKER_ENABLED", False)
    monkeypatch.setattr(settings, "STAFFING_JOB_BOARD_WORKER_ENABLED", False)


@pytest.fixture(autouse=True)
def _disable_compliance_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "COMPLIANCE_MONITOR_WORKER_ENABLED", False)


@pytest.fixture(autouse=True)
def _configure_admin_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_API_KEY", TEST_ADMIN_KEY)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Key": TEST_ADMIN_KEY}


@pytest.fixture
def client(admin_headers: dict[str, str]) -> TestClient:
    return TestClient(app, headers=admin_headers)
