"""
Test Structure Verification Script

Validates test file structure without execution:
- Imports are valid
- Fixtures are properly defined
- Test functions follow pytest conventions
- Async tests use proper decorators
"""

import ast
import sys
from pathlib import Path
from typing import Any


class TestValidator(ast.NodeVisitor):
    """AST visitor to validate test structure."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.test_count = 0
        self.async_test_count = 0
        self.fixture_count = 0
        self.has_pytest_import = False
        self.has_asyncio_import = False
    
    def visit_Import(self, node: ast.Import) -> None:
        """Check imports."""
        for alias in node.names:
            if alias.name == "pytest":
                self.has_pytest_import = True
            if alias.name == "asyncio":
                self.has_asyncio_import = True
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from imports."""
        if node.module and node.module.startswith("pytest"):
            self.has_pytest_import = True
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check function definitions."""
        # Check for test functions
        if node.name.startswith("test_"):
            self.test_count += 1
        
        # Check for fixtures
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "fixture":
                self.fixture_count += 1
            elif isinstance(decorator, ast.Attribute):
                if decorator.attr == "fixture":
                    self.fixture_count += 1
        
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Check async function definitions."""
        if node.name.startswith("test_"):
            self.async_test_count += 1
            
            # Check for @pytest.mark.asyncio decorator
            has_asyncio_marker = False
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Attribute):
                    if (
                        isinstance(decorator.value, ast.Attribute)
                        and decorator.value.attr == "mark"
                        and decorator.attr == "asyncio"
                    ):
                        has_asyncio_marker = True
            
            if not has_asyncio_marker:
                self.warnings.append(
                    f"Async test '{node.name}' missing @pytest.mark.asyncio decorator "
                    f"(may work with asyncio_mode=auto)"
                )
        
        self.generic_visit(node)
    
    def report(self) -> dict[str, Any]:
        """Generate validation report."""
        return {
            "filename": self.filename,
            "test_count": self.test_count,
            "async_test_count": self.async_test_count,
            "fixture_count": self.fixture_count,
            "has_pytest_import": self.has_pytest_import,
            "has_asyncio_import": self.has_asyncio_import or self.async_test_count == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "status": "VALID" if not self.errors else "INVALID",
        }


def validate_test_file(filepath: Path) -> dict[str, Any]:
    """Validate a single test file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        
        tree = ast.parse(source, filename=str(filepath))
        validator = TestValidator(filepath.name)
        validator.visit(tree)
        
        # Check for pytest import if tests exist
        if validator.test_count > 0 and not validator.has_pytest_import:
            validator.warnings.append("Missing pytest import")
        
        return validator.report()
    
    except SyntaxError as e:
        return {
            "filename": filepath.name,
            "errors": [f"Syntax error: {e}"],
            "status": "INVALID",
        }
    except Exception as e:
        return {
            "filename": filepath.name,
            "errors": [f"Unexpected error: {e}"],
            "status": "INVALID",
        }


def main():
    """Run validation on all test files."""
    test_dir = Path("tests")
    
    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        sys.exit(1)
    
    # Find all test files
    test_files = sorted(test_dir.glob("test_*.py"))
    
    print(f"🔍 Validating {len(test_files)} test files...\n")
    
    results = []
    for test_file in test_files:
        result = validate_test_file(test_file)
        results.append(result)
    
    # Print summary
    valid_count = sum(1 for r in results if r["status"] == "VALID")
    invalid_count = len(results) - valid_count
    total_tests = sum(r.get("test_count", 0) for r in results)
    total_async = sum(r.get("async_test_count", 0) for r in results)
    
    print("=" * 80)
    print(f"📊 VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total Files:      {len(results)}")
    print(f"Valid:            {valid_count} ✅")
    print(f"Invalid:          {invalid_count} ❌")
    print(f"Total Tests:      {total_tests}")
    print(f"Async Tests:      {total_async}")
    print("=" * 80)
    
    # Print detailed results
    print("\n📝 DETAILED RESULTS:\n")
    
    # Enterprise component tests
    enterprise_tests = [
        "test_circuit_breaker.py",
        "test_semantic_matcher.py",
        "test_bias_auditor.py",
        "test_vms_pipeline.py",
        "test_unified_matching_engine.py",
        "test_api_matching.py",
        "test_api_shifts.py",
    ]
    
    print("🏢 ENTERPRISE COMPONENT TESTS:")
    for result in results:
        if result["filename"] in enterprise_tests:
            status_icon = "✅" if result["status"] == "VALID" else "❌"
            print(f"  {status_icon} {result['filename']}")
            print(f"     Tests: {result.get('test_count', 0)} "
                  f"(Async: {result.get('async_test_count', 0)})")
            
            if result.get("errors"):
                for error in result["errors"]:
                    print(f"     ❌ ERROR: {error}")
            
            if result.get("warnings"):
                for warning in result["warnings"]:
                    print(f"     ⚠️  WARNING: {warning}")
    
    print("\n📦 LEGACY TESTS:")
    legacy_count = 0
    for result in results:
        if result["filename"] not in enterprise_tests:
            legacy_count += 1
    print(f"  Found {legacy_count} legacy test files (not validated in detail)")
    
    # Exit with error if any invalid
    if invalid_count > 0:
        print(f"\n❌ {invalid_count} test files have errors!")
        sys.exit(1)
    else:
        print("\n✅ All test files are structurally valid!")
        sys.exit(0)


if __name__ == "__main__":
    main()
