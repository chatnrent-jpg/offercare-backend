"""System pulse daemon — autonomous heartbeat for match retry cascade autopilot."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PULSE_INTERVAL_SECONDS = 60
_DEFAULT_COOLDOWN_SECONDS = 60


class SystemPulseHardStop(RuntimeError):
    """Hive halt — system pulse daemon import or compile failure."""


@dataclass(frozen=True)
class PulseTickResult:
    ok: bool
    processed: int
    dispatched: int
    elapsed_ms: float
    message: str


def _import_match_retry_scheduler() -> Any:
    try:
        from strategy.match_retry_scheduler import MatchRetryScheduler

        return MatchRetryScheduler
    except ImportError:
        import importlib.util
        from pathlib import Path

        module_path = Path(__file__).resolve().parent / "match_retry_scheduler.py"
        spec = importlib.util.spec_from_file_location("match_retry_scheduler", module_path)
        if spec is None or spec.loader is None:
            raise SystemPulseHardStop("match_retry_scheduler_import_failed") from None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.MatchRetryScheduler


class SystemPulseDaemon:
    """Background autopilot heartbeat — runs match retry cascade on a fixed clock."""

    def __init__(
        self,
        *,
        pulse_interval_seconds: int = _DEFAULT_PULSE_INTERVAL_SECONDS,
        cooldown_seconds: int = _DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        if pulse_interval_seconds <= 0:
            raise ValueError("pulse_interval_seconds must be positive")
        if cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be positive")
        self.pulse_interval_seconds = int(pulse_interval_seconds)
        self.cooldown_seconds = int(cooldown_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def execute_pulse(self) -> PulseTickResult:
        """Single heartbeat tick — lazy DB session + retry cascade execution."""
        started = time.perf_counter()
        scheduler_cls = _import_match_retry_scheduler()
        scheduler = scheduler_cls()
        try:
            results = scheduler.execute_retry_cascade()
        finally:
            scheduler.close()

        dispatched = sum(1 for row in results if str(row.status) == "dispatched")
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return PulseTickResult(
            ok=True,
            processed=len(results),
            dispatched=dispatched,
            elapsed_ms=round(elapsed_ms, 3),
            message=f"pulse_ok processed={len(results)} dispatched={dispatched}",
        )

    def _run_pulse_loop(self) -> None:
        logger.info(
            "System pulse daemon started interval=%ss cooldown=%ss",
            self.pulse_interval_seconds,
            self.cooldown_seconds,
        )
        while not self._stop_event.is_set():
            try:
                tick = self.execute_pulse()
                logger.info(
                    "System pulse tick ok processed=%s dispatched=%s elapsed_ms=%s",
                    tick.processed,
                    tick.dispatched,
                    tick.elapsed_ms,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "System pulse exception — entering cooling-off period (%ss): %s",
                    self.cooldown_seconds,
                    exc,
                )
                if self._stop_event.wait(self.cooldown_seconds):
                    break
                continue

            if self._stop_event.wait(self.pulse_interval_seconds):
                break

        logger.info("System pulse daemon stopped")

    def start_pulse_loop(self) -> None:
        """Start non-blocking background heartbeat thread (daemon=True)."""
        if self.is_running:
            logger.info("System pulse daemon already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_pulse_loop,
            name="system-pulse-daemon",
            daemon=True,
        )
        self._thread.start()
        logger.info("System pulse daemon thread launched")

    def stop_pulse_loop(self, *, join_timeout_seconds: float = 5.0) -> None:
        """Signal background thread to stop and wait briefly for clean exit."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=max(join_timeout_seconds, 0.1))
        self._thread = None


if __name__ == "__main__":
    print("COMPILE_OK system_pulse_daemon")
    daemon = SystemPulseDaemon(pulse_interval_seconds=60, cooldown_seconds=60)
    print(f"daemon={daemon.__class__.__name__} interval={daemon.pulse_interval_seconds}s")
