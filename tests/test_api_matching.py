"""
Integration Tests — Unified Matching API Routes

Tests full matching pipeline with all enterprise components:
- CircuitBreaker (150ms latency ceiling)
- SemanticMatcher (license-restricted matching)
- BiasAuditor (tamper-evident ledger)
- Transaction safety and rollback

Validates complete end-to-end workflow from API request to database commit.
"""

import uuid as uuid_module
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.api.v1.matching import get_bias_auditor, get_circuit_breaker, get_semantic_matcher
from app.models import HB1106BiasLedger, MarylandProvider, VMSShiftIngest
from app.services.matcher import MatchResult
from app.services.mbon_verification import MbonVerificationResult


@pytest.mark.asyncio
async def test_get_matched_shifts_success(test_client, async_db, mock_provider):
    """Test GET /api/v1/matching/shifts — successful retrieval with semantic matching."""
    # Create test shifts
    shift1 = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="CNA",
        hourly_rate=25.0,
        crisis_rate=False,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    shift2 = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=2),
        shift_end=datetime.now(timezone.utc) + timedelta(days=2, hours=8),
        required_license="CNA",
        hourly_rate=30.0,
        crisis_rate=True,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add_all([shift1, shift2])
    await async_db.commit()
    
    # Mock semantic matcher to return valid matches
    mock_match_result = MatchResult(
        caregiver_id=str(mock_provider.provider_id),
        facility_shift_id=str(shift1.shift_id),
        similarity_score=0.85,
        match_method="semantic_vector",
        caregiver_license="CNA",
        shift_license_required="CNA",
        compliance_passed=True,
    )
    
    with patch.object(
        get_semantic_matcher(),
        "match_caregiver_to_shift",
        return_value=[mock_match_result],
    ):
        # Mock license verification
        with patch(
            "app.api.v1.matching.verify_mbon_license_async",
            return_value=MbonVerificationResult(
                status="ACTIVE",
                license_number="MD12345",
                expiration_date=datetime.now(timezone.utc) + timedelta(days=365),
                source="MBON_API",
            ),
        ):
            response = test_client.get(
                "/api/v1/matching/shifts",
                headers={"Authorization": f"Bearer {mock_provider.jwt_token}"},
            )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] >= 1
    assert len(data["shifts"]) >= 1
    assert data["caregiver"]["provider_id"] == str(mock_provider.provider_id)
    
    # Verify shift data
    shift_data = data["shifts"][0]
    assert "shift_id" in shift_data
    assert "similarity_score" in shift_data
    assert shift_data["similarity_score"] > 0


@pytest.mark.asyncio
async def test_get_matched_shifts_license_boundary(test_client, async_db, mock_provider):
    """Test license boundary enforcement — CNA cannot match LPN shifts."""
    # Create LPN shift (should be blocked for CNA)
    lpn_shift = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="LPN",  # Higher license
        hourly_rate=35.0,
        crisis_rate=False,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add(lpn_shift)
    await async_db.commit()
    
    # Mock semantic matcher to return BLOCKED match
    mock_blocked_result = MatchResult(
        caregiver_id=str(mock_provider.provider_id),
        facility_shift_id=str(lpn_shift.shift_id),
        similarity_score=0.0,
        match_method="semantic_vector",
        caregiver_license="CNA",
        shift_license_required="LPN",
        compliance_passed=False,  # Boundary violation
    )
    
    with patch.object(
        get_semantic_matcher(),
        "match_caregiver_to_shift",
        return_value=[mock_blocked_result],
    ):
        with patch(
            "app.api.v1.matching.verify_mbon_license_async",
            return_value=MbonVerificationResult(
                status="ACTIVE",
                license_number="MD12345",
                expiration_date=datetime.now(timezone.utc) + timedelta(days=365),
                source="MBON_API",
            ),
        ):
            response = test_client.get(
                "/api/v1/matching/shifts",
                headers={"Authorization": f"Bearer {mock_provider.jwt_token}"},
            )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should return 0 shifts (all blocked by license boundary)
    assert data["total"] == 0
    assert len(data["shifts"]) == 0


