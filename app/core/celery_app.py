"""
Celery Background Worker Infrastructure
Initializes Celery with Redis broker and schedules OHCQ compliance tasks

Configuration:
- Redis message broker for task queue
- Hourly MBON scraper synchronization
- New York timezone for Maryland operations
"""

from celery import Celery
from celery.schedules import crontab

# Initialize Celery and bind it to the Redis backend broker
celery_app = Celery(
    "vettedme_workers",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

# Configure performance tweaks and strict time handling
celery_app.conf.update(
    timezone="America/New_York",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ack_late=True,
    worker_prefetch_multiplier=1
)

# 🗓️ Schedule the OHCQ Scraper Sync Cycle to run automatically every hour
celery_app.conf.beat_schedule = {
    "run-mbon-scraper-sync-hourly": {
        "task": "app.core.celery_app.execute_mbon_sync_job",
        "schedule": crontab(minute=0),  # Runs at the top of every hour
    },
}


# ============================================================================
# Task Implementation: MBON Scraper Synchronization
# ============================================================================

import asyncio
from app.database import SessionLocal  # Standard SQLAlchemy sessionmaker
from app.workers.mbon_scraper import MBONScraperPool


@celery_app.task(name="app.core.celery_app.execute_mbon_sync_job")
def execute_mbon_sync_job():
    """
    Celery entry point that safely wraps the async MBON synchronization pool loop
    and injects a clean, short-lived production database session handler.
    
    Process:
    1. Creates fresh database session via SessionLocal()
    2. Instantiates MBONScraperPool with optional proxy rotation
    3. Executes async run_sync_cycle() via asyncio.run()
    4. Handles errors with rollback
    5. Ensures session cleanup in finally block
    
    Scheduled: Hourly at minute 0 via Celery Beat
    
    Raises:
        RuntimeError: If MBON synchronization fails
    """
    db = SessionLocal()
    try:
        # Instantiate scraper pool with custom rotation proxies if available
        scraper_pool = MBONScraperPool(proxies=[])
        
        # Drive the async execution loop cleanly inside the synchronous Celery worker thread
        asyncio.run(scraper_pool.run_sync_cycle(db))
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Automated background MBON synchronization failed: {str(e)}")
    finally:
        db.close()
