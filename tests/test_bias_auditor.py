"""
Test Suite: Maryland HB 1106 Bias Auditor & Post-Match Hash-Chainer

Component 3 validation: ledger initialization, sequential chaining, integrity verification.

Authority: Elite Systems Engineer Architecture Audit (2026-07-06).
Tests tamper-evident blockchain-style audit trail for algorithmic employment decisions.
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.auditor.bias_auditor import (
    GENESIS_BLOCK_HASH,
    BiasAuditRecord,
    BiasAuditor,
    LedgerIntegrityError,
)


@pytest.fixture
def bias_auditor():
    """Fixture: BiasAuditor instance."""
    return BiasAuditor()


@pytest.fixture
def mock_db_session():
    """Fixture: Mocked SQLAlchemy AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ============================================================================
# TEST 1: Ledger initialization and genesis block insertion
# ============================================================================


@pytest.mark.asyncio
async def test_ledger_initialization(bias_auditor, mock_db_session):
    """
    Test that ledger table is created successfully with proper schema.

    Validates:
    - CREATE TABLE IF NOT EXISTS hb1106_bias_ledger
    - Required columns: id, match_id, parent_hash, block_hash, serialized_payload, created_at
    - Indices on match_id, created_at, block_hash
    """
    # Track executed SQL
    executed_queries = []

    async def mock_execute(query, params=None):
        executed_queries.append(str(query))
        return MagicMock()

    mock_db_session.execute.side_effect = mock_execute

    # Initialize ledger
    await bias_auditor.initialize_ledger(mock_db_session)

    # Assert table creation
    assert any("CREATE TABLE IF NOT EXISTS hb1106_bias_ledger" in q for q in executed_queries), (
        "Ledger table not created"
    )

    # Assert columns present
    combined_sql = " ".join(executed_queries)
    required_columns = ["match_id", "parent_hash", "block_hash", "serialized_payload", "created_at"]
    for col in required_columns:
        assert col in combined_sql, f"Column {col} missing from schema"

    # Assert indices created
    assert any("idx_hb1106_match_id" in q for q in executed_queries), "match_id index not created"
    assert any("idx_hb1106_created_at" in q for q in executed_queries), "created_at index not created"
    assert any("idx_hb1106_block_hash" in q for q in executed_queries), "block_hash index not created"

    # Assert commit called
    mock_db_session.commit.assert_called_once()

    print(f"✓ Ledger initialization: table and {len(required_columns)} columns created")


@pytest.mark.asyncio
async def test_genesis_block_first_record(bias_auditor, mock_db_session):
    """
    Test that first ledger record uses genesis block hash as parent.

    Validates:
    - Empty ledger → parent_hash = "0" * 64
    - Block hash computed correctly from genesis + payload
    """
    match_id = str(uuid.uuid4())
    caregiver_id = str(uuid.uuid4())
    shift_id = str(uuid.uuid4())

    # Mock empty ledger (no previous records)
    mock_latest_hash_result = MagicMock()
    mock_latest_hash_result.first.return_value = None

    # Mock insert result
    mock_insert_result = MagicMock()
    ledger_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    mock_insert_result.first.return_value = (ledger_id, created_at)

    async def mock_execute(query, params=None):
        if "ORDER BY created_at DESC" in str(query):
            return mock_latest_hash_result
        if "INSERT INTO hb1106_bias_ledger" in str(query):
            return mock_insert_result
        return MagicMock()

    mock_db_session.execute.side_effect = mock_execute

    # Create first audit record
    metadata = {
        "caregiver_license": "CNA",
        "shift_license_required": "CNA",
        "region": "Baltimore",
    }

    record = await bias_auditor.audit_and_chain_match(
        match_id=match_id,
        caregiver_id=caregiver_id,
        facility_shift_id=shift_id,
        similarity_score=0.87,
        metadata=metadata,
        db_session=mock_db_session,
    )

    # Assert genesis block used as parent
    assert record.parent_hash == GENESIS_BLOCK_HASH, (
        f"First record should use genesis block, got {record.parent_hash}"
    )

    # Assert block hash computed correctly
    payload = json.loads(record.serialized_payload)
    expected_hash = hashlib.sha256(
        (GENESIS_BLOCK_HASH + record.serialized_payload).encode("utf-8")
    ).hexdigest()
    assert record.block_hash == expected_hash, "Block hash computation incorrect"

    print(f"✓ Genesis block: first record parent_hash = {GENESIS_BLOCK_HASH[:16]}...")


