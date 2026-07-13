#!/usr/bin/env bash
# Celery Beat Scheduler Startup Script
# Starts the beat scheduler for triggering scheduled tasks (e.g., hourly MBON sync)

set -euo pipefail

echo "⏰ Starting Celery Beat Scheduler for VettedMe OHCQ Infrastructure..."
echo ""
echo "Beat Configuration:"
echo "  - App: app.core.celery_app"
echo "  - Log Level: info"
echo "  - Scheduled Tasks:"
echo "    • MBON Scraper Sync: Hourly at :00"
echo ""

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ ERROR: Redis server is not running!"
    echo "   Start Redis with: redis-server"
    exit 1
fi

echo "✅ Redis server is running"
echo ""
echo "⚠️  WARNING: Only run ONE beat scheduler instance!"
echo "   Multiple beat instances will cause duplicate task execution."
echo ""
echo "Starting beat scheduler... (Press Ctrl+C to stop)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

celery -A app.core.celery_app beat --loglevel=info
