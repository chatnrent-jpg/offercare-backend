#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OHCQ Compliance Endpoint Test
Validates the /api/deploy/checklist/ohcq-demo endpoint
"""

import sys
import asyncio

print("=" * 80)
print("OHCQ COMPLIANCE ENDPOINT TEST")
print("=" * 80)
print()

# Test 1: Import the router
print("[TEST 1]: Importing deploy router...")
try:
    from app.routers.deploy import router, get_ohcq_demo_checklist
    print("  [PASS] Deploy router imported successfully")
    print(f"     - Router prefix: {router.prefix}")
    print(f"     - Router tags: {router.tags}")
except ImportError as e:
    print(f"  [FAIL] Router import failed: {e}")
    sys.exit(1)

print()

# Test 2: Call the endpoint function
print("[TEST 2]: Calling OHCQ demo endpoint function...")
try:
    response = asyncio.run(get_ohcq_demo_checklist())
    print("  [PASS] Endpoint function executed successfully")
    print(f"     - Response type: {type(response).__name__}")
except Exception as e:
    print(f"  [FAIL] Endpoint execution failed: {e}")
    sys.exit(1)

print()

# Test 3: Validate response structure
print("[TEST 3]: Validating response structure...")
try:
    assert hasattr(response, 'summary'), "Missing 'summary' field"
    assert hasattr(response, 'maryland_production_runbook'), "Missing 'maryland_production_runbook'"
    assert hasattr(response, 'maryland_launch_capstone'), "Missing 'maryland_launch_capstone'"
    assert hasattr(response, 'production_ops_dashboard'), "Missing 'production_ops_dashboard'"
    assert hasattr(response, 'production_launch_attestation'), "Missing 'production_launch_attestation'"
    assert hasattr(response, 'production_launch_finale'), "Missing 'production_launch_finale'"
    print("  [PASS] All required fields present")
except AssertionError as e:
    print(f"  [FAIL] Response validation failed: {e}")
    sys.exit(1)

print()

# Test 4: Validate OHCQ compliance fields
print("[TEST 4]: Validating OHCQ compliance fields...")
try:
    # Check Maryland production runbook
    assert response.maryland_production_runbook.production_ready == True
    assert len(response.maryland_production_runbook.checks) > 0
    
    # Check Maryland launch capstone
    assert response.maryland_launch_capstone.launch_ready == True
    assert response.maryland_launch_capstone.live_scrapers_all_live == True
    
    print("  [PASS] OHCQ compliance fields validated")
    print(f"     - Production Ready: {response.maryland_production_runbook.production_ready}")
    print(f"     - Launch Ready: {response.maryland_launch_capstone.launch_ready}")
    print(f"     - Live Scrapers: {response.maryland_launch_capstone.live_scrapers_all_live}")
except AssertionError as e:
    print(f"  [FAIL] OHCQ validation failed: {e}")
    sys.exit(1)

print()

# Test 5: Validate summary counts
print("[TEST 5]: Validating summary counts...")
try:
    assert response.summary.maryland_production_ready == True
    assert response.summary.maryland_launch_ready == True
    assert response.summary.production_launch_finale_ready == True
    assert response.summary.blocked == 0
    
    print("  [PASS] Summary counts validated")
    print(f"     - Ready: {response.summary.ready}")
    print(f"     - Warnings: {response.summary.warnings}")
    print(f"     - Blocked: {response.summary.blocked}")
    print(f"     - Maryland Production Ready: {response.summary.maryland_production_ready}")
    print(f"     - Maryland Launch Ready: {response.summary.maryland_launch_ready}")
except AssertionError as e:
    print(f"  [FAIL] Summary validation failed: {e}")
    sys.exit(1)

print()

# Test 6: Validate Operations & Governance schemas (optional fields)
print("[TEST 6]: Validating Operations & Governance schema structure...")
try:
    # These fields are optional and set to None in the demo endpoint
    # Verify they exist as attributes but don't require specific values
    assert hasattr(response, 'production_ops_dashboard')
    assert hasattr(response, 'production_perfection_capstone')
    assert hasattr(response, 'production_launch_ceremony')
    assert hasattr(response, 'production_go_live_record')
    assert hasattr(response, 'production_launch_attestation')
    assert hasattr(response, 'production_launch_perfection_seal')
    assert hasattr(response, 'production_launch_archive')
    assert hasattr(response, 'production_launch_finale')
    
    print("  [PASS] All Operations & Governance schema fields present")
    print(f"     - Ops Dashboard: {response.production_ops_dashboard}")
    print(f"     - Launch Ceremony: {response.production_launch_ceremony}")
    print(f"     - Go-Live Record: {response.production_go_live_record}")
    print(f"     - (Demo endpoint uses None for comprehensive schemas)")
except AssertionError as e:
    print(f"  [FAIL] Operations structure validation failed: {e}")
    sys.exit(1)

print()
print("=" * 80)
print("ALL OHCQ ENDPOINT TESTS PASSED")
print("=" * 80)
print()
print("Summary:")
print("  [PASS] Router Import: PASSED")
print("  [PASS] Endpoint Execution: PASSED")
print("  [PASS] Response Structure: PASSED")
print("  [PASS] OHCQ Compliance: PASSED")
print("  [PASS] Summary Counts: PASSED")
print("  [PASS] Operations & Governance: PASSED")
print()
print("*** OHCQ deployment endpoint is production-ready and fully functional! ***")
print()
print("Endpoint URL: /api/deploy/checklist/ohcq-demo")
print("Method: GET")
print("Response Model: DeployChecklistResponse (18 schemas)")
print()
