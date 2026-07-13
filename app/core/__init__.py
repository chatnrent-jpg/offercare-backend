"""
Core Application Infrastructure
Background workers, schedulers, and system configuration
"""

# Optional Celery imports - gracefully degrade if not installed
try:
    from app.core.celery_app import celery_app, execute_mbon_sync_job
    CELERY_AVAILABLE = True
except ImportError:
    celery_app = None
    execute_mbon_sync_job = None
    CELERY_AVAILABLE = False

__all__ = [
    "celery_app",
    "execute_mbon_sync_job",
    "CELERY_AVAILABLE",
]
