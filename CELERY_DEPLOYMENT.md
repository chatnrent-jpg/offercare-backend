# Celery Worker Deployment Guide

## Overview
This guide covers starting the Celery background worker infrastructure for automated MBON credential verification and other scheduled tasks.

## Prerequisites

### 1. Redis Server Running
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Start Redis if not running (Linux/Mac)
redis-server

# Or with config file
redis-server /path/to/redis.conf
```

### 2. Python Dependencies Installed
```bash
pip install celery redis
```

## Worker Execution Commands

### Primary Task Consumer Worker
Processes tasks from the Redis queue and executes background jobs.

```bash
celery -A app.core.celery_app worker --loglevel=info
```

**Options:**
- `--loglevel=info` - Standard logging (use `debug` for more detail)
- `--concurrency=4` - Number of worker processes (default: CPU count)
- `--pool=prefork` - Worker pool type (default: prefork)

**Example with concurrency:**
```bash
celery -A app.core.celery_app worker --loglevel=info --concurrency=2
```

### Beat Scheduler
Triggers scheduled tasks (like hourly MBON sync) at their configured times.

```bash
celery -A app.core.celery_app beat --loglevel=info
```

**Note:** Only run ONE beat scheduler instance. Multiple beat instances will cause duplicate task execution.

### Combined Worker + Beat (Development Only)
```bash
celery -A app.core.celery_app worker --beat --loglevel=info
```

**Warning:** Not recommended for production. Run worker and beat separately for better control and monitoring.

## Production Deployment

### Using systemd (Linux)

#### 1. Worker Service (`/etc/systemd/system/celery-worker.service`)
```ini
[Unit]
Description=Celery Worker for VettedMe
After=network.target redis.service

[Service]
Type=forking
User=vettedme
Group=vettedme
WorkingDirectory=/opt/vettedme/vettedme-backend
Environment="PATH=/opt/vettedme/venv/bin"
ExecStart=/opt/vettedme/venv/bin/celery -A app.core.celery_app worker \
          --loglevel=info \
          --concurrency=4 \
          --logfile=/var/log/celery/worker.log \
          --pidfile=/var/run/celery/worker.pid
ExecStop=/opt/vettedme/venv/bin/celery -A app.core.celery_app control shutdown
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 2. Beat Service (`/etc/systemd/system/celery-beat.service`)
```ini
[Unit]
Description=Celery Beat Scheduler for VettedMe
After=network.target redis.service

[Service]
Type=simple
User=vettedme
Group=vettedme
WorkingDirectory=/opt/vettedme/vettedme-backend
Environment="PATH=/opt/vettedme/venv/bin"
ExecStart=/opt/vettedme/venv/bin/celery -A app.core.celery_app beat \
          --loglevel=info \
          --logfile=/var/log/celery/beat.log \
          --pidfile=/var/run/celery/beat.pid
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 3. Enable and Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-worker celery-beat
sudo systemctl start celery-worker celery-beat

# Check status
sudo systemctl status celery-worker
sudo systemctl status celery-beat
```

### Using Docker Compose

Add to `docker-compose.prod.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  celery-worker:
    build: .
    command: celery -A app.core.celery_app worker --loglevel=info --concurrency=4
    depends_on:
      - redis
      - db
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - .:/app

  celery-beat:
    build: .
    command: celery -A app.core.celery_app beat --loglevel=info
    depends_on:
      - redis
      - db
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - .:/app

volumes:
  redis_data:
```

## Monitoring

### Flower Web UI
Real-time monitoring dashboard for Celery.

```bash
# Install Flower
pip install flower

# Start Flower
celery -A app.core.celery_app flower

# Access at: http://localhost:5555
```

**Production with authentication:**
```bash
celery -A app.core.celery_app flower \
  --basic_auth=admin:password123 \
  --port=5555
```

### Command-Line Monitoring

**Check active workers:**
```bash
celery -A app.core.celery_app inspect active
```

**Check scheduled tasks:**
```bash
celery -A app.core.celery_app inspect scheduled
```

**Check registered tasks:**
```bash
celery -A app.core.celery_app inspect registered
```

**Worker stats:**
```bash
celery -A app.core.celery_app inspect stats
```

## Scheduled Tasks

### Current Schedule

| Task | Schedule | Description |
|------|----------|-------------|
| `execute_mbon_sync_job` | Hourly (at :00) | Maryland Board of Nursing credential verification |

### Manual Task Execution

```python
from app.core import execute_mbon_sync_job

# Trigger immediately
result = execute_mbon_sync_job.delay()
print(f"Task ID: {result.id}")

# Wait for result (blocking)
print(result.get(timeout=300))  # 5 minute timeout
```

## Troubleshooting

### Worker Won't Start
```bash
# Check Redis connection
redis-cli ping

# Check Celery config
python -c "from app.core.celery_app import celery_app; print(celery_app.conf)"

# Test import
python -c "from app.core import celery_app, execute_mbon_sync_job; print('OK')"
```

### Tasks Not Executing
```bash
# Check beat scheduler is running
celery -A app.core.celery_app inspect scheduled

# Check worker is receiving tasks
celery -A app.core.celery_app inspect active

# Purge all tasks (CAUTION: deletes all pending tasks)
celery -A app.core.celery_app purge
```

### Database Connection Issues
- Ensure `DATABASE_URL` environment variable is set
- Check database is accessible from worker container/host
- Verify `SessionLocal()` is configured correctly

## Logs

### View Worker Logs
```bash
# If using systemd
sudo journalctl -u celery-worker -f

# If running in terminal
# Logs appear in stdout
```

### View Beat Logs
```bash
# If using systemd
sudo journalctl -u celery-beat -f

# If running in terminal
# Logs appear in stdout
```

## Production Checklist

- [ ] Redis server is running and accessible
- [ ] Database connection is configured
- [ ] Environment variables are set
- [ ] Worker service is enabled (systemd/docker)
- [ ] Beat scheduler is running (ONLY ONE INSTANCE)
- [ ] Flower monitoring is accessible (optional)
- [ ] Logs are being written and rotated
- [ ] Health checks are configured
- [ ] Alerts are set up for task failures

## OHCQ Compliance

The MBON sync task ensures Maryland Department of Health compliance by:
- Verifying healthcare credentials hourly
- Updating credential status in real-time
- Maintaining audit trail via timestamps
- Processing 50 credentials per cycle
- Filtering for Maryland (MD) credentials only

## Support

For issues or questions:
1. Check logs for error messages
2. Verify Redis and database connectivity
3. Ensure Celery and dependencies are installed
4. Review task definitions in `app/core/celery_app.py`
