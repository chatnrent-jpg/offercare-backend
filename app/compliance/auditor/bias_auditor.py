"""
Maryland HB 1106 Bias Auditor & Post-Match Hash-Chainer

Component 3: Tamper-evident blockchain-style ledger for algorithmic employment decisions.
Satisfies Maryland AEDT (Algorithmic Employment Decision Tracking) statutory requirements.

Authority: MD HB 1106 § 3-601 — Bias Audit and Record Retention (2024).
Implements SHA-256 sequential hash-chaining with genesis block pattern.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Genesis block hash — 64-character zero string (first ledger entry parent)
GENESIS_BLOCK_HASH = "0" * 64


class LedgerIntegrityError(Exception):
    """
    Critical compliance error raised when hash-chain validation fails.

    Indicates potential data tampering or ledger corruption.
    Maryland HB 1106 requires immediate escalation to compliance officer.
    """

    pass


@dataclass
class BiasAuditRecord:
    """Single entry in the HB 1106 bias audit ledger."""

    ledger_id: str
    match_id: str
    parent_hash: str
    block_hash: str
    serialized_payload: str
    created_at: datetime


class BiasAuditor:
    """
    Maryland HB 1106 Bias Auditor with cryptographic hash-chaining.

    Implements tamper-evident sequential ledger for algorithmic matching decisions.
    Each record contains SHA-256 hash of previous record, forming immutable audit chain.

    Compliance mandate: All AI-driven employment decisions must be logged with:
    - Candidate demographics (license type, region, protected attributes)
    - Decision criteria (similarity scores, ranking factors)
    - Temporal metadata (timestamp, decision context)
    - Cryptographic proof-of-sequence (parent hash → block hash)
    """

    def __init__(self):
        """Initialize HB 1106 bias auditor."""
        pass

    async def initialize_ledger(self, db_session: AsyncSession) -> None:
        """
        Initialize hb1106_bias_ledger table if not exists.

        Creates:
        - Ledger table with UUID primary key
        - Index on match_id for fast lookups
        - Index on created_at for chronological scanning
        - Index on block_hash for integrity verification

        Args:
            db_session: SQLAlchemy AsyncSession
        """
        try:
            create_table_query = text("""
                CREATE TABLE IF NOT EXISTS hb1106_bias_ledger (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    match_id VARCHAR(255) NOT NULL,
                    parent_hash CHAR(64) NOT NULL,
                    block_hash CHAR(64) NOT NULL UNIQUE,
                    serialized_payload TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_hb1106_match_id 
                ON hb1106_bias_ledger(match_id);

                CREATE INDEX IF NOT EXISTS idx_hb1106_created_at 
                ON hb1106_bias_ledger(created_at);

                CREATE INDEX IF NOT EXISTS idx_hb1106_block_hash 
                ON hb1106_bias_ledger(block_hash);
            """)

            await db_session.execute(create_table_query)
            await db_session.commit()
            logger.info("HB 1106 bias audit ledger initialized successfully")

        except Exception as exc:
            logger.error(f"Failed to initialize bias audit ledger: {exc}")
            await db_session.rollback()
            raise

    async def audit_and_chain_match(
        self,
        *,
        match_id: str,
        caregiver_id: str,
        facility_shift_id: str,
        similarity_score: float,
        metadata: dict[str, Any],
        db_session: AsyncSession,
    ) -> BiasAuditRecord:
        """
        Audit algorithmic matching decision and append to hash-chained ledger.

        Creates tamper-evident record by:
        1. Building canonical JSON payload (alphabetically sorted keys)
        2. Fetching parent hash from most recent ledger entry
        3. Computing block hash: SHA-256(parent_hash + payload)
        4. Inserting new record with cryptographic chain link

        Args:
            match_id: Unique identifier for this match decision
            caregiver_id: UUID of caregiver being matched
            facility_shift_id: UUID of facility shift
            similarity_score: Semantic similarity score (0.0 to 1.0)
            metadata: Additional criteria (license types, region, demographics)
            db_session: SQLAlchemy AsyncSession

        Returns:
            BiasAuditRecord with computed hashes and ledger ID

        Raises:
            Exception: Database write failure or hash computation error
        """
        try:
            # Build canonical payload — alphabetically sorted keys for determinism
            payload = {
                "caregiver_id": caregiver_id,
                "caregiver_license": metadata.get("caregiver_license", "UNKNOWN"),
                "facility_shift_id": facility_shift_id,
                "match_id": match_id,
                "metadata": metadata,
                "region": metadata.get("region", "UNKNOWN"),
                "shift_license_required": metadata.get("shift_license_required", "UNKNOWN"),
                "similarity_score": similarity_score,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Serialize with sorted keys for deterministic string representation
            serialized_payload = json.dumps(payload, sort_keys=True)

            # Fetch parent hash from most recent ledger entry
            parent_hash = await self._get_latest_block_hash(db_session)

            # Compute block hash: SHA-256(parent_hash + payload)
            block_hash = self._compute_block_hash(parent_hash, serialized_payload)

            # Insert new record into ledger
            insert_query = text("""
                INSERT INTO hb1106_bias_ledger 
                (match_id, parent_hash, block_hash, serialized_payload, created_at)
                VALUES (:match_id, :parent_hash, :block_hash, :serialized_payload, NOW())
                RETURNING id, created_at;
            """)

            result = await db_session.execute(
                insert_query,
                {
                    "match_id": match_id,
                    "parent_hash": parent_hash,
                    "block_hash": block_hash,
                    "serialized_payload": serialized_payload,
                },
            )
            await db_session.commit()

            row = result.first()
            ledger_id = str(row[0])
            created_at = row[1]

            logger.info(
                f"HB 1106 audit record created: match_id={match_id}, "
                f"block_hash={block_hash[:16]}..., parent={parent_hash[:16]}..."
            )

            return BiasAuditRecord(
                ledger_id=ledger_id,
                match_id=match_id,
                parent_hash=parent_hash,
                block_hash=block_hash,
                serialized_payload=serialized_payload,
                created_at=created_at,
            )

        except Exception as exc:
            logger.error(f"Failed to audit and chain match: {exc}")
            await db_session.rollback()
            raise

    async def verify_ledger_integrity(self, db_session: AsyncSession) -> dict[str, Any]:
        """
        Verify complete integrity of HB 1106 bias audit ledger.

        Scans entire ledger sequentially, recalculating each block hash and
        verifying it matches stored value. Detects any tampering, corruption,
        or out-of-order modifications.

        Algorithm:
        1. Fetch all ledger entries ordered by created_at
        2. For each entry:
           - Recalculate block_hash from parent_hash + serialized_payload
           - Compare with stored block_hash
           - Verify parent_hash matches previous entry's block_hash
        3. If any mismatch detected → raise LedgerIntegrityError

        Args:
            db_session: SQLAlchemy AsyncSession

        Returns:
            Dict with verification results:
            {
                "status": "VALID" | "CORRUPTED",
                "total_records": int,
                "verified_records": int,
                "genesis_hash": str,
                "latest_hash": str,
                "corrupted_record_ids": list[str],
            }

        Raises:
            LedgerIntegrityError: Hash mismatch detected (data tampering)
        """
        try:
            # Fetch all ledger entries in chronological order
            query = text("""
                SELECT id, match_id, parent_hash, block_hash, serialized_payload, created_at
                FROM hb1106_bias_ledger
                ORDER BY created_at ASC, id ASC;
            """)

            result = await db_session.execute(query)
            rows = result.fetchall()

            if not rows:
                logger.info("HB 1106 ledger is empty — no records to verify")
                return {
                    "status": "VALID",
                    "total_records": 0,
                    "verified_records": 0,
                    "genesis_hash": GENESIS_BLOCK_HASH,
                    "latest_hash": GENESIS_BLOCK_HASH,
                    "corrupted_record_ids": [],
                }

            # Verify sequential integrity
            verified_count = 0
            corrupted_ids = []
            previous_block_hash = None

            for idx, row in enumerate(rows):
                ledger_id = str(row[0])
                match_id = row[1]
                stored_parent_hash = row[2]
                stored_block_hash = row[3]
                serialized_payload = row[4]
                created_at = row[5]

                # Verify parent hash matches previous block
                if idx == 0:
                    # First record must have genesis block as parent
                    if stored_parent_hash != GENESIS_BLOCK_HASH:
                        logger.error(
                            f"Genesis block parent hash mismatch: "
                            f"expected {GENESIS_BLOCK_HASH}, got {stored_parent_hash}"
                        )
                        corrupted_ids.append(ledger_id)
                        continue
                else:
                    # Subsequent records must chain to previous block
                    if stored_parent_hash != previous_block_hash:
                        logger.error(
                            f"Chain break detected at record {ledger_id}: "
                            f"parent_hash={stored_parent_hash[:16]}... does not match "
                            f"previous block_hash={previous_block_hash[:16] if previous_block_hash else 'None'}..."
                        )
                        corrupted_ids.append(ledger_id)
                        continue

                # Recalculate block hash and verify
                expected_block_hash = self._compute_block_hash(stored_parent_hash, serialized_payload)

                if expected_block_hash != stored_block_hash:
                    logger.error(
                        f"Hash mismatch at record {ledger_id}: "
                        f"expected {expected_block_hash[:16]}..., got {stored_block_hash[:16]}..."
                    )
                    corrupted_ids.append(ledger_id)
                    continue

                # Record verified
                verified_count += 1
                previous_block_hash = stored_block_hash

            # Final verification result
            total_records = len(rows)
            status = "VALID" if verified_count == total_records else "CORRUPTED"

            result_summary = {
                "status": status,
                "total_records": total_records,
                "verified_records": verified_count,
                "genesis_hash": GENESIS_BLOCK_HASH,
                "latest_hash": previous_block_hash or GENESIS_BLOCK_HASH,
                "corrupted_record_ids": corrupted_ids,
            }

            if status == "CORRUPTED":
                error_msg = (
                    f"HB 1106 Ledger Integrity FAILURE: {len(corrupted_ids)} corrupted records detected. "
                    f"IDs: {corrupted_ids[:5]}{'...' if len(corrupted_ids) > 5 else ''}"
                )
                logger.critical(error_msg)
                raise LedgerIntegrityError(error_msg)

            logger.info(f"HB 1106 ledger integrity verified: {verified_count}/{total_records} records valid")
            return result_summary

        except LedgerIntegrityError:
            raise
        except Exception as exc:
            logger.error(f"Ledger integrity verification failed: {exc}")
            raise

    async def _get_latest_block_hash(self, db_session: AsyncSession) -> str:
        """
        Fetch the block_hash of the most recent ledger entry.

        Returns:
            Latest block hash, or GENESIS_BLOCK_HASH if ledger is empty
        """
        query = text("""
            SELECT block_hash
            FROM hb1106_bias_ledger
            ORDER BY created_at DESC, id DESC
            LIMIT 1;
        """)

        result = await db_session.execute(query)
        row = result.first()

        if row:
            return row[0]

        # Ledger is empty — return genesis block hash
        logger.debug("Ledger empty — using genesis block hash")
        return GENESIS_BLOCK_HASH

    def _compute_block_hash(self, parent_hash: str, serialized_payload: str) -> str:
        """
        Compute SHA-256 block hash from parent hash and payload.

        Hash computation:
        SHA-256(parent_hash + serialized_payload)

        Args:
            parent_hash: Hash of previous block (or genesis hash)
            serialized_payload: JSON string of current match data

        Returns:
            64-character hexadecimal SHA-256 hash
        """
        combined = parent_hash + serialized_payload
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    async def get_audit_trail(
        self,
        *,
        match_id: str | None = None,
        caregiver_id: str | None = None,
        db_session: AsyncSession,
        limit: int = 100,
    ) -> list[BiasAuditRecord]:
        """
        Retrieve audit trail records for compliance review.

        Args:
            match_id: Optional filter by specific match
            caregiver_id: Optional filter by caregiver
            db_session: SQLAlchemy AsyncSession
            limit: Maximum records to return

        Returns:
            List of BiasAuditRecord objects
        """
        # Build query with optional filters
        where_clauses = []
        params = {"limit": limit}

        if match_id:
            where_clauses.append("match_id = :match_id")
            params["match_id"] = match_id

        if caregiver_id:
            where_clauses.append("serialized_payload LIKE :caregiver_pattern")
            params["caregiver_pattern"] = f"%{caregiver_id}%"

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        query = text(f"""
            SELECT id, match_id, parent_hash, block_hash, serialized_payload, created_at
            FROM hb1106_bias_ledger
            {where_sql}
            ORDER BY created_at DESC
            LIMIT :limit;
        """)

        result = await db_session.execute(query, params)
        rows = result.fetchall()

        return [
            BiasAuditRecord(
                ledger_id=str(row[0]),
                match_id=row[1],
                parent_hash=row[2],
                block_hash=row[3],
                serialized_payload=row[4],
                created_at=row[5],
            )
            for row in rows
        ]
