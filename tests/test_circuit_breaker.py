"""
Test suite for High-Throughput Circuit Breaker & State Fallback Engine

Verifies:
- 150ms latency ceiling enforcement
- State transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Database session rollback on failure
- Compliance audit ledger intercept logging
- Fallback routing under timeout and exception conditions
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.resilience import CircuitBreaker, CircuitBreakerState


@pytest.fixture
def mock_db_session():
    """Mock SQLAlchemy AsyncSession for testing."""
    session = AsyncMock(spec=AsyncSession)
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def circuit_breaker():
    """Circuit breaker instance with test-friendly thresholds."""
    return CircuitBreaker(
        failure_threshold=2,
        recovery_timeout_seconds=1.0,
        latency_ceiling_ms=150.0,
        half_open_max_calls=1,
    )


# ============================================================================
# TEST 1: Timeout triggers fallback and trips breaker to OPEN
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_timeout_triggers_fallback(circuit_breaker, mock_db_session):
    """
    Test that a slow registry call (>150ms) triggers timeout, routes to fallback,
    rolls back database session, and trips breaker to OPEN after threshold.
    """

    # Slow downstream function — exceeds 150ms ceiling
    async def slow_registry_call(**kwargs):
        await asyncio.sleep(0.3)  # 300ms — well over 150ms ceiling
        return {"status": "SUCCESS", "data": "from_registry"}

    # Fast fallback function — returns cached/default state
    async def fast_fallback(**kwargs):
        return {"status": "FALLBACK", "data": "cached_state"}

    # Mock the compliance audit ledger model
    with patch("app.core.resilience.circuit_breaker.ComplianceAuditLedger") as MockAuditLedger:
        mock_audit_instance = MagicMock()
        MockAuditLedger.return_value = mock_audit_instance

        # First call — should timeout and increment failure count
        result1 = await circuit_breaker.execute(
            downstream_fn=slow_registry_call,
            fallback_fn=fast_fallback,
            db_session=mock_db_session,
        )

        # Assert fallback was executed
        assert result1["status"] == "FALLBACK"
        assert result1["data"] == "cached_state"

        # Assert database session was rolled back
        mock_db_session.rollback.assert_called_once()

        # Assert audit log was attempted (add + commit called)
        mock_db_session.add.assert_called_once_with(mock_audit_instance)
        mock_db_session.commit.assert_called_once()

        # Assert failure count incremented but breaker still CLOSED (threshold = 2)
        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

        # Reset mocks for second call
        mock_db_session.rollback.reset_mock()
        mock_db_session.add.reset_mock()
        mock_db_session.commit.reset_mock()

        # Second call — should timeout again and trip breaker to OPEN
        result2 = await circuit_breaker.execute(
            downstream_fn=slow_registry_call,
            fallback_fn=fast_fallback,
            db_session=mock_db_session,
        )

        # Assert fallback was executed again
        assert result2["status"] == "FALLBACK"
        assert result2["data"] == "cached_state"

        # Assert database session rolled back again
        mock_db_session.rollback.assert_called_once()

        # Assert breaker tripped to OPEN
        assert circuit_breaker.failure_count == 2
        assert circuit_breaker.state == CircuitBreakerState.OPEN


# ============================================================================
# TEST 2: OPEN state routes directly to fallback without calling downstream
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_open_routes_to_fallback_immediately(circuit_breaker, mock_db_session):
    """
    Test that when breaker is OPEN, requests route directly to fallback
    without attempting the downstream call.
    """

    call_count = 0

    async def downstream_fn(**kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.3)  # Slow call
        return {"status": "SUCCESS"}

    async def fallback_fn(**kwargs):
        return {"status": "FALLBACK"}

    with patch("app.core.resilience.circuit_breaker.ComplianceAuditLedger"):
        # Trip breaker to OPEN by causing 2 failures
        await circuit_breaker.execute(
            downstream_fn=downstream_fn,
            fallback_fn=fallback_fn,
            db_session=mock_db_session,
        )
        await circuit_breaker.execute(
            downstream_fn=downstream_fn,
            fallback_fn=fallback_fn,
            db_session=mock_db_session,
        )

        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert call_count == 2  # Two attempts before tripping

        # Third call — should route to fallback immediately without calling downstream
        result = await circuit_breaker.execute(
            downstream_fn=downstream_fn,
            fallback_fn=fallback_fn,
            db_session=mock_db_session,
        )

        assert result["status"] == "FALLBACK"
        assert call_count == 2  # Should still be 2 — no new downstream call


# ============================================================================
# TEST 3: Upstream exception triggers fallback and rollback
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_upstream_exception_triggers_fallback(circuit_breaker, mock_db_session):
    """
    Test that an upstream exception (not timeout) also triggers fallback,
    rollback, and audit logging.
    """

    async def failing_downstream(**kwargs):
        raise ValueError("Simulated registry API error")

    async def fallback_fn(**kwargs):
        return {"status": "FALLBACK", "error_handled": True}

    with patch("app.core.resilience.circuit_breaker.ComplianceAuditLedger"):
        result = await circuit_breaker.execute(
            downstream_fn=failing_downstream,
            fallback_fn=fallback_fn,
            db_session=mock_db_session,
        )

        # Assert fallback executed
        assert result["status"] == "FALLBACK"
        assert result["error_handled"] is True

        # Assert rollback called
        mock_db_session.rollback.assert_called_once()

        # Assert failure count incremented
        assert circuit_breaker.failure_count == 1


# ============================================================================
# TEST 4: Successful call resets HALF_OPEN to CLOSED
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery(circuit_breaker, mock_db_session):
    """
    Test HALF_OPEN recovery — after timeout expires, one successful call
    should transition breaker from OPEN → HALF_OPEN → CLOSED.
    """

    call_count = 0

    async def sometimes_slow_fn(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            # First two calls timeout
            await asyncio.sleep(0.3)
        else:
            # Third call succeeds quickly
            await asyncio.sleep(0.01)
        return {"status": "SUCCESS", "call_count": call_count}

    async def fallback_fn(**kwargs):
        return {"status": "FALLBACK"}

    with patch("app.core.resilience.circuit_breaker.ComplianceAuditLedger"):
        # Trip breaker to OPEN
        await circuit_breaker.execute(
            downstream_fn=sometimes_slow_fn,
            fallback_fn=fallback_fn,
            db_session=mock_db_session,
        )
        await circuit_breaker.execute(
            downstream_fn=sometimes_slow_fn,
            fallback_fn=fallback_fn,
            db_session=mock_db_session,
        )

        assert circuit_breaker.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Next call should attempt HALF_OPEN recovery
        result = await circuit_breaker.execute(
            downstream_fn=sometimes_slow_fn,
            fallback_fn=fallback_fn,
            db_session=mock_db_session,
        )

        # Call should succeed (fast now) and transition to CLOSED
        assert result["status"] == "SUCCESS"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0


# ============================================================================
# TEST 5: Manual reset
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_manual_reset(circuit_breaker, mock_db_session):
    """Test that manual reset returns breaker to CLOSED state."""

    async def slow_fn(**kwargs):
        await asyncio.sleep(0.3)
        return {}

    async def fallback_fn(**kwargs):
        return {"status": "FALLBACK"}

    with patch("app.core.resilience.circuit_breaker.ComplianceAuditLedger"):
        # Trip breaker to OPEN
        await circuit_breaker.execute(
            downstream_fn=slow_fn,
            fallback_fn=fallback_fn,
            db_session=mock_db_session,
        )
        await circuit_breaker.execute(
            downstream_fn=slow_fn,
            fallback_fn=fallback_fn,
            db_session=mock_db_session,
        )

        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 2

        # Manual reset
        await circuit_breaker.reset()

        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0


# ============================================================================
# TEST 6: Fallback failure handling
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_fallback_failure(circuit_breaker, mock_db_session):
    """Test that if fallback also fails, a safe empty result is returned."""

    async def slow_fn(**kwargs):
        await asyncio.sleep(0.3)
        return {}

    async def failing_fallback(**kwargs):
        raise RuntimeError("Fallback also failed")

    with patch("app.core.resilience.circuit_breaker.ComplianceAuditLedger"):
        result = await circuit_breaker.execute(
            downstream_fn=slow_fn,
            fallback_fn=failing_fallback,
            db_session=mock_db_session,
        )

        # Should return safe failure indicator
        assert result["status"] == "FALLBACK_FAILED"
        assert "error" in result


# ============================================================================
# TEST 7: Concurrent execution safety (asyncio.Lock)
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_concurrent_safety(circuit_breaker, mock_db_session):
    """Test that concurrent executions are thread/coroutine-safe via asyncio.Lock."""

    async def slow_fn(**kwargs):
        await asyncio.sleep(0.3)
        return {}

    async def fallback_fn(**kwargs):
        return {"status": "FALLBACK"}

    with patch("app.core.resilience.circuit_breaker.ComplianceAuditLedger"):
        # Execute 5 concurrent calls
        tasks = [
            circuit_breaker.execute(
                downstream_fn=slow_fn,
                fallback_fn=fallback_fn,
                db_session=mock_db_session,
            )
            for _ in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # All should route to fallback
        assert all(r["status"] == "FALLBACK" for r in results)

        # Breaker should be OPEN (threshold = 2)
        assert circuit_breaker.state == CircuitBreakerState.OPEN

        # Failure count should be stable (not corrupted by concurrent access)
        assert circuit_breaker.failure_count >= 2
