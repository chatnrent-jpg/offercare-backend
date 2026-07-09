"""
High-Throughput Circuit Breaker & State Fallback Engine

Authority: Component 1 — 150ms latency ceiling enforcement for external registry calls (MBON/OIG).
Prevents partial matching state corruption via safe rollback and compliance audit ledger intercept logging.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

# Import ComplianceAuditLedger at module level for testing
try:
    from app.models import ComplianceAuditLedger
except ImportError:
    ComplianceAuditLedger = None  # type: ignore

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker state machine — three-state fault tolerance."""

    CLOSED = "CLOSED"  # Normal operation — requests pass through
    OPEN = "OPEN"  # Breaker tripped — all requests route to fallback
    HALF_OPEN = "HALF_OPEN"  # Recovery test — limited requests allowed


class CircuitBreaker:
    """
    High-throughput async circuit breaker with SQLAlchemy session rollback and audit intercept.

    Enforces strict 150ms latency ceiling for external registry calls. On timeout or upstream
    failure, safely rolls back database session, logs CIRCUIT_BREAKER_INTERCEPT to compliance
    audit ledger, and routes to fallback function.

    Thread/coroutine-safe via asyncio.Lock.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        latency_ceiling_ms: float = 150.0,
        half_open_max_calls: int = 1,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before tripping to OPEN
            recovery_timeout_seconds: Seconds to wait before trying HALF_OPEN
            latency_ceiling_ms: Maximum allowed latency in milliseconds (default 150ms)
            half_open_max_calls: Number of test calls allowed in HALF_OPEN state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.latency_ceiling_seconds = latency_ceiling_ms / 1000.0
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        """Current circuit breaker state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Current failure count."""
        return self._failure_count

    @property
    def last_failure_time(self) -> datetime | None:
        """Timestamp of last failure (None if no failures)."""
        return self._last_failure_time

    async def execute(
        self,
        *,
        downstream_fn: Callable[..., Any],
        fallback_fn: Callable[..., Any],
        db_session: AsyncSession,
        **kwargs: Any,
    ) -> Any:
        """
        Execute downstream function with circuit breaker protection and fallback routing.

        On timeout (>150ms) or upstream exception:
        - Rolls back database session to prevent partial state corruption
        - Logs CIRCUIT_BREAKER_INTERCEPT to compliance_audit_ledger
        - Routes to fallback function

        Args:
            downstream_fn: Async function to execute (e.g., MBON registry call)
            fallback_fn: Async fallback function (e.g., local cached state)
            db_session: SQLAlchemy AsyncSession for rollback and audit logging
            **kwargs: Arguments to pass to downstream_fn and fallback_fn

        Returns:
            Result from downstream_fn if successful, otherwise result from fallback_fn
        """
        async with self._lock:
            # Check if breaker should transition to HALF_OPEN
            if self._state == CircuitBreakerState.OPEN:
                if self._should_attempt_recovery():
                    logger.info("Circuit breaker transitioning to HALF_OPEN for recovery test")
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_calls = 0
                else:
                    # Breaker still OPEN — route to fallback immediately
                    logger.warning("Circuit breaker OPEN — routing to fallback without attempting call")
                    return await self._execute_fallback(
                        fallback_fn=fallback_fn,
                        db_session=db_session,
                        reason="BREAKER_OPEN",
                        **kwargs,
                    )

            # HALF_OPEN state — limit test calls
            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    logger.warning("HALF_OPEN call limit reached — routing to fallback")
                    return await self._execute_fallback(
                        fallback_fn=fallback_fn,
                        db_session=db_session,
                        reason="HALF_OPEN_LIMIT",
                        **kwargs,
                    )
                self._half_open_calls += 1

        # Execute downstream call with strict latency ceiling
        try:
            async with asyncio.timeout(self.latency_ceiling_seconds):
                result = await downstream_fn(**kwargs)

            # Success — reset failure count if recovering
            async with self._lock:
                if self._state == CircuitBreakerState.HALF_OPEN:
                    logger.info("HALF_OPEN recovery successful — transitioning to CLOSED")
                    self._state = CircuitBreakerState.CLOSED
                    self._failure_count = 0
                    self._half_open_calls = 0

            return result

        except asyncio.TimeoutError:
            logger.error(
                f"Circuit breaker timeout — call exceeded {self.latency_ceiling_seconds * 1000}ms ceiling"
            )
            return await self._handle_failure(
                fallback_fn=fallback_fn,
                db_session=db_session,
                error_type="TIMEOUT",
                error_detail=f"Exceeded {self.latency_ceiling_seconds * 1000}ms latency ceiling",
                **kwargs,
            )

        except Exception as exc:
            logger.error(f"Circuit breaker caught upstream exception: {exc}")
            return await self._handle_failure(
                fallback_fn=fallback_fn,
                db_session=db_session,
                error_type="UPSTREAM_EXCEPTION",
                error_detail=str(exc),
                **kwargs,
            )

    async def _handle_failure(
        self,
        *,
        fallback_fn: Callable[..., Any],
        db_session: AsyncSession,
        error_type: str,
        error_detail: str,
        **kwargs: Any,
    ) -> Any:
        """
        Handle downstream failure — increment counters, trip breaker if needed, rollback, log, fallback.

        Args:
            fallback_fn: Async fallback function
            db_session: SQLAlchemy AsyncSession
            error_type: Type of error (TIMEOUT, UPSTREAM_EXCEPTION)
            error_detail: Human-readable error detail
            **kwargs: Arguments for fallback function

        Returns:
            Result from fallback function
        """
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)

            # Trip breaker to OPEN if threshold exceeded
            if self._failure_count >= self.failure_threshold and self._state != CircuitBreakerState.OPEN:
                logger.critical(
                    f"Circuit breaker TRIPPED — failure threshold {self.failure_threshold} exceeded"
                )
                self._state = CircuitBreakerState.OPEN

        # Rollback database session to prevent partial state corruption
        try:
            await db_session.rollback()
            logger.info("Database session rolled back successfully")
        except Exception as rollback_exc:
            logger.error(f"Database rollback failed: {rollback_exc}")

        # Log intercept to compliance audit ledger
        await self._log_circuit_breaker_intercept(
            db_session=db_session,
            error_type=error_type,
            error_detail=error_detail,
            breaker_state=self._state.value,
            failure_count=self._failure_count,
        )

        # Execute fallback
        return await self._execute_fallback(
            fallback_fn=fallback_fn,
            db_session=db_session,
            reason=error_type,
            **kwargs,
        )

    async def _execute_fallback(
        self,
        *,
        fallback_fn: Callable[..., Any],
        db_session: AsyncSession,
        reason: str,
        **kwargs: Any,
    ) -> Any:
        """
        Execute fallback function safely.

        Args:
            fallback_fn: Async fallback function
            db_session: SQLAlchemy AsyncSession (passed to fallback if needed)
            reason: Reason for fallback execution
            **kwargs: Arguments for fallback function

        Returns:
            Result from fallback function
        """
        logger.info(f"Executing fallback function — reason: {reason}")
        try:
            return await fallback_fn(**kwargs)
        except Exception as fallback_exc:
            logger.error(f"Fallback function failed: {fallback_exc}")
            # Return safe empty result if fallback also fails
            return {"status": "FALLBACK_FAILED", "error": str(fallback_exc)}

    async def _log_circuit_breaker_intercept(
        self,
        *,
        db_session: AsyncSession,
        error_type: str,
        error_detail: str,
        breaker_state: str,
        failure_count: int,
    ) -> None:
        """
        Log CIRCUIT_BREAKER_INTERCEPT event to compliance_audit_ledger.

        Safe write — catches exceptions to prevent blocking fallback execution.

        Args:
            db_session: SQLAlchemy AsyncSession
            error_type: Type of error (TIMEOUT, UPSTREAM_EXCEPTION)
            error_detail: Human-readable error detail
            breaker_state: Current breaker state (CLOSED, OPEN, HALF_OPEN)
            failure_count: Current failure count
        """
        try:
            if ComplianceAuditLedger is None:
                logger.warning("ComplianceAuditLedger not available - skipping audit log")
                return

            audit_payload = {
                "event_type": "CIRCUIT_BREAKER_INTERCEPT",
                "error_type": error_type,
                "error_detail": error_detail,
                "breaker_state": breaker_state,
                "failure_count": failure_count,
                "latency_ceiling_ms": self.latency_ceiling_seconds * 1000,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            audit_entry = ComplianceAuditLedger(
                event_type="CIRCUIT_BREAKER_INTERCEPT",
                raw_payload_json=json.dumps(audit_payload),
                created_at=datetime.now(timezone.utc),
            )

            db_session.add(audit_entry)
            await db_session.commit()
            logger.info("CIRCUIT_BREAKER_INTERCEPT logged to compliance_audit_ledger")

        except Exception as log_exc:
            logger.error(f"Failed to log circuit breaker intercept to audit ledger: {log_exc}")
            # Do not raise — logging failure must not block fallback execution

    def _should_attempt_recovery(self) -> bool:
        """
        Determine if breaker should attempt recovery (transition to HALF_OPEN).

        Returns:
            True if recovery timeout has elapsed, False otherwise
        """
        if self._last_failure_time is None:
            return True

        elapsed_seconds = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
        return elapsed_seconds >= self.recovery_timeout_seconds

    async def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state (for testing/admin operations)."""
        async with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            logger.info("Circuit breaker manually reset to CLOSED")
