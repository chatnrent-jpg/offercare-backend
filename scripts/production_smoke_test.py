import time
import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.middleware.security_middleware_optimized import HardenedFortressMiddleware
from app.api.v1 import api_v1_router

def run_production_preflight_checks():
    """
    Executes core performance gating checks on the final production app context.
    Mitigates cold-start framework initialization overhead before benchmarking.
    """
    print("Initializing production pre-flight automation...")
    
    app = FastAPI()
    app.add_middleware(HardenedFortressMiddleware)
    app.include_router(api_v1_router, prefix="/api/v1")
    client = TestClient(app)
    
    # 1. Trigger an initial cold-start request to warm up the application context
    print("Warming up FastAPI application routers and memory structures...")
    client.post("/api/v1/scale/segment-waves", json={"provider_ids": ["warmup_id"]})
    
    print("Testing sustained Layer 0 Whitelist Fast-Pass latency envelope...")
    
    # 2. Benchmark the warmed, sustained inside-memory cache layer performance
    start_time = time.perf_counter()
    response = client.post("/api/v1/scale/segment-waves", json={"provider_ids": ["test_1"]})
    duration_ms = (time.perf_counter() - start_time) * 1000
    
    print(f"Layer 0 Hot-Path Response received in: {duration_ms:.2f}ms")
    
    # 3. Enforce the hard performance boundary (< 5.0ms on local testing harness)
    if duration_ms > 5.0:
        print("CRITICAL PERFORMANCE FAILURE: Security middleware overhead breached threshold.")
        sys.exit(1)
        
    print("SUCCESS: Production pre-flight smoke tests passed within canonical bounds!")
    sys.exit(0)

if __name__ == '__main__':
    run_production_preflight_checks()