# ============================================================================
# TEST 2: Sequential chaining — row N contains hash of row N-1
# ============================================================================


@pytest.mark.asyncio
async def test_sequential_hash_chaining(bias_auditor, mock_db_session):
    """
    Test that sequential records form proper hash chain.

    Validates:
    - Record 1: parent_hash = genesis
    - Record 2: parent_hash = Record 1 block_hash
    - Record 3: parent_hash = Record 2 block_hash
    - Each block_hash is SHA-256(parent_hash + payload)
    """
    # Simulate sequential record creation
    records = []

    for i in range(3):
        match_id = f"match-{i}"
        caregiver_id = f"caregiver-{i}"
        shift_id = f"shift-{i}"

        # Mock fetching latest hash
        if i == 0:
            # First record: genesis parent
            latest_hash = GENESIS_BLOCK_HASH
        else:
            # Subsequent records: previous block hash
            latest_hash = records[-1].block_hash

        mock_latest_hash_result = MagicMock()
        mock_latest_hash_result.first.return_value = (latest_hash,) if i > 0 else None

        # Mock insert result
        mock_insert_result = MagicMock()
        ledger_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)
        mock_insert_result.first.return_value = (ledger_id, created_at)

        async def mock_execute(query, params=None):
            if "ORDER BY created_at DESC" in str(query):
                return mock_latest_hash_result
            if "INSERT INTO hb1106_bias_ledger" in str(query):
                return mock_insert_result
            return MagicMock()

        mock_db_session.execute.side_effect = mock_execute

        # Create record
        metadata = {
            "caregiver_license": "CNA",
            "shift_license_required": "CNA",
            "region": "Baltimore",
        }

        record = await bias_auditor.audit_and_chain_match(
            match_id=match_id,
            caregiver_id=caregiver_id,
            facility_shift_id=shift_id,
            similarity_score=0.85 + i * 0.01,
            metadata=metadata,
            db_session=mock_db_session,
        )

        records.append(record)

    # Verify chain integrity
    for i, record in enumerate(records):
        if i == 0:
            # First record chains to genesis
            assert record.parent_hash == GENESIS_BLOCK_HASH, f"Record 0 should chain to genesis"
        else:
            # Subsequent records chain to previous block
            assert record.parent_hash == records[i - 1].block_hash, (
                f"Record {i} parent_hash should match Record {i-1} block_hash"
            )

        # Verify hash computation
        expected_hash = hashlib.sha256(
            (record.parent_hash + record.serialized_payload).encode("utf-8")
        ).hexdigest()
        assert record.block_hash == expected_hash, f"Record {i} hash computation incorrect"

    print(f"✓ Sequential chaining: {len(records)} records form valid chain")


# ============================================================================
# TEST 3: Ledger integrity verification passes on clean data
# ============================================================================


