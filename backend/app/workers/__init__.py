"""Celery workers for NEURA."""
from app.workers.celery_app import celery_app
from app.workers.tasks import video_generation, tts_generation

__all__ = [
    "celery_app",
    "video_generation",
    "tts_generation",
]

