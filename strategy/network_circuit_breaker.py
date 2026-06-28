"""High-speed network circuit breaker — 150ms API speed guard for matching pipeline."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

_SPEED_GUARD_TIMEOUT_S = 0.150
_DEFAULT_COOLOFF_SECONDS = 30.0
_TRIP_STATUS = "CIRCUIT_BREAKER_TRIPPED"
_TRIP_DETAILS = "Target API exceeded the high-speed 150ms performance safety threshold."

_STATE_CLOSED = "CLOSED"
_STATE_OPEN = "OPEN"
_STATE_HALF_OPEN = "HALF_OPEN"

T = TypeVar("T")


class NetworkCircuitBreakerHardStop(RuntimeError):
    """Hive halt — circuit breaker import or compile failure."""


class NetworkCircuitBreaker:
    """Concurrency wrapper — trips when external callables exceed the 150ms safety threshold."""

    timeout_s: float = _SPEED_GUARD_TIMEOUT_S

    def __init__(self, cooloff_seconds: float = _DEFAULT_COOLOFF_SECONDS) -> None:
        self._lock = threading.Lock()
        self._state = _STATE_CLOSED
        self._last_state_change_time = time.monotonic()
        self._cooloff_seconds = cooloff_seconds

    def _trip_payload(self) -> dict[str, Any]:
        return {
            "circuit_tripped": True,
            "status": _TRIP_STATUS,
            "details": _TRIP_DETAILS,
        }

    def _transition_locked(self, new_state: str) -> None:
        self._state = new_state
        self._last_state_change_time = time.monotonic()

    def _open_circuit(self) -> None:
        with self._lock:
            if self._state != _STATE_OPEN:
                logger.warning("HIVE_CIRCUIT: state -> OPEN")
            self._transition_locked(_STATE_OPEN)

    def _close_circuit(self) -> None:
        with self._lock:
            logger.info("HIVE_CIRCUIT: HALF_OPEN -> CLOSED (healed)")
            self._transition_locked(_STATE_CLOSED)

    def _intercept_before_execute(self) -> tuple[bool, bool]:
        """Return (may_execute, is_probe)."""
        with self._lock:
            if self._state == _STATE_CLOSED:
                return True, False
            if self._state == _STATE_HALF_OPEN:
                return True, True
            elapsed = time.monotonic() - self._last_state_change_time
            if elapsed >= self._cooloff_seconds:
                logger.info("HIVE_CIRCUIT: OPEN -> HALF_OPEN probe trial")
                self._transition_locked(_STATE_HALF_OPEN)
                return True, True
            return False, False

    def execute_with_speed_guard(
        self,
        func: Callable[..., T],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> T | dict[str, Any]:
        """Run *func* in an isolated thread; trip if it exceeds 150ms."""
        may_execute, is_probe = self._intercept_before_execute()
        if not may_execute:
            logger.warning(
                "HIVE_CIRCUIT: OPEN cool-off active (%.0fs) — short-circuit",
                self._cooloff_seconds,
            )
            return self._trip_payload()

        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nw_circuit")
        future: Future[T] = executor.submit(func, *args, **kwargs)
        try:
            result = future.result(timeout=self.timeout_s)
            if is_probe:
                self._close_circuit()
            return result
        except FuturesTimeoutError:
            logger.warning(
                "HIVE_CIRCUIT_TRIP: %s exceeded %.0fms guard",
                getattr(func, "__name__", "callable"),
                self.timeout_s * 1000,
            )
            self._open_circuit()
            return self._trip_payload()
        except Exception:
            if is_probe:
                logger.warning(
                    "HIVE_CIRCUIT: HALF_OPEN probe failed for %s — reopening circuit",
                    getattr(func, "__name__", "callable"),
                )
                self._open_circuit()
            raise
        finally:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                executor.shutdown(wait=False)


if __name__ == "__main__":
    print("COMPILE_OK network_circuit_breaker")
    breaker = NetworkCircuitBreaker()
    fast = breaker.execute_with_speed_guard(lambda: {"ok": True})
    print(f"fast={fast} state={breaker._state}")
    slow = breaker.execute_with_speed_guard(lambda: __import__("time").sleep(0.5) or "late")
    print(f"slow_tripped={slow.get('circuit_tripped')} state={breaker._state}")
    blocked = breaker.execute_with_speed_guard(lambda: {"ok": True})
    print(f"blocked_tripped={blocked.get('circuit_tripped')} state={breaker._state}")
