"""
End-to-End Integration Test Suite: OHCQ Compliance Flow
Phase 2: Intelligence & Compliance

This E2E test verifies the complete data flow:
1. Database seeded credentials (app/db/seed_credentials.py)
2. MBON Scraper Pool worker (app/workers/mbon_scraper.py)
3. HTTP Mock Interceptor (tests/conftest.py)
4. Database persistence and state updates

Tests the full cycle: DB → Worker → Network (Mocked) → DB Update
"""

import pytest
from datetime import datetime, timezone
from app.database import SessionLocal
from app.workers.mbon_scraper import MBONScraperPool
from app.models import HealthcareCredential


@pytest.mark.asyncio
async def test_end_to_end_scraper_synchronization_cycle():
    """
    E2E Verification: Complete MBON scraper workflow
    
    Ensures data changes flow correctly from the database layer, 
    through the worker engine, and safely save back to the database.
    
    Flow:
    1. Query seeded test credentials from database
    2. Run MBON scraper sync cycle (uses mock interceptor)
    3. Verify database records updated with verification results
    4. Validate timestamps and status changes
    """
    db = SessionLocal()
    try:
        # 1. Instantiate the Scraper Module with mock proxy rotation
        scraper = MBONScraperPool(proxies=[])
        
        # 2. Get initial state of seeded test credentials
        initial_credentials = db.query(HealthcareCredential).filter(
            HealthcareCredential.license_number.like("%-TEST-%")
        ).all()
        
        assert len(initial_credentials) >= 3, "Expected at least 3 seeded test credentials"
        
        # Record initial verification timestamps
        initial_timestamps = {
            cred.license_number: cred.ohcq_verified_at
            for cred in initial_credentials
        }
        
        # 3. Run the sync loop against the database seed entries
        await scraper.run_sync_cycle(db)
        
        # 4. Pull refreshed records back out to verify state changes
        db.expire_all()  # Force refresh from database
        updated_credentials = db.query(HealthcareCredential).filter(
            HealthcareCredential.license_number.like("%-TEST-%")
        ).all()
        
        # 5. Verify credentials were processed
        assert len(updated_credentials) == len(initial_credentials)
        
        # 6. Verify at least one credential had its verification timestamp updated
        # (Some may not update if they weren't in PENDING/ACTIVE status)
        timestamps_updated = sum(
            1 for cred in updated_credentials
            if initial_timestamps.get(cred.license_number) != cred.ohcq_verified_at
        )
        
        assert timestamps_updated > 0, "Expected at least one credential to be verified"
        
    finally:
        db.close()


@pytest.mark.asyncio
async def test_scraper_pool_handles_pending_credentials():
    """
    Unit Test: Verify scraper prioritizes PENDING credentials
    
    Tests that the scraper correctly identifies and processes
    credentials that have never been verified (is_ohcq_verified=False).
    """
    db = SessionLocal()
    try:
        scraper = MBONScraperPool()
        
        # Get unverified test credential
        pending_cred = db.query(HealthcareCredential).filter(
            HealthcareCredential.license_number.like("%-TEST-%"),
            HealthcareCredential.is_ohcq_verified == False
        ).first()
        
        if pending_cred:
            # Verify the scraper can process individual credentials
            result = await scraper.verify_license(
                pending_cred.license_number,
                pending_cred.license_type
            )
            
            # Mock interceptor will return NOT_FOUND for TEST credentials
            # unless they match the specific mock patterns
            assert "status" in result
            assert "checked_at" in result
            assert result["is_valid"] in [True, False]
            
    finally:
        db.close()


