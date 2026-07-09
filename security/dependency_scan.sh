#!/bin/bash
# Dependency vulnerability scanning with Safety and pip-audit

echo "🔍 Scanning dependencies for known vulnerabilities..."

# Install scanners
pip install safety pip-audit -q

# Run Safety check
echo "Running Safety scan..."
safety check --json > security/safety_report.json

# Run pip-audit
echo "Running pip-audit..."
pip-audit --format json > security/pip_audit_report.json

echo "✅ Dependency scan complete"
echo "   Safety report: security/safety_report.json"
echo "   Pip-audit report: security/pip_audit_report.json"

# Check for vulnerabilities
VULN_COUNT=$(jq length security/safety_report.json)

if [ "$VULN_COUNT" -gt 0 ]; then
    echo "⚠️  WARNING: Found $VULN_COUNT vulnerable dependencies"
    jq -r '.[] | "  - \(.package): \(.vulnerability)"' security/safety_report.json
    exit 1
else
    echo "✅ No known vulnerabilities found"
    exit 0
fi