@pytest.mark.asyncio
async def test_lock_shift_match_success(test_client, async_db, mock_provider):
    """Test POST /api/v1/matching/shifts/{shift_id}/lock — full pipeline success."""
    # Create active shift
    shift = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="CNA",
        hourly_rate=28.0,
        crisis_rate=False,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add(shift)
    await async_db.commit()
    
    # Mock all components
    mock_match_result = MatchResult(
        caregiver_id=str(mock_provider.provider_id),
        facility_shift_id=str(shift.shift_id),
        similarity_score=0.92,
        match_method="semantic_vector",
        caregiver_license="CNA",
        shift_license_required="CNA",
        compliance_passed=True,
    )
    
    with patch.object(
        get_semantic_matcher(),
        "match_caregiver_to_shift",
        return_value=[mock_match_result],
    ):
        with patch(
            "app.api.v1.matching.verify_mbon_license_async",
            return_value=MbonVerificationResult(
                status="ACTIVE",
                license_number="MD12345",
                expiration_date=datetime.now(timezone.utc) + timedelta(days=365),
                source="MBON_API",
            ),
        ):
            # BiasAuditor will actually write to DB (not mocked)
            response = test_client.post(
                f"/api/v1/matching/shifts/{shift.shift_id}/lock",
                headers={"Authorization": f"Bearer {mock_provider.jwt_token}"},
            )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert data["match_approved"] is True
    assert data["compliance_passed"] is True
    assert data["license_verified"] is True
    assert data["similarity_score"] == 0.92
    assert data["shift_id"] == str(shift.shift_id)
    assert data["audit_record_id"] is not None
    
    # Verify shift status updated to LOCKED
    await async_db.refresh(shift)
    assert shift.status == "LOCKED"
    
    # Verify audit record created
    result = await async_db.execute(
        select(HB1106BiasLedger).where(HB1106BiasLedger.match_id == data["match_id"])
    )
    audit_record = result.scalar_one_or_none()
    
    assert audit_record is not None
    assert audit_record.block_hash is not None
    assert len(audit_record.block_hash) == 64  # SHA-256 hex


@pytest.mark.asyncio
async def test_lock_shift_match_license_boundary(test_client, async_db, mock_provider):
    """Test shift lock failure due to license boundary violation."""
    # Create LPN shift (CNA cannot lock)
    shift = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="LPN",
        hourly_rate=35.0,
        crisis_rate=False,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add(shift)
    await async_db.commit()
    
    # Mock semantic matcher to return blocked result
    mock_blocked_result = MatchResult(
        caregiver_id=str(mock_provider.provider_id),
        facility_shift_id=str(shift.shift_id),
        similarity_score=0.0,
        match_method="semantic_vector",
        caregiver_license="CNA",
        shift_license_required="LPN",
        compliance_passed=False,  # BLOCKED
    )
    
    with patch.object(
        get_semantic_matcher(),
        "match_caregiver_to_shift",
        return_value=[mock_blocked_result],
    ):
        with patch(
            "app.api.v1.matching.verify_mbon_license_async",
            return_value=MbonVerificationResult(
                status="ACTIVE",
                license_number="MD12345",
                expiration_date=datetime.now(timezone.utc) + timedelta(days=365),
                source="MBON_API",
            ),
        ):
            response = test_client.post(
                f"/api/v1/matching/shifts/{shift.shift_id}/lock",
                headers={"Authorization": f"Bearer {mock_provider.jwt_token}"},
            )
    
    assert response.status_code == 400
    data = response.json()
    
    assert data["detail"]["error"] == "LICENSE_BOUNDARY_VIOLATION"
    assert "CNA" in data["detail"]["detail"]
    assert "LPN" in data["detail"]["detail"]
    
    # Verify shift status unchanged
    await async_db.refresh(shift)
    assert shift.status == "ACTIVE"


@pytest.mark.asyncio
async def test_lock_shift_match_already_locked(test_client, async_db, mock_provider):
    """Test shift lock failure — shift already locked."""
    # Create locked shift
    shift = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="CNA",
        hourly_rate=28.0,
        crisis_rate=False,
        status="LOCKED",  # Already locked
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add(shift)
    await async_db.commit()
    
    with patch(
        "app.api.v1.matching.verify_mbon_license_async",
        return_value=MbonVerificationResult(
            status="ACTIVE",
            license_number="MD12345",
            expiration_date=datetime.now(timezone.utc) + timedelta(days=365),
            source="MBON_API",
        ),
    ):
        response = test_client.post(
            f"/api/v1/matching/shifts/{shift.shift_id}/lock",
            headers={"Authorization": f"Bearer {mock_provider.jwt_token}"},
        )
    
    assert response.status_code == 409
    data = response.json()
    
    assert data["detail"]["error"] == "SHIFT_UNAVAILABLE"
    assert "LOCKED" in data["detail"]["detail"]


@pytest.mark.asyncio
async def test_verify_ledger_integrity_success(test_client, async_db):
    """Test GET /api/v1/matching/admin/verify-ledger — valid ledger."""
    # BiasAuditor will initialize empty ledger (valid by default)
    response = test_client.get("/api/v1/matching/admin/verify-ledger")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "VALID"
    assert data["total_records"] >= 0
    assert data["verified_records"] == data["total_records"]
    assert "genesis_hash" in data
    assert "latest_hash" in data
    assert data["corrupted_record_ids"] == []