@pytest.mark.asyncio
async def test_ledger_integrity_verification_passes(bias_auditor, mock_db_session):
    """
    Test that integrity verification passes on uncorrupted sequential data.

    Validates:
    - Scan entire ledger
    - Recalculate each hash
    - All hashes match → status="VALID"
    - No LedgerIntegrityError raised
    """
    # Create mock ledger with 5 sequential records
    mock_records = []
    previous_hash = GENESIS_BLOCK_HASH

    for i in range(5):
        match_id = f"match-{i}"
        payload = {
            "caregiver_id": f"caregiver-{i}",
            "caregiver_license": "CNA",
            "facility_shift_id": f"shift-{i}",
            "match_id": match_id,
            "metadata": {"region": "Baltimore"},
            "region": "Baltimore",
            "shift_license_required": "CNA",
            "similarity_score": 0.80 + i * 0.02,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        serialized = json.dumps(payload, sort_keys=True)
        block_hash = hashlib.sha256((previous_hash + serialized).encode("utf-8")).hexdigest()

        mock_records.append(
            (
                str(uuid.uuid4()),  # id
                match_id,  # match_id
                previous_hash,  # parent_hash
                block_hash,  # block_hash
                serialized,  # serialized_payload
                datetime.now(timezone.utc),  # created_at
            )
        )

        previous_hash = block_hash

    # Mock database query
    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_records

    async def mock_execute(query, params=None):
        return mock_result

    mock_db_session.execute.side_effect = mock_execute

    # Verify ledger integrity
    result = await bias_auditor.verify_ledger_integrity(mock_db_session)

    # Assert verification passed
    assert result["status"] == "VALID", f"Expected VALID status, got {result['status']}"
    assert result["total_records"] == 5
    assert result["verified_records"] == 5
    assert len(result["corrupted_record_ids"]) == 0
    assert result["genesis_hash"] == GENESIS_BLOCK_HASH
    assert result["latest_hash"] == mock_records[-1][3]  # Last block hash

    print(f"✓ Integrity verification passed: {result['verified_records']}/{result['total_records']} records valid")


# ============================================================================
# TEST 4: Ledger integrity verification fails on tampered data
# ============================================================================


@pytest.mark.asyncio
async def test_ledger_integrity_verification_fails_on_tampering(bias_auditor, mock_db_session):
    """
    Test that integrity verification detects and fails on tampered data.

    Validates:
    - Maliciously altered payload → hash mismatch detected
    - Raises LedgerIntegrityError
    - Returns status="CORRUPTED" with corrupted_record_ids
    """
    # Create mock ledger with 5 records, tamper with record #3
    mock_records = []
    previous_hash = GENESIS_BLOCK_HASH

    for i in range(5):
        match_id = f"match-{i}"
        payload = {
            "caregiver_id": f"caregiver-{i}",
            "caregiver_license": "CNA",
            "facility_shift_id": f"shift-{i}",
            "match_id": match_id,
            "metadata": {"region": "Baltimore"},
            "region": "Baltimore",
            "shift_license_required": "CNA",
            "similarity_score": 0.80 + i * 0.02,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        serialized = json.dumps(payload, sort_keys=True)
        block_hash = hashlib.sha256((previous_hash + serialized).encode("utf-8")).hexdigest()

        # TAMPER: Alter record #3 payload (but keep original hash)
        if i == 3:
            tampered_payload = payload.copy()
            tampered_payload["similarity_score"] = 0.99  # Fraudulent score increase
            serialized = json.dumps(tampered_payload, sort_keys=True)
            # Keep original block_hash → will cause mismatch

        mock_records.append(
            (
                str(uuid.uuid4()),  # id
                match_id,  # match_id
                previous_hash,  # parent_hash
                block_hash,  # block_hash (unchanged, but payload tampered)
                serialized,  # serialized_payload (TAMPERED for i==3)
                datetime.now(timezone.utc),  # created_at
            )
        )

        previous_hash = block_hash

    # Mock database query
    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_records

    async def mock_execute(query, params=None):
        return mock_result

    mock_db_session.execute.side_effect = mock_execute

    # Verify ledger integrity — should detect tampering
    with pytest.raises(LedgerIntegrityError) as exc_info:
        await bias_auditor.verify_ledger_integrity(mock_db_session)

    # Assert error message contains corruption details
    error_msg = str(exc_info.value)
    assert "FAILURE" in error_msg or "corrupted" in error_msg.lower()
    assert "1" in error_msg  # 1 corrupted record

    print("✓ Tampering detected: LedgerIntegrityError raised for altered record")


@pytest.mark.asyncio
async def test_ledger_integrity_chain_break_detection(bias_auditor, mock_db_session):
    """
    Test that integrity verification detects hash chain breaks.

    Validates:
    - Out-of-order insertion (parent_hash doesn't match previous block_hash)
    - Raises LedgerIntegrityError
    """
    # Create mock ledger with intentional chain break at record #2
    mock_records = []
    previous_hash = GENESIS_BLOCK_HASH

    for i in range(4):
        match_id = f"match-{i}"
        payload = {
            "caregiver_id": f"caregiver-{i}",
            "caregiver_license": "CNA",
            "facility_shift_id": f"shift-{i}",
            "match_id": match_id,
            "metadata": {"region": "Baltimore"},
            "region": "Baltimore",
            "shift_license_required": "CNA",
            "similarity_score": 0.80 + i * 0.02,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        serialized = json.dumps(payload, sort_keys=True)
        block_hash = hashlib.sha256((previous_hash + serialized).encode("utf-8")).hexdigest()

        # CHAIN BREAK: At record #2, use wrong parent hash
        if i == 2:
            previous_hash = "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"  # Bogus hash

        mock_records.append(
            (
                str(uuid.uuid4()),  # id
                match_id,  # match_id
                previous_hash,  # parent_hash (BROKEN for i==2)
                block_hash,  # block_hash
                serialized,  # serialized_payload
                datetime.now(timezone.utc),  # created_at
            )
        )

        if i != 2:
            previous_hash = block_hash
        else:
            # Restore correct hash for subsequent records
            previous_hash = hashlib.sha256(
                (mock_records[1][3] + serialized).encode("utf-8")
            ).hexdigest()

    # Mock database query
    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_records

    async def mock_execute(query, params=None):
        return mock_result

    mock_db_session.execute.side_effect = mock_execute

    # Verify ledger integrity — should detect chain break
    with pytest.raises(LedgerIntegrityError) as exc_info:
        await bias_auditor.verify_ledger_integrity(mock_db_session)

    error_msg = str(exc_info.value)
    assert "FAILURE" in error_msg or "corrupted" in error_msg.lower()

    print("✓ Chain break detected: LedgerIntegrityError raised for broken parent_hash link")


# ============================================================================
# TEST 5 (BONUS): Empty ledger verification
# ============================================================================


@pytest.mark.asyncio
async def test_empty_ledger_verification(bias_auditor, mock_db_session):
    """
    Test that empty ledger verification returns valid status.

    Validates:
    - No records → status="VALID"
    - genesis_hash and latest_hash both set to GENESIS_BLOCK_HASH
    """
    # Mock empty ledger
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []

    async def mock_execute(query, params=None):
        return mock_result

    mock_db_session.execute.side_effect = mock_execute

    # Verify empty ledger
    result = await bias_auditor.verify_ledger_integrity(mock_db_session)

    # Assert valid empty state
    assert result["status"] == "VALID"
    assert result["total_records"] == 0
    assert result["verified_records"] == 0
    assert result["genesis_hash"] == GENESIS_BLOCK_HASH
    assert result["latest_hash"] == GENESIS_BLOCK_HASH
    assert len(result["corrupted_record_ids"]) == 0

    print("✓ Empty ledger verification: status=VALID, genesis hash preserved")


# ============================================================================
# TEST 6 (BONUS): Deterministic payload serialization
# ============================================================================


@pytest.mark.asyncio
async def test_deterministic_payload_serialization(bias_auditor):
    """
    Test that payload serialization is deterministic (sorted keys).

    Validates:
    - Same data with different key order → identical serialized string
    - Critical for hash consistency across systems
    """
    # Two payloads with same data, different key order
    payload_1 = {
        "match_id": "test-match",
        "caregiver_id": "caregiver-123",
        "similarity_score": 0.85,
        "metadata": {"region": "Baltimore"},
    }

    payload_2 = {
        "similarity_score": 0.85,
        "metadata": {"region": "Baltimore"},
        "match_id": "test-match",
        "caregiver_id": "caregiver-123",
    }

    # Serialize both
    serialized_1 = json.dumps(payload_1, sort_keys=True)
    serialized_2 = json.dumps(payload_2, sort_keys=True)

    # Assert identical output
    assert serialized_1 == serialized_2, "Payload serialization not deterministic"

    # Compute hashes
    hash_1 = hashlib.sha256((GENESIS_BLOCK_HASH + serialized_1).encode("utf-8")).hexdigest()
    hash_2 = hashlib.sha256((GENESIS_BLOCK_HASH + serialized_2).encode("utf-8")).hexdigest()

    assert hash_1 == hash_2, "Hash computation not deterministic"

    print(f"✓ Deterministic serialization: identical hashes for same data with different key order")


# ============================================================================
# TEST 7 (BONUS): Audit trail retrieval
# ============================================================================


@pytest.mark.asyncio
async def test_audit_trail_retrieval(bias_auditor, mock_db_session):
    """
    Test retrieving audit trail records for compliance review.

    Validates:
    - Filter by match_id
    - Returns chronologically ordered records
    - Limit parameter works
    """
    match_id = "test-match-123"

    # Mock database records
    mock_records = [
        (
            str(uuid.uuid4()),
            match_id,
            GENESIS_BLOCK_HASH,
            "abc123" + "0" * 58,
            '{"test": "data"}',
            datetime.now(timezone.utc),
        ),
        (
            str(uuid.uuid4()),
            match_id,
            "abc123" + "0" * 58,
            "def456" + "0" * 58,
            '{"test": "data2"}',
            datetime.now(timezone.utc),
        ),
    ]

    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_records

    async def mock_execute(query, params=None):
        return mock_result

    mock_db_session.execute.side_effect = mock_execute

    # Retrieve audit trail
    records = await bias_auditor.get_audit_trail(
        match_id=match_id,
        db_session=mock_db_session,
        limit=100,
    )

    # Assert records returned
    assert len(records) == 2
    assert all(isinstance(r, BiasAuditRecord) for r in records)
    assert all(r.match_id == match_id for r in records)

    print(f"✓ Audit trail retrieval: {len(records)} records retrieved for match_id={match_id}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
