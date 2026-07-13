"""
Test Suite: Unified Matching Engine Integration

Deep Cleanroom Validation — Elite Systems Engineer (2026-07-06)
Tests complete workflow integration of all 4 components.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MarylandProvider
from app.services.unified_matching_engine import UnifiedMatchingEngine
from app.services.vms import VMSPayload


@pytest.fixture
def matching_engine():
    """Fixture: UnifiedMatchingEngine instance."""
    return UnifiedMatchingEngine()


@pytest.fixture
def mock_db_session():
    """Fixture: Mocked SQLAlchemy AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def sample_caregiver():
    """Fixture: Sample MarylandProvider."""
    return MarylandProvider(
        provider_id=uuid.uuid4(),
        email="test@vettedme.ai",
        full_name="Test Caregiver",
        credential_type="CNA",
        state="MD",
        md_license_number="CNA12345",
        min_hourly_rate=40.0,
    )


@pytest.fixture
def sample_vms_payload():
    """Fixture: Sample VMS shift payload."""
    return VMSPayload(
        vms_source="ShiftWise",
        facility_id=str(uuid.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="CNA",
        hourly_rate=45.50,
        shift_description="8-hour CNA day shift",
        crisis_rate=False,
        status="PENDING",
    )


# ============================================================================
# TEST 1: Infrastructure initialization
# ============================================================================


@pytest.mark.asyncio
async def test_infrastructure_initialization(matching_engine, mock_db_session):
    """
    Test that all component schemas are initialized successfully.

    Validates:
    - VMS shifts ingest table created
    - pgvector extension and indices created
    - HB 1106 bias audit ledger created
    """
    executed_queries = []

    async def mock_execute(query, params=None):
        executed_queries.append(str(query))
        return MagicMock()

    mock_db_session.execute.side_effect = mock_execute

    # Initialize infrastructure
    await matching_engine.initialize_infrastructure(mock_db_session)

    # Assert VMS table created
    combined_sql = " ".join(executed_queries)
    assert "vms_shifts_ingest" in combined_sql, "VMS table not created"

    # Assert pgvector extension created
    assert "CREATE EXTENSION IF NOT EXISTS pgvector" in combined_sql, (
        "pgvector extension not created"
    )

    # Assert bias audit ledger created
    assert "hb1106_bias_ledger" in combined_sql, "HB 1106 ledger not created"

    # Assert commit called
    assert mock_db_session.commit.call_count >= 3, "Insufficient commits"

    print("✓ Infrastructure initialization: all 3 component schemas created")


# ============================================================================
# TEST 2: Full workflow with license compliance pass
# ============================================================================


@pytest.mark.asyncio
async def test_full_workflow_license_compliance_pass(
    matching_engine,
    mock_db_session,
    sample_caregiver,
    sample_vms_payload,
):
    """
    Test complete matching workflow with successful license match.

    Validates:
    - VMS ingest succeeds
    - License verification passes (with circuit breaker)
    - Semantic match confirms CNA-to-CNA compliance
    - Bias audit record created
    - Overall workflow returns approved match
    """
    # Mock VMS ingestion
    with patch.object(
        matching_engine.vms_pipeline,
        "process_vms_payload",
        new_callable=AsyncMock,
    ) as mock_vms:
        mock_vms.return_value = MagicMock(
            shift_id=str(uuid.uuid4()),
            status="ACTIVE",
            conflict_detected=False,
            processing_time_ms=10.0,
            error=None,
        )

        # Mock license verification
        with patch(
            "app.services.unified_matching_engine.verify_mbon_license_async",
            new_callable=AsyncMock,
        ) as mock_license:
            mock_license.return_value = MagicMock(
                status="ACTIVE",
                license_number="CNA12345",
                expires_on=datetime.now(timezone.utc) + timedelta(days=365),
                disciplinary_action=False,
                source="MBON_API",
            )

            # Mock semantic matcher
            with patch.object(
                matching_engine.semantic_matcher,
                "match_caregiver_to_shift",
                new_callable=AsyncMock,
            ) as mock_match:
                from app.services.matcher import MatchResult

                mock_match.return_value = [
                    MatchResult(
                        caregiver_id=str(sample_caregiver.provider_id),
                        shift_id=str(uuid.uuid4()),
                        similarity_score=0.87,
                        rank=1,
                        caregiver_license="CNA",
                        shift_license_required="CNA",
                        compliance_passed=True,
                        match_method="semantic_vector",
                        execution_time_ms=15.0,
                    )
                ]

                # Mock bias auditor
                with patch.object(
                    matching_engine.bias_auditor,
                    "audit_and_chain_match",
                    new_callable=AsyncMock,
                ) as mock_audit:
                    from app.compliance import BiasAuditRecord

                    mock_audit.return_value = BiasAuditRecord(
                        ledger_id=str(uuid.uuid4()),
                        match_id=str(uuid.uuid4()),
                        parent_hash="0" * 64,
                        block_hash="abc123" + "0" * 58,
                        serialized_payload='{"test": "data"}',
                        created_at=datetime.now(timezone.utc),
                    )

                    # Execute full workflow
                    result = await matching_engine.execute_full_match_workflow(
                        vms_payload=sample_vms_payload,
                        caregiver=sample_caregiver,
                        db_session=mock_db_session,
                    )

    # Assert workflow succeeded
    assert result.match_approved is True, "Match should be approved"
    assert result.compliance_passed is True, "Compliance should pass"
    assert result.license_verified is True, "License should be verified"
    assert result.similarity_score == 0.87, f"Expected score 0.87, got {result.similarity_score}"
    assert result.audit_record_id is not None, "Audit record should be created"
    assert result.error is None, f"Expected no error, got {result.error}"
    assert result.execution_time_ms > 0, "Execution time should be recorded"

    print(
        f"✓ Full workflow SUCCESS: score={result.similarity_score:.2f}, "
        f"time={result.execution_time_ms:.2f}ms"
    )


# ============================================================================
# TEST 3: License compliance failure (CNA→LPN boundary)
# ============================================================================


@pytest.mark.asyncio
async def test_license_compliance_failure_cna_to_lpn(
    matching_engine,
    mock_db_session,
    sample_caregiver,
    sample_vms_payload,
):
    """
    Test that CNA is strictly blocked from LPN shifts.

    Validates:
    - VMS ingest succeeds
    - License verification passes
    - Semantic match FAILS due to license boundary
    - Workflow returns rejected match with compliance error
    """
    # Modify payload to require LPN
    lpn_payload = VMSPayload(
        vms_source=sample_vms_payload.vms_source,
        facility_id=sample_vms_payload.facility_id,
        shift_start=sample_vms_payload.shift_start,
        shift_end=sample_vms_payload.shift_end,
        required_license="LPN",  # CNA cannot match this
        hourly_rate=sample_vms_payload.hourly_rate,
    )

    # Mock VMS ingestion
    with patch.object(
        matching_engine.vms_pipeline,
        "process_vms_payload",
        new_callable=AsyncMock,
    ) as mock_vms:
        mock_vms.return_value = MagicMock(
            shift_id=str(uuid.uuid4()),
            status="ACTIVE",
            conflict_detected=False,
            error=None,
        )

        # Mock license verification
        with patch(
            "app.services.unified_matching_engine.verify_mbon_license_async",
            new_callable=AsyncMock,
        ) as mock_license:
            mock_license.return_value = MagicMock(
                status="ACTIVE",
                license_number="CNA12345",
            )

            # Mock semantic matcher (returns compliance failure)
            with patch.object(
                matching_engine.semantic_matcher,
                "match_caregiver_to_shift",
                new_callable=AsyncMock,
            ) as mock_match:
                from app.services.matcher import MatchResult

                mock_match.return_value = [
                    MatchResult(
                        caregiver_id=str(sample_caregiver.provider_id),
                        shift_id=str(uuid.uuid4()),
                        similarity_score=0.0,
                        rank=0,
                        caregiver_license="CNA",
                        shift_license_required="LPN",
                        compliance_passed=False,  # BLOCKED
                        match_method="license_blocked",
                        execution_time_ms=5.0,
                    )
                ]

                # Execute workflow
                result = await matching_engine.execute_full_match_workflow(
                    vms_payload=lpn_payload,
                    caregiver=sample_caregiver,
                    db_session=mock_db_session,
                )

    # Assert match rejected
    assert result.match_approved is False, "Match should be rejected"
    assert result.compliance_passed is False, "Compliance should fail"
    assert result.error is not None, "Error message should be present"
    assert "License compliance boundary" in result.error or "CNA cannot match LPN" in result.error

    print(f"✓ License boundary enforced: {result.error}")


# ============================================================================
# TEST 4: Circuit breaker status monitoring
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_status_monitoring(matching_engine):
    """
    Test circuit breaker status API for monitoring.

    Validates:
    - Returns current state (CLOSED, OPEN, HALF_OPEN)
    - Returns failure count and threshold
    - Returns last failure timestamp
    """
    status = matching_engine.get_circuit_breaker_status()

    # Assert status structure
    assert "state" in status
    assert "failure_count" in status
    assert "failure_threshold" in status
    assert "last_failure_time" in status

    # Assert initial state
    assert status["state"] == "CLOSED", f"Expected CLOSED state, got {status['state']}"
    assert status["failure_count"] == 0, "Initial failure count should be 0"
    assert status["failure_threshold"] == 3, "Threshold should be 3"

    print(f"✓ Circuit breaker monitoring: state={status['state']}, failures={status['failure_count']}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