@pytest.mark.asyncio
async def test_scraper_pool_with_real_intercepted_licenses():
    """
    Integration Test: Verify scraper with specific mock interceptor patterns
    
    Uses the exact license numbers defined in the mock interceptor
    (R234951, L098114, A774123) to verify proper integration.
    """
    scraper = MBONScraperPool()
    
    # Test Active RN (should be intercepted and return ACTIVE)
    rn_result = await scraper.verify_license("R234951", "RN")
    assert rn_result["is_valid"] is True
    assert rn_result["status"] == "ACTIVE"
    assert isinstance(rn_result["checked_at"], str)
    
    # Test Active LPN (should be intercepted and return ACTIVE)
    lpn_result = await scraper.verify_license("L098114", "LPN")
    assert lpn_result["is_valid"] is True
    assert lpn_result["status"] == "ACTIVE"
    
    # Test Not Found CNA (should be intercepted and return NOT_FOUND)
    cna_result = await scraper.verify_license("A774123", "CNA")
    assert cna_result["is_valid"] is False
    assert cna_result["status"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_database_persistence_after_verification():
    """
    Integration Test: Verify database updates persist correctly
    
    Ensures that when the scraper updates a credential's verification
    status, the changes are properly committed and queryable.
    """
    db = SessionLocal()
    try:
        # Create a temporary test credential
        import uuid
        from app.models import MarylandProvider
        
        # Get or create test provider
        test_provider = db.query(MarylandProvider).filter(
            MarylandProvider.full_name.like("%Test Provider%")
        ).first()
        
        if not test_provider:
            pytest.skip("No test provider found - run seed_credentials first")
        
        # Create a new test credential
        from datetime import timedelta
        test_cred = HealthcareCredential(
            provider_id=test_provider.provider_id,
            license_type="RN",
            license_number="RN-E2E-TEST-999",
            expiration_date=(datetime.now(timezone.utc) + timedelta(days=365)).date(),
            is_ohcq_verified=False,
            background_check_passed=False,
        )
        
        db.add(test_cred)
        db.commit()
        db.refresh(test_cred)
        
        initial_verified_at = test_cred.ohcq_verified_at
        assert initial_verified_at is None
        
        # Verify through scraper (will use mock interceptor)
        scraper = MBONScraperPool()
        result = await scraper.verify_license(test_cred.license_number, test_cred.license_type)
        
        # Manually update the record (simulating what run_sync_cycle does)
        test_cred.ohcq_verified_at = datetime.fromisoformat(result["checked_at"])
        db.commit()
        
        # Query again to verify persistence
        db.expire(test_cred)
        refreshed_cred = db.query(HealthcareCredential).filter_by(
            license_number="RN-E2E-TEST-999"
        ).first()
        
        assert refreshed_cred is not None
        assert refreshed_cred.ohcq_verified_at is not None
        assert refreshed_cred.ohcq_verified_at != initial_verified_at
        
        # Cleanup
        db.delete(refreshed_cred)
        db.commit()
        
    finally:
        db.close()


@pytest.mark.asyncio
async def test_scraper_handles_network_failures_gracefully():
    """
    Edge Case Test: Verify scraper handles unexpected license formats
    
    Tests that the scraper doesn't crash when given invalid or
    unexpected license numbers that don't match mock patterns.
    """
    scraper = MBONScraperPool()
    
    # Test with invalid format
    result = await scraper.verify_license("INVALID-999", "UNKNOWN")
    
    # Should return INVALID_QUERY from fallback mock route (400 status)
    # But our scraper treats non-200/404 as NOT_FOUND
    assert result["is_valid"] is False
    assert result["status"] in ["NOT_FOUND", "PROBE_FAILED"]
    assert "checked_at" in result


@pytest.mark.asyncio
async def test_compliance_workflow_full_cycle():
    """
    Compliance Workflow Test: Complete OHCQ verification cycle
    
    Simulates the full compliance workflow:
    1. Healthcare provider applies
    2. Credential created in database
    3. MBON scraper verifies license
    4. Database updated with verification results
    5. Compliance gates check verification status
    """
    db = SessionLocal()
    try:
        # Get a test credential
        test_cred = db.query(HealthcareCredential).filter(
            HealthcareCredential.license_number.like("%-TEST-%")
        ).first()
        
        if not test_cred:
            pytest.skip("No test credentials found - run seed_credentials first")
        
        # Simulate scraper verification
        scraper = MBONScraperPool()
        verification_result = await scraper.verify_license(
            test_cred.license_number,
            test_cred.license_type
        )
        
        # Verify result structure for compliance reporting
        assert "is_valid" in verification_result
        assert "status" in verification_result
        assert "checked_at" in verification_result
        
        # Verify timestamp is recent (within last minute)
        checked_time = datetime.fromisoformat(verification_result["checked_at"])
        time_diff = datetime.now(timezone.utc) - checked_time
        assert time_diff.total_seconds() < 60, "Verification timestamp should be recent"
        
    finally:
        db.close()
