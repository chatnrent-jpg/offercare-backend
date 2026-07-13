#!/usr/bin/env bash
# Celery Worker Startup Script
# Starts the primary task consumer worker for background job processing

set -euo pipefail

echo "🚀 Starting Celery Worker for VettedMe OHCQ Infrastructure..."
echo ""
echo "Worker Configuration:"
echo "  - App: app.core.celery_app"
echo "  - Log Level: info"
echo "  - Concurrency: 2 worker processes"
echo "  - Pool: prefork (multiprocessing)"
echo ""

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ ERROR: Redis server is not running!"
    echo "   Start Redis with: redis-server"
    exit 1
fi

echo "✅ Redis server is running"
echo ""
echo "Starting worker... (Press Ctrl+C to stop)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

celery -A app.core.celery_app worker --loglevel=info --concurrency=2
