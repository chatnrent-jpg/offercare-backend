"""
Full Test Sweep Execution Script — VettedCare.ai

Runs complete test suite with diagnostics and reporting.
Verifies enterprise components and legacy tests co-exist without conflicts.
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def print_header(text: str) -> None:
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def run_command(cmd: list[str], description: str) -> tuple[bool, str, float]:
    """Run command and return success status, output, and execution time."""
    print(f"🔍 {description}...")
    start = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        elapsed = time.time() - start
        
        success = result.returncode == 0
        output = result.stdout + result.stderr
        
        return success, output, elapsed
    
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return False, "TIMEOUT: Command exceeded 5 minute limit", elapsed
    
    except Exception as e:
        elapsed = time.time() - start
        return False, f"ERROR: {str(e)}", elapsed


def main():
    """Execute full test sweep with diagnostics."""
    print_header("🚀 VettedCare.ai — Full Test Sweep Execution")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working Directory: {Path.cwd()}")
    
    results = {}
    
    # Step 1: Verify pytest installation
    print_header("Step 1: Verify Test Infrastructure")
    success, output, elapsed = run_command(
        [sys.executable, "-m", "pytest", "--version"],
        "Check pytest installation"
    )
    
    if success:
        print(f"✅ pytest installed: {output.strip()}")
        results["pytest_installed"] = True
    else:
        print(f"❌ pytest not found: {output}")
        results["pytest_installed"] = False
        print("\n⚠️  Install pytest: pip install -r requirements.txt")
        return
    
    # Step 2: Check pytest-asyncio
    success, output, elapsed = run_command(
        [sys.executable, "-c", "import pytest_asyncio; print(pytest_asyncio.__version__)"],
        "Check pytest-asyncio"
    )
    
    if success:
        print(f"✅ pytest-asyncio installed: {output.strip()}")
        results["pytest_asyncio"] = True
    else:
        print(f"⚠️  pytest-asyncio not found (may cause issues)")
        results["pytest_asyncio"] = False
    
    # Step 3: Run enterprise component tests (core components only)
    print_header("Step 2: Run Enterprise Component Tests (Core Components)")
    
    # Core component tests (don't require FastAPI app)
    core_component_tests = [
        "tests/test_circuit_breaker.py",
        "tests/test_semantic_matcher.py",
        "tests/test_bias_auditor.py",
        "tests/test_vms_pipeline.py",
        "tests/test_unified_matching_engine.py",
    ]
    
    # API integration tests (require FastAPI app - may fail with version issues)
    api_tests = [
        "tests/test_api_matching.py",
        "tests/test_api_shifts.py",
    ]
    
    enterprise_tests = core_component_tests
    
    enterprise_cmd = [
        sys.executable, "-m", "pytest",
        *enterprise_tests,
        "-v", "--tb=short",
    ]
    
    success, output, elapsed = run_command(
        enterprise_cmd,
        "Core component tests (38 tests: CircuitBreaker, SemanticMatcher, BiasAuditor, VMS, UnifiedEngine)"
    )
    
    results["enterprise_tests"] = {
        "success": success,
        "elapsed": elapsed,
        "output": output,
    }
    
    if success:
        print(f"✅ Enterprise tests PASSED in {elapsed:.2f}s")
        
        # Parse output for test counts
        if "passed" in output:
            import re
            match = re.search(r"(\d+) passed", output)
            if match:
                passed = int(match.group(1))
                print(f"   {passed} tests passed")
                results["enterprise_count"] = passed
    else:
        print(f"❌ Enterprise tests FAILED")
        print("\n--- Test Output (last 100 lines) ---")
        print("\n".join(output.split("\n")[-100:]))
    
    # Step 4: Run full test suite (if enterprise passed)
    if results["enterprise_tests"]["success"]:
        print_header("Step 3: Run Full Test Suite")
        
        full_cmd = [
            sys.executable, "-m", "pytest",
            "tests/",
            "-v", "--tb=short",
            "--maxfail=10",  # Stop after 10 failures
        ]
        
        success, output, elapsed = run_command(
            full_cmd,
            "Full test suite (all tests)"
        )
        
        results["full_suite"] = {
            "success": success,
            "elapsed": elapsed,
            "output": output,
        }
        
        if success:
            print(f"✅ Full test suite PASSED in {elapsed:.2f}s")
            
            # Parse output
            import re
            match = re.search(r"(\d+) passed", output)
            if match:
                passed = int(match.group(1))
                print(f"   {passed} tests passed")
                results["full_count"] = passed
            
            # Check for warnings
            if "warnings summary" in output.lower():
                print("⚠️  Some warnings detected (check output)")
        else:
            print(f"❌ Full test suite had failures")
            print("\n--- Failure Summary (last 100 lines) ---")
            print("\n".join(output.split("\n")[-100:]))
    
    # Final summary
    print_header("📊 Test Sweep Summary")
    
    print(f"Enterprise Tests: {'✅ PASS' if results['enterprise_tests']['success'] else '❌ FAIL'}")
    if "enterprise_count" in results:
        print(f"  - {results['enterprise_count']} tests passed")
    print(f"  - Execution time: {results['enterprise_tests']['elapsed']:.2f}s")
    
    if "full_suite" in results:
        print(f"\nFull Test Suite: {'✅ PASS' if results['full_suite']['success'] else '❌ FAIL'}")
        if "full_count" in results:
            print(f"  - {results['full_count']} tests passed")
        print(f"  - Execution time: {results['full_suite']['elapsed']:.2f}s")
    
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Save detailed report
    report_file = Path("test_sweep_report.txt")
    with open(report_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("VettedCare.ai — Full Test Sweep Report\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")
        
        f.write("Enterprise Component Tests:\n")
        f.write(f"  Status: {'PASS' if results['enterprise_tests']['success'] else 'FAIL'}\n")
        f.write(f"  Time: {results['enterprise_tests']['elapsed']:.2f}s\n\n")
        f.write("--- Output ---\n")
        f.write(results['enterprise_tests']['output'])
        f.write("\n\n")
        
        if "full_suite" in results:
            f.write("Full Test Suite:\n")
            f.write(f"  Status: {'PASS' if results['full_suite']['success'] else 'FAIL'}\n")
            f.write(f"  Time: {results['full_suite']['elapsed']:.2f}s\n\n")
            f.write("--- Output ---\n")
            f.write(results['full_suite']['output'])
    
    print(f"\n📝 Detailed report saved to: {report_file.absolute()}")
    
    # Exit with appropriate code
    if results["enterprise_tests"]["success"]:
        if "full_suite" in results and results["full_suite"]["success"]:
            print("\n🎉 SUCCESS: All tests passed!")
            sys.exit(0)
        else:
            print("\n⚠️  Enterprise tests passed, but full suite had issues")
            sys.exit(1)
    else:
        print("\n❌ FAILURE: Enterprise tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
