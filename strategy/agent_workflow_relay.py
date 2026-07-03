"""Agent workflow relay — Claude matching brain to Manus web operator handoff coordinator."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DEFAULT_MANUS_REGISTRY_URL = "https://mbon.maryland.gov"
_DEFAULT_SHIFT_ID_TOKEN = "agent_relay_demo_shift"


class AgentWorkflowRelayHardStop(RuntimeError):
    """Hive halt — agent workflow relay dependency or compile failure."""


class AgentWorkflowRelay:
    """Multi-agent pipeline coordinator — Claude logic layer to Manus browser execution."""

    def __init__(self, db: Session | None = None) -> None:
        self._db = db
        self._owns_session = False
        self._broker: Any | None = None
        self._circuit_breaker: Any | None = None

    @property
    def db(self) -> Session:
        if self._db is None:
            try:
                from app.database import SessionLocal
            except Exception as exc:  # noqa: BLE001
                raise AgentWorkflowRelayHardStop("database_session_import_failed") from exc
            self._db = SessionLocal()
            self._owns_session = True
        return self._db

    def close(self) -> None:
        if self._broker is not None:
            try:
                self._broker.close()
            except Exception:  # noqa: BLE001
                logger.debug("agent_workflow_relay broker close skipped", exc_info=True)
            self._broker = None
        if self._owns_session and self._db is not None:
            self._db.close()
            self._db = None
            self._owns_session = False

    def _get_broker(self) -> Any:
        if self._broker is None:
            try:
                from strategy.unified_match_matrix_broker import UnifiedMatchMatrixBroker
            except Exception as exc:  # noqa: BLE001
                raise AgentWorkflowRelayHardStop("unified_match_matrix_broker_import_failed") from exc
            self._broker = UnifiedMatchMatrixBroker(db=self.db)
        return self._broker

    def _get_circuit_breaker(self) -> Any:
        if self._circuit_breaker is None:
            try:
                from strategy.network_circuit_breaker import NetworkCircuitBreaker
            except Exception as exc:  # noqa: BLE001
                raise AgentWorkflowRelayHardStop("network_circuit_breaker_import_failed") from exc
            self._circuit_breaker = NetworkCircuitBreaker()
        return self._circuit_breaker

    @staticmethod
    def _shift_id_from_context(shift_context: dict[str, Any]) -> str:
        for key in ("shift_id", "offer_id", "inbound_tracking_token"):
            token = str(shift_context.get(key) or "").strip()
            if token:
                return token
        return f"{_DEFAULT_SHIFT_ID_TOKEN}_{uuid4().hex[:12]}"

    def invoke_claude_matching_brain(
        self,
        shift_context: dict[str, Any],
        *,
        shift_id: str | None = None,
    ) -> dict[str, Any]:
        """Forward shift context to UnifiedMatchMatrixBroker under lookahead-safe routing."""
        if not isinstance(shift_context, dict):
            raise TypeError("shift_context must be a dict")

        resolved_shift_id = str(shift_id or "").strip() or self._shift_id_from_context(shift_context)
        broker = self._get_broker()
        try:
            result = broker.resolve_canonical_shift_matches(resolved_shift_id, shift_context)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "agent_workflow_relay claude brain failed shift_id=%s err=%s",
                resolved_shift_id,
                exc,
            )
            raise
        return {
            "assigned_agent": "CLAUDE_MATCHING_BRAIN",
            "shift_id": resolved_shift_id,
            "routing_engine": result.get("routing_engine"),
            "match_count": result.get("match_count"),
            "ok": bool(result.get("ok")),
            "matches": list(result.get("matches") or []),
            "broker_payload": result,
        }

    @staticmethod
    def _build_manus_browser_task_packet(
        provider_id: str,
        target_url: str,
    ) -> dict[str, Any]:
        return {
            "assigned_agent": "MANUS_WEB_OPERATOR",
            "provider_id": str(provider_id).strip(),
            "target_registry": str(target_url).strip() or _DEFAULT_MANUS_REGISTRY_URL,
            "verification_required": True,
            "status": "PENDING_MANUS_BROWSER_RUN",
        }

    def delegate_web_lookup_to_manus(
        self,
        provider_id: str,
        target_url: str = _DEFAULT_MANUS_REGISTRY_URL,
    ) -> dict[str, Any]:
        """Stage Manus browser verification task behind the 150ms network speed guard."""
        provider_token = str(provider_id or "").strip()
        if not provider_token:
            raise ValueError("provider_id is required")

        registry_url = str(target_url or _DEFAULT_MANUS_REGISTRY_URL).strip()
        breaker = self._get_circuit_breaker()
        guarded = breaker.execute_with_speed_guard(
            self._build_manus_browser_task_packet,
            provider_token,
            registry_url,
        )

        if isinstance(guarded, dict) and guarded.get("circuit_tripped"):
            return {
                "assigned_agent": "MANUS_WEB_OPERATOR",
                "provider_id": provider_token,
                "target_registry": registry_url,
                "verification_required": True,
                "status": str(guarded.get("status") or "CIRCUIT_BREAKER_TRIPPED"),
                "circuit_tripped": True,
                "details": guarded.get("details"),
            }

        return dict(guarded)

    def execute_demo_workflow_run(
        self,
        *,
        shift_id: str,
        facility_name: str = "",
        shift_context: dict[str, Any] | None = None,
        provider_id: str | None = None,
        target_url: str = _DEFAULT_MANUS_REGISTRY_URL,
    ) -> dict[str, Any]:
        """End-to-end multi-agent relay — Claude match brain then Manus registry handoff."""
        shift_token = str(shift_id or "").strip()
        if not shift_token:
            raise ValueError("shift_id is required")

        resolved_context = dict(shift_context or {})
        resolved_context["shift_id"] = shift_token
        facility_token = str(facility_name or "").strip()
        if facility_token:
            resolved_context["facility_name"] = facility_token

        started_at = datetime.now(timezone.utc).isoformat()
        workflow_id = f"agent_relay_{uuid4().hex[:16]}"
        stages: list[str] = []

        claude_result: dict[str, Any] | None = None
        claude_error: str | None = None
        try:
            claude_result = self.invoke_claude_matching_brain(
                resolved_context,
                shift_id=shift_token,
            )
            stages.append("claude_matching_brain")
        except Exception as exc:  # noqa: BLE001
            claude_error = str(exc)

        resolved_provider_id = str(provider_id or "").strip()
        if not resolved_provider_id and claude_result:
            matches = list(claude_result.get("matches") or [])
            if matches:
                top = matches[0]
                if isinstance(top, dict):
                    resolved_provider_id = str(top.get("provider_id") or "").strip()

        manus_result: dict[str, Any] | None = None
        manus_error: str | None = None
        if resolved_provider_id:
            try:
                manus_result = self.delegate_web_lookup_to_manus(
                    resolved_provider_id,
                    target_url=target_url,
                )
                stages.append("manus_web_operator")
            except Exception as exc:  # noqa: BLE001
                manus_error = str(exc)
        else:
            manus_error = "provider_id_unresolved"

        completed_at = datetime.now(timezone.utc).isoformat()
        ok = claude_result is not None and claude_result.get("ok") is True
        manus_pending = (
            manus_result is not None
            and manus_result.get("status") == "PENDING_MANUS_BROWSER_RUN"
            and not manus_result.get("circuit_tripped")
        )
        if claude_error:
            status = "FAILED"
        elif manus_error and not manus_pending:
            status = "PARTIAL"
        elif ok and manus_pending:
            status = "COMPLETE"
        elif ok:
            status = "PARTIAL"
        else:
            status = "PARTIAL"

        return {
            "workflow": "agent_workflow_relay_demo",
            "workflow_id": workflow_id,
            "shift_id": shift_token,
            "facility_name": facility_token or None,
            "status": status,
            "started_at_utc": started_at,
            "completed_at_utc": completed_at,
            "pipeline_stages": stages,
            "claude_brain": claude_result,
            "claude_error": claude_error,
            "manus_handoff": manus_result,
            "manus_error": manus_error,
            "resolved_provider_id": resolved_provider_id or None,
            "shift_context": resolved_context,
        }


if __name__ == "__main__":
    sample_context = {
        "required_role": "CNA",
        "facility_type": "SNF",
        "care_tags": ["dementia"],
        "shift_starts_at": "2026-06-29T23:00:00+00:00",
        "facility_county": "Baltimore City",
        "state": "MD",
    }
    relay = AgentWorkflowRelay()
    try:
        packet = relay.execute_demo_workflow_run(
            shift_id="agent_relay_demo_shift_001",
            facility_name="Baltimore Memory Care",
            shift_context=sample_context,
            provider_id="CNA-MD-DEMO-001",
        )
        assert packet["workflow"] == "agent_workflow_relay_demo"
        assert "claude_matching_brain" in packet["pipeline_stages"]
        assert packet["manus_handoff"] is not None
        assert packet["manus_handoff"]["assigned_agent"] == "MANUS_WEB_OPERATOR"
    finally:
        relay.close()
    print("COMPILE_OK agent_workflow_relay")
