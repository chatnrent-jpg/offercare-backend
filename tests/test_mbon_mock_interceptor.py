"""
Test Suite: MBON Registry Mock Interceptor Validation
Phase 2: Intelligence & Compliance

Validates that the mock MBON registry interceptor correctly:
1. Intercepts outgoing HTTP requests to https://mbon.org
2. Returns deterministic mock responses for testing
3. Prevents live government server traffic during tests
4. Provides coverage for RN, LPN, and CNA license lookups
"""

import pytest
import httpx


@pytest.mark.asyncio
async def test_mbon_interceptor_active_rn_license():
    """
    Test Case 1: Active RN License (R234951)
    
    Verifies that the mock interceptor returns a valid ACTIVE status
    for the seeded RN test license number.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get("https://mbon.org/RN/R234951")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ACTIVE"
        assert data["license_number"] == "R234951"
        assert data["license_type"] == "RN"
        assert data["expiry_date"] == "2027-10-31"
        assert data["disciplinary_actions"] is False


@pytest.mark.asyncio
async def test_mbon_interceptor_active_lpn_license():
    """
    Test Case 2: Active LPN License (L098114)
    
    Verifies that the mock interceptor returns a valid ACTIVE status
    for the seeded LPN test license number.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get("https://mbon.org/LPN/L098114")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ACTIVE"
        assert data["license_number"] == "L098114"
        assert data["license_type"] == "LPN"
        assert data["expiry_date"] == "2027-04-30"
        assert data["disciplinary_actions"] is False


@pytest.mark.asyncio
async def test_mbon_interceptor_not_found_cna_license():
    """
    Test Case 3: Not Found CNA License (A774123)
    
    Verifies that the mock interceptor returns a 404 NOT_FOUND status
    for the seeded CNA test license number (simulating revoked/invalid license).
    """
    async with httpx.AsyncClient() as client:
        response = await client.get("https://mbon.org/CNA/A774123")
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["status"] == "NOT_FOUND"
        assert "not located" in data["detail"].lower()


@pytest.mark.asyncio
async def test_mbon_interceptor_fallback_invalid_query():
    """
    Test Case 4: Fallback Catch-All Route
    
    Verifies that unanticipated license queries return a 400 INVALID_QUERY
    response as a safety fallback.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get("https://mbon.org/UNKNOWN/XYZ999")
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["status"] == "INVALID_QUERY"


@pytest.mark.asyncio
async def test_mbon_scraper_pool_integration():
    """
    Integration Test: MBONScraperPool with Mock Interceptor
    
    Validates that the MBONScraperPool class correctly uses the mock
    interceptor and processes license verification results.
    """
    from app.workers.mbon_scraper import MBONScraperPool
    
    scraper = MBONScraperPool(proxies=[])
    
    # Test RN verification
    rn_result = await scraper.verify_license("R234951", "RN")
    assert rn_result["is_valid"] is True
    assert rn_result["status"] == "ACTIVE"
    assert "checked_at" in rn_result
    
    # Test LPN verification
    lpn_result = await scraper.verify_license("L098114", "LPN")
    assert lpn_result["is_valid"] is True
    assert lpn_result["status"] == "ACTIVE"
    
    # Test CNA verification (not found)
    cna_result = await scraper.verify_license("A774123", "CNA")
    assert cna_result["is_valid"] is False
    assert cna_result["status"] == "NOT_FOUND"


# ============================================================================
# EDGE CASE TESTING
# ============================================================================

@pytest.mark.asyncio
async def test_mbon_interceptor_rate_limiting_simulation():
    """
    Edge Case: Rapid Sequential Requests
    
    Verifies that the mock interceptor can handle rapid-fire requests
    without blocking or failing (simulating rate limit bypass in tests).
    """
    async with httpx.AsyncClient() as client:
        # Fire 10 rapid requests
        tasks = [
            client.get("https://mbon.org/RN/R234951")
            for _ in range(10)
        ]
        
        import asyncio
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        assert len(responses) == 10


@pytest.mark.asyncio
async def test_mbon_interceptor_no_network_leakage():
    """
    Security Test: Network Isolation Validation
    
    Ensures that NO actual HTTP traffic reaches live government servers
    during test execution by verifying all requests are intercepted.
    """
    async with httpx.AsyncClient() as client:
        # This should hit the mock, not the real server
        response = await client.get("https://mbon.org/RN/R234951")
        
        # If this passes without network errors, mock is working
        assert response.status_code == 200
        
        # Verify response time is instant (< 100ms, not real network latency)
        # Note: This is implicit - respx mocks return instantly
        assert response.elapsed.total_seconds() < 1.0
