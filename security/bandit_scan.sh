#!/bin/bash
# Automated security vulnerability scanning with Bandit

echo "🔍 Running Bandit security scan..."

# Install bandit if not present
pip install bandit -q

# Run Bandit on entire codebase
bandit -r app/ -f json -o security/bandit_report.json

# Run with severity filter
bandit -r app/ -ll -f txt -o security/bandit_high_severity.txt

echo "✅ Bandit scan complete"
echo "   Full report: security/bandit_report.json"
echo "   High severity: security/bandit_high_severity.txt"

# Check for critical issues
CRITICAL_COUNT=$(grep -c '"issue_severity": "HIGH"' security/bandit_report.json)

if [ "$CRITICAL_COUNT" -gt 0 ]; then
    echo "⚠️  WARNING: Found $CRITICAL_COUNT HIGH severity issues"
    exit 1
else
    echo "✅ No HIGH severity issues found"
    exit 0
fi
