"""Persistent compliance audit ledger — credential screening and Sentinel event trail."""

from __future__ import annotations

import base64
import logging
import os
import threading
import uuid
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base

logger = logging.getLogger(__name__)

_HIVE_FIELD_ENCRYPTION_KEY_ENV = "HIVE_FIELD_ENCRYPTION_KEY"
_FALLBACK_FERNET_KEY = base64.urlsafe_b64encode(
    b"hive_field_encryption_baseline_key"
).decode("ascii")

_keys_lock = threading.Lock()
_cached_fernet_keys: list[str] | None = None


def _load_fernet_module() -> tuple[Any, Any]:
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError as exc:
        raise RuntimeError("cryptography package required for compliance audit encryption") from exc
    return Fernet, InvalidToken


def _parse_fernet_key_stack() -> list[str]:
    """Parse comma-separated rotation keys — thread-safe cached read."""
    global _cached_fernet_keys
    with _keys_lock:
        if _cached_fernet_keys is not None:
            return list(_cached_fernet_keys)

        raw = str(os.environ.get(_HIVE_FIELD_ENCRYPTION_KEY_ENV) or "").strip()
        if raw:
            keys = [token.strip() for token in raw.split(",") if token.strip()]
        else:
            keys = []

        if not keys:
            keys = [_FALLBACK_FERNET_KEY]

        _cached_fernet_keys = keys
        return list(_cached_fernet_keys)


def _primary_fernet_cipher() -> Any:
    Fernet, _ = _load_fernet_module()
    primary_key = _parse_fernet_key_stack()[0]
    return Fernet(primary_key.encode("utf-8"))


def _decrypt_with_key_stack(ciphertext: str) -> str | None:
    Fernet, InvalidToken = _load_fernet_module()
    keys = _parse_fernet_key_stack()
    for index, key in enumerate(keys):
        try:
            cipher = Fernet(key.encode("utf-8"))
            decrypted = cipher.decrypt(ciphertext.encode("utf-8"))
            return decrypted.decode("utf-8")
        except InvalidToken:
            logger.debug(
                "compliance_audit_ledger decrypt InvalidToken — cycling key index=%s",
                index,
            )
            continue
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "compliance_audit_ledger decrypt fault key index=%s error=%s",
                index,
                exc,
            )
            continue
    return None


class ComplianceAuditLedger(Base):
    """Immutable-style audit row for provider credential and Sentinel guard outcomes."""

    __tablename__ = "compliance_audit_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(String(128), nullable=True)
    timesheet_token = Column(String(128), nullable=True)
    compliance_status = Column(String(64), nullable=False)
    is_eligible = Column(Boolean, nullable=False, default=False)
    checked_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    _encrypted_payload_json = Column("raw_payload_json", Text, nullable=True)

    @property
    def raw_payload_json(self) -> str | None:
        stored = self._encrypted_payload_json
        if stored is None:
            return None
        token = str(stored)
        if not token:
            return token

        decrypted = _decrypt_with_key_stack(token)
        if decrypted is not None:
            return decrypted

        logger.debug(
            "compliance_audit_ledger payload decrypt fallback (legacy/plaintext): key stack exhausted"
        )
        return token

    @raw_payload_json.setter
    def raw_payload_json(self, value: str | None) -> None:
        if value is None:
            self._encrypted_payload_json = None
            return
        plaintext = str(value)
        if not plaintext:
            self._encrypted_payload_json = plaintext
            return
        encrypted = _primary_fernet_cipher().encrypt(plaintext.encode("utf-8")).decode("utf-8")
        self._encrypted_payload_json = encrypted


# Alias for directive naming compatibility.
ComplianceAuditLedgerModel = ComplianceAuditLedger


if __name__ == "__main__":
    print("COMPILE_OK compliance_audit_ledger")
    print(f"table={ComplianceAuditLedger.__tablename__}")
    print(f"key_stack_size={len(_parse_fernet_key_stack())}")
    row = ComplianceAuditLedger(
        compliance_status="CREDENTIALS_PASSED",
        is_eligible=True,
    )
    sample = '{"registry":"MBON","status":"ACTIVE"}'
    row.raw_payload_json = sample
    stored = row._encrypted_payload_json
    roundtrip = row.raw_payload_json
    print(f"encrypted={stored != sample} roundtrip_ok={roundtrip == sample}")
    row._encrypted_payload_json = sample
    legacy = row.raw_payload_json
    print(f"legacy_fallback_ok={legacy == sample}")
