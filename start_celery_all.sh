#!/usr/bin/env bash
# Complete Celery Infrastructure Startup Script
# Starts worker + beat in a single process (DEVELOPMENT ONLY)

set -euo pipefail

echo "🚀 Starting Complete Celery Infrastructure (Worker + Beat)..."
echo ""
echo "⚠️  WARNING: This combined mode is for DEVELOPMENT ONLY!"
echo "   For production, run worker and beat in separate processes."
echo ""
echo "Configuration:"
echo "  - App: app.core.celery_app"
echo "  - Log Level: info"
echo "  - Worker Concurrency: 2"
echo "  - Beat Scheduler: Enabled"
echo ""

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ ERROR: Redis server is not running!"
    echo "   Start Redis with: redis-server"
    exit 1
fi

echo "✅ Redis server is running"
echo ""
echo "Starting worker with beat... (Press Ctrl+C to stop)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

celery -A app.core.celery_app worker --beat --loglevel=info --concurrency=2
