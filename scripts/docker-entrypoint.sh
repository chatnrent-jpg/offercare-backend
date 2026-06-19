#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
python - <<'PY'
import os
import sys
import time

import psycopg2

url = os.environ.get("DATABASE_URL", "")
deadline = time.time() + 60
last_error = None
while time.time() < deadline:
    try:
        psycopg2.connect(url)
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        last_error = exc
        time.sleep(1)
print(f"Database not ready after 60s: {last_error}", file=sys.stderr)
sys.exit(1)
PY

echo "Running database migrations..."
alembic upgrade head

echo "Starting OfferCare.ai API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
