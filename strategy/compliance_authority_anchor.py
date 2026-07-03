"""Compliance authority anchor — sync strategy gate outcomes to provider dispatch state."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DISPATCH_STATUS_BY_COMPLIANCE = {
    "CREDENTIALS_PASSED": "ELIGIBLE",
    "OIG_FLAGGED": "SUSPENDED_SANCTIONED",
    "LICENSE_EXPIRED": "SUSPENDED_EXPIRED",
    "CREDENTIALS_PENDING": "COMPLIANCE_HOLD",
    "COMPLIANCE_SENTINEL_MATCHING_HOLD": "COMPLIANCE_HOLD",
    "COMPLIANCE_SENTINEL_BLOCKED": "COMPLIANCE_HOLD",
}


class ComplianceAuthorityAnchorHardStop(RuntimeError):
    """Hive halt — compliance authority anchor import or DB failure."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_checked_at(value: str | None) -> datetime:
    if not value:
        return _utc_now()
    token = str(value).strip()
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return _utc_now()
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _import_dispatch_compliance_evaluation() -> Any:
    try:
        from strategy.credential_check_engine import DispatchComplianceEvaluation
    except ImportError:
        import importlib.util

        module_path = Path(__file__).resolve().parent / "credential_check_engine.py"
        spec = importlib.util.spec_from_file_location("credential_check_engine", module_path)
        if spec is None or spec.loader is None:
            raise ComplianceAuthorityAnchorHardStop("dispatch_compliance_evaluation_import_failed") from None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.DispatchComplianceEvaluation
    return DispatchComplianceEvaluation


def _import_compliance_audit_ledger() -> Any:
    try:
        from app.models.compliance_audit_ledger import ComplianceAuditLedger
    except ImportError:
        import importlib.util

        module_path = Path(__file__).resolve().parents[1] / "app" / "models" / "compliance_audit_ledger.py"
        spec = importlib.util.spec_from_file_location("compliance_audit_ledger", module_path)
        if spec is None or spec.loader is None:
            raise ComplianceAuthorityAnchorHardStop("compliance_audit_ledger_import_failed") from None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.ComplianceAuditLedger
    return ComplianceAuditLedger


def _import_maryland_provider() -> Any:
    try:
        from app.models import MarylandProvider
    except ImportError as exc:
        raise ComplianceAuthorityAnchorHardStop("maryland_provider_import_failed") from exc
    return MarylandProvider


def _dispatch_status_for(compliance_status: str) -> str | None:
    return _DISPATCH_STATUS_BY_COMPLIANCE.get(str(compliance_status or "").strip().upper())


def _evaluation_payload(evaluation: Any) -> dict[str, Any]:
    return {
        "ok": evaluation.ok,
        "provider_id": evaluation.provider_id,
        "license_number": evaluation.license_number,
        "is_eligible": evaluation.is_eligible,
        "compliance_status": evaluation.compliance_status,
        "checked_at": evaluation.checked_at,
        "mbon_status": evaluation.mbon_status,
        "oig_status": evaluation.oig_status,
        "license_expiration_date": evaluation.license_expiration_date,
        "details": evaluation.details,
        "anchor_source": "ComplianceAuthorityAnchor",
    }


