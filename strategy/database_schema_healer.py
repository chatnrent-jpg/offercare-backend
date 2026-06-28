"""Database schema healer — autonomous boot-time verification for audit tables."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

_AUDIT_TABLE_NAME = "compliance_audit_ledger"
_HEALTH_OK_MESSAGE = "HIVE_DB_HEALTH: compliance_audit_ledger table verified."


class DatabaseSchemaHealerHardStop(RuntimeError):
    """Hive halt — schema healer import or compile failure."""


class DatabaseSchemaHealer:
    """Boot resilience utility — verifies and heals missing compliance audit tables."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine

    def _lazy_engine(self) -> Engine:
        if self._engine is not None:
            return self._engine
        try:
            from app.database import engine as default_engine
        except Exception as exc:  # noqa: BLE001
            raise DatabaseSchemaHealerHardStop("database_engine_import_failed") from exc
        self._engine = default_engine
        return self._engine

    def _import_compliance_audit_ledger(self) -> Any:
        try:
            from app.models.compliance_audit_ledger import ComplianceAuditLedger
        except ImportError:
            import importlib.util

            module_path = Path(__file__).resolve().parents[1] / "app" / "models" / "compliance_audit_ledger.py"
            spec = importlib.util.spec_from_file_location("compliance_audit_ledger", module_path)
            if spec is None or spec.loader is None:
                raise DatabaseSchemaHealerHardStop("compliance_audit_ledger_import_failed") from None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.ComplianceAuditLedger
        return ComplianceAuditLedger

    def _audit_table_exists(self, bind: Engine) -> bool:
        inspector = inspect(bind)
        return _AUDIT_TABLE_NAME in set(inspector.get_table_names())

    def verify_and_heal_audit_tables(self) -> dict[str, Any]:
        """Verify compliance audit ledger table; create in isolation if missing."""
        try:
            engine = self._lazy_engine()
            ledger_model = self._import_compliance_audit_ledger()

            with engine.begin() as connection:
                if self._audit_table_exists(connection):
                    logger.info(_HEALTH_OK_MESSAGE)
                    return {
                        "ok": True,
                        "table": _AUDIT_TABLE_NAME,
                        "action": "verified",
                        "message": _HEALTH_OK_MESSAGE,
                    }

                try:
                    from app.database import Base

                    Base.metadata.create_all(
                        bind=connection,
                        tables=[ledger_model.__table__],
                        checkfirst=True,
                    )
                except SQLAlchemyError as exc:
                    logger.warning(
                        "HIVE_DB_ALERT: compliance_audit_ledger heal failed — boot continues: %s",
                        exc,
                    )
                    return {
                        "ok": False,
                        "table": _AUDIT_TABLE_NAME,
                        "action": "heal_failed",
                        "message": str(exc),
                    }

            if self._audit_table_exists(engine):
                logger.info("HIVE_DB_HEALTH: compliance_audit_ledger table created and verified.")
                return {
                    "ok": True,
                    "table": _AUDIT_TABLE_NAME,
                    "action": "created",
                    "message": "HIVE_DB_HEALTH: compliance_audit_ledger table created and verified.",
                }

            logger.warning(
                "HIVE_DB_ALERT: compliance_audit_ledger still missing after heal attempt — boot continues."
            )
            return {
                "ok": False,
                "table": _AUDIT_TABLE_NAME,
                "action": "missing_after_heal",
                "message": "compliance_audit_ledger missing after heal attempt",
            }
        except SQLAlchemyError as exc:
            logger.warning(
                "HIVE_DB_ALERT: audit table verification skipped — boot continues: %s",
                exc,
            )
            return {
                "ok": False,
                "table": _AUDIT_TABLE_NAME,
                "action": "verification_skipped",
                "message": str(exc),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "HIVE_DB_ALERT: schema healer fault — boot continues: %s",
                exc,
            )
            return {
                "ok": False,
                "table": _AUDIT_TABLE_NAME,
                "action": "healer_fault",
                "message": str(exc),
            }


if __name__ == "__main__":
    print("COMPILE_OK database_schema_healer")
    healer = DatabaseSchemaHealer(engine=None)
    print(f"healer={healer.__class__.__name__} table={_AUDIT_TABLE_NAME}")
