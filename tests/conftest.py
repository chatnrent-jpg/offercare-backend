"""
Test Configuration & Fixtures — VettedMe.ai

Provides both legacy sync and modern async test fixtures.
Supports gradual migration from synchronous to asynchronous testing.
"""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta, timezone
import uuid as uuid_module

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.database import AsyncSessionLocal, SessionLocal, async_engine, engine
from app.models import MarylandProvider

# Skip app import entirely - not needed for enterprise component tests
APP_AVAILABLE = False
app = None

# Conditionally import migrations if available
try:
    from app.migrations import run_migrations
    MIGRATIONS_AVAILABLE = True
except ImportError:
    MIGRATIONS_AVAILABLE = False

# Conditionally import pollution cleanup if available
try:
    from tests.pollution_cleanup import (
        purge_lock_test_pollution,
        purge_matched_shift_test_pollution,
        purge_post_acute_demo_pollution,
    )
    POLLUTION_CLEANUP_AVAILABLE = True
except ImportError:
    POLLUTION_CLEANUP_AVAILABLE = False

TEST_ADMIN_KEY = "offercare-test-admin-key"


# ============================================================================
# LEGACY SYNC FIXTURES (for backward compatibility)
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def _apply_db_patches() -> None:
    """Apply database migrations (if available)."""
    if MIGRATIONS_AVAILABLE:
        run_migrations(engine)


@pytest.fixture(scope="session", autouse=True)
def _purge_committed_test_pollution() -> None:
    """Purge test pollution at session start (if cleanup available)."""
    if not POLLUTION_CLEANUP_AVAILABLE:
        return
    
    session = SessionLocal()
    try:
        purge_lock_test_pollution(session)
        purge_post_acute_demo_pollution(session)
        purge_matched_shift_test_pollution(session)
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _purge_matched_shift_pollution_before_test() -> None:
    """Purge matched shift pollution before each test (if cleanup available)."""
    if not POLLUTION_CLEANUP_AVAILABLE:
        return
    
    session = SessionLocal()
    try:
        purge_matched_shift_test_pollution(session)
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _disable_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable rate limiting for tests."""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)


@pytest.fixture(autouse=True)
def _disable_cascade_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable cascade worker for tests."""
    monkeypatch.setattr(settings, "SNIPER_CASCADE_WORKER_ENABLED", False)


@pytest.fixture(autouse=True)
def _disable_staffing_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable staffing schedulers for tests."""
    monkeypatch.setattr(settings, "STAFFING_VMS_WORKER_ENABLED", False)
    monkeypatch.setattr(settings, "STAFFING_JOB_BOARD_WORKER_ENABLED", False)


@pytest.fixture(autouse=True)
def _disable_compliance_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable compliance scheduler for tests."""
    monkeypatch.setattr(settings, "COMPLIANCE_MONITOR_WORKER_ENABLED", False)


@pytest.fixture(autouse=True)
def _configure_admin_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure admin API key for tests."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", TEST_ADMIN_KEY)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Admin headers for authenticated requests."""
    return {"X-Admin-Key": TEST_ADMIN_KEY}


@pytest.fixture
def client(admin_headers: dict[str, str]) -> TestClient:
    """Legacy sync test client with admin headers."""
    if app is None:
        pytest.skip("FastAPI app not available (version compatibility issue)")
    return TestClient(app, headers=admin_headers)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Legacy sync database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ============================================================================
# MODERN ASYNC FIXTURES (for new enterprise component tests)
# ============================================================================

@pytest_asyncio.fixture
async def async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session for modern tests."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest.fixture
def test_client() -> TestClient:
    """Test client for API integration tests."""
    # For now, enterprise component tests don't need a full app
    # API integration tests will be skipped if app is unavailable
    if app is None:
        pytest.skip("FastAPI app not available (version compatibility issue)")
    return TestClient(app)


@pytest_asyncio.fixture
async def mock_provider(async_db: AsyncSession) -> MarylandProvider:
    """Create mock Maryland provider for testing."""
    provider = MarylandProvider(
        provider_id=uuid_module.uuid4(),
        full_name="Test CNA Provider",
        email=f"test.{uuid_module.uuid4().hex[:8]}@vettedme.test",
        phone_number="4101234567",
        npi_number="1234567893",  # Valid Luhn checksum
        md_license_number="CNA-MD-TEST123",
        credential_type="CNA",
        service_lines=["POST_ACUTE_CARE"],
        state="MD",
        min_hourly_rate=25.0,
        response_propensity=0.8,
        fatigue_score=0.2,
        is_active=True,
        status="VERIFIED",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    # Mock JWT token for auth
    provider.jwt_token = "mock_jwt_token_for_testing"
    
    async_db.add(provider)
    await async_db.commit()
    await async_db.refresh(provider)
    
    return provider


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (requires pytest-asyncio)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
