"""Celery application configuration."""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "neura",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 minutes soft limit
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
    
    # Result backend settings
    result_expires=86400,  # 24 hours
    
    # Beat schedule for periodic tasks
    beat_schedule={
        "cleanup-expired-sessions": {
            "task": "app.workers.tasks.cleanup_expired_sessions",
            "schedule": 3600.0,  # Every hour
        },
        "process-pending-jobs": {
            "task": "app.workers.tasks.process_pending_jobs",
            "schedule": 60.0,  # Every minute
        },
    },
)

# Task routes for different queues
celery_app.conf.task_routes = {
    "app.workers.tasks.video_generation.*": {"queue": "gpu"},
    "app.workers.tasks.tts_generation.*": {"queue": "gpu"},
    "app.workers.tasks.*": {"queue": "default"},
}