class ComplianceAuthorityAnchor:
    """Cross-layer bridge — persist encrypted audit rows and sync provider dispatch status."""

    def __init__(self, db: Session | None = None) -> None:
        self._db = db
        self._owns_session = False

    @property
    def db(self) -> Session:
        if self._db is None:
            try:
                from app.database import SessionLocal
            except Exception as exc:  # noqa: BLE001
                raise ComplianceAuthorityAnchorHardStop("database_session_import_failed") from exc
            self._db = SessionLocal()
            self._owns_session = True
        return self._db

    def close(self) -> None:
        if self._owns_session and self._db is not None:
            self._db.close()
            self._db = None
            self._owns_session = False

    def _resolve_provider_uuid(self, provider_id: str) -> UUID:
        token = str(provider_id or "").strip()
        if not token:
            raise ValueError("invalid_provider_token")
        try:
            return UUID(token)
        except ValueError as exc:
            raise ValueError("invalid_provider_token") from exc

    def _provider_exists(self, provider_uuid: UUID) -> bool:
        MarylandProvider = _import_maryland_provider()
        row = (
            self.db.query(MarylandProvider)
            .filter(MarylandProvider.provider_id == provider_uuid)
            .first()
        )
        return row is not None

    def _write_audit_ledger(self, provider_uuid: UUID, evaluation: Any) -> None:
        ComplianceAuditLedger = _import_compliance_audit_ledger()
        row = ComplianceAuditLedger(
            provider_id=str(provider_uuid),
            compliance_status=str(evaluation.compliance_status),
            is_eligible=bool(evaluation.is_eligible),
            checked_at=_parse_checked_at(evaluation.checked_at),
        )
        row.raw_payload_json = json.dumps(_evaluation_payload(evaluation), default=str)
        self.db.add(row)

    def _update_dispatch_status(self, provider_uuid: UUID, dispatch_status: str) -> int:
        MarylandProvider = _import_maryland_provider()
        stmt = (
            update(MarylandProvider)
            .where(MarylandProvider.provider_id == provider_uuid)
            .values(dispatch_status=str(dispatch_status))
        )
        result = self.db.execute(stmt)
        return int(result.rowcount or 0)

    def synchronize_gate_to_provider_status(
        self,
        provider_id: str,
        evaluation: Any,
    ) -> dict[str, Any]:
        """Record encrypted audit event and sync maryland_providers dispatch status."""
        DispatchComplianceEvaluation = _import_dispatch_compliance_evaluation()
        if not isinstance(evaluation, DispatchComplianceEvaluation):
            raise TypeError("evaluation must be DispatchComplianceEvaluation")

        compliance_status = str(evaluation.compliance_status or "").strip().upper()
        target_dispatch_status = _dispatch_status_for(compliance_status)
        if target_dispatch_status is None:
            logger.warning(
                "HIVE_COMPLIANCE_ANCHOR: unmapped compliance_status=%s provider=%s",
                compliance_status,
                provider_id,
            )
            return {
                "ok": False,
                "provider_id": str(provider_id),
                "compliance_status": compliance_status,
                "action": "status_unmapped",
                "message": f"compliance_status not anchored: {compliance_status}",
            }

        try:
            provider_uuid = self._resolve_provider_uuid(provider_id)
        except ValueError as exc:
            logger.warning(
                "HIVE_COMPLIANCE_ANCHOR: invalid provider token=%s error=%s",
                provider_id,
                exc,
            )
            return {
                "ok": False,
                "provider_id": str(provider_id),
                "compliance_status": compliance_status,
                "action": "invalid_provider_token",
                "message": "invalid provider token",
            }

        try:
            with self.db.begin():
                if not self._provider_exists(provider_uuid):
                    raise ValueError("provider_not_found")

                self._write_audit_ledger(provider_uuid, evaluation)
                updated = self._update_dispatch_status(provider_uuid, target_dispatch_status)
                if updated != 1:
                    raise ValueError("provider_dispatch_status_not_updated")

            logger.info(
                "HIVE_COMPLIANCE_ANCHOR: synced provider=%s compliance=%s dispatch=%s",
                provider_uuid,
                compliance_status,
                target_dispatch_status,
            )
            return {
                "ok": True,
                "provider_id": str(provider_uuid),
                "compliance_status": compliance_status,
                "dispatch_status": target_dispatch_status,
                "is_eligible": bool(evaluation.is_eligible),
                "action": "synchronized",
            }
        except SQLAlchemyError as exc:
            logger.warning(
                "HIVE_COMPLIANCE_ANCHOR: database sync failed provider=%s error=%s",
                provider_id,
                exc,
            )
            return {
                "ok": False,
                "provider_id": str(provider_id),
                "compliance_status": compliance_status,
                "action": "database_error",
                "message": str(exc),
            }
        except ValueError as exc:
            logger.warning(
                "HIVE_COMPLIANCE_ANCHOR: sync rollback provider=%s error=%s",
                provider_id,
                exc,
            )
            return {
                "ok": False,
                "provider_id": str(provider_id),
                "compliance_status": compliance_status,
                "action": "sync_rejected",
                "message": str(exc),
            }


if __name__ == "__main__":
    print("COMPILE_OK compliance_authority_anchor")
    anchor = ComplianceAuthorityAnchor(db=None)
    print(f"anchor={anchor.__class__.__name__}")
    print(f"status_map={list(_DISPATCH_STATUS_BY_COMPLIANCE.keys())}")
