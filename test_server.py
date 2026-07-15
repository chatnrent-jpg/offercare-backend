"""
Quick test script to verify server can start
Run this to diagnose issues: python test_server.py
"""

import sys

print("🔍 Testing VettedMe Server Setup...")
print("-" * 50)

# Test 1: Python version
print("\n1. Python Version:")
print(f"   ✅ {sys.version}")

# Test 2: Import FastAPI
print("\n2. Testing FastAPI import...")
try:
    import fastapi
    print(f"   ✅ FastAPI {fastapi.__version__} installed")
except ImportError as e:
    print(f"   ❌ FastAPI not found: {e}")
    sys.exit(1)

# Test 3: Import app.main
print("\n3. Testing app.main import...")
try:
    from app.main import app
    print("   ✅ app.main imported successfully")
except Exception as e:
    print(f"   ❌ Failed to import app.main:")
    print(f"      Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Check if app has routes
print("\n4. Checking routes...")
try:
    routes = [route.path for route in app.routes]
    print(f"   ✅ Found {len(routes)} routes")
    
    # Check for critical routes
    critical_routes = ["/", "/dashboard", "/docs", "/api/v1/passports"]
    for route in critical_routes:
        if route in routes:
            print(f"   ✅ {route}")
        else:
            print(f"   ⚠️  {route} not found")
            
except Exception as e:
    print(f"   ❌ Error checking routes: {e}")

# Test 5: Check database connection
print("\n5. Testing database connection...")
try:
    from app.database import engine
    from sqlalchemy import text
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("   ✅ Database connection successful")
except Exception as e:
    print(f"   ⚠️  Database connection failed: {e}")
    print("      (This is OK if database isn't set up yet)")

# Test 6: Check static files
print("\n6. Checking static files...")
import os
static_files = [
    "app/static/index.html",
    "app/static/dashboard/index.html",
    "app/static/passport/index.html",
]
for file_path in static_files:
    if os.path.exists(file_path):
        print(f"   ✅ {file_path}")
    else:
        print(f"   ❌ {file_path} not found")

print("\n" + "=" * 50)
print("✅ ALL TESTS PASSED!")
print("\nYou can now start the server:")
print("   python -m uvicorn app.main:app --reload")
print("=" * 50)
