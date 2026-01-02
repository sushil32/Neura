"""Monitoring and health check endpoints."""
from datetime import datetime, timedelta
from typing import Dict, List

import structlog
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.models.job import Job
from app.utils.monitoring import (
    get_metrics,
    get_metrics_content_type,
    set_active_users,
)

router = APIRouter()
logger = structlog.get_logger()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict:
    """
    Comprehensive health check endpoint.
    
    Checks:
    - Database connectivity
    - Redis connectivity
    - External service availability
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
    }
    
    # Database check
    try:
        await db.execute(select(func.now()))
        health["checks"]["database"] = {"status": "healthy"}
    except Exception as e:
        health["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"
    
    # Redis check
    try:
        import redis.asyncio as redis
        from app.config import settings
        
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        health["checks"]["redis"] = {"status": "healthy"}
    except Exception as e:
        health["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"
    
    # MinIO check
    try:
        from app.utils.storage import storage
        await storage.ensure_bucket_exists()
        health["checks"]["storage"] = {"status": "healthy"}
    except Exception as e:
        health["checks"]["storage"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"
    
    return health


@router.get("/health/live")
async def liveness_check() -> Dict:
    """
    Kubernetes liveness probe.
    
    Returns 200 if the service is running.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> Dict:
    """
    Kubernetes readiness probe.
    
    Returns 200 if the service is ready to accept traffic.
    """
    try:
        await db.execute(select(func.now()))
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        return Response(
            content='{"status": "not_ready"}',
            status_code=503,
            media_type="application/json",
        )


@router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format.
    """
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type(),
    )


@router.get("/stats")
async def application_stats(db: AsyncSession = Depends(get_db)) -> Dict:
    """
    Application statistics for dashboards.
    
    Returns aggregated statistics about users, videos, and jobs.
    """
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # User stats
    total_users = await db.scalar(select(func.count()).select_from(User))
    active_users_24h = await db.scalar(
        select(func.count()).select_from(User).where(User.last_login >= day_ago)
    )
    new_users_7d = await db.scalar(
        select(func.count()).select_from(User).where(User.created_at >= week_ago)
    )
    
    # Update Prometheus gauge
    set_active_users(active_users_24h or 0)
    
    # Video stats
    total_videos = await db.scalar(select(func.count()).select_from(Video))
    videos_today = await db.scalar(
        select(func.count()).select_from(Video).where(Video.created_at >= day_ago)
    )
    videos_by_status = await db.execute(
        select(Video.status, func.count()).group_by(Video.status)
    )
    video_status_counts = {row[0]: row[1] for row in videos_by_status.fetchall()}
    
    # Job stats
    total_jobs = await db.scalar(select(func.count()).select_from(Job))
    jobs_by_status = await db.execute(
        select(Job.status, func.count()).group_by(Job.status)
    )
    job_status_counts = {row[0]: row[1] for row in jobs_by_status.fetchall()}
    
    # Average processing time for completed jobs
    avg_processing_time = await db.scalar(
        select(func.avg(
            func.extract('epoch', Job.completed_at) - func.extract('epoch', Job.started_at)
        )).where(
            Job.status == "completed",
            Job.completed_at.isnot(None),
            Job.started_at.isnot(None),
        )
    )
    
    return {
        "timestamp": now.isoformat(),
        "users": {
            "total": total_users or 0,
            "active_24h": active_users_24h or 0,
            "new_7d": new_users_7d or 0,
        },
        "videos": {
            "total": total_videos or 0,
            "today": videos_today or 0,
            "by_status": video_status_counts,
        },
        "jobs": {
            "total": total_jobs or 0,
            "by_status": job_status_counts,
            "avg_processing_seconds": round(avg_processing_time or 0, 2),
        },
    }


@router.get("/version")
async def version_info() -> Dict:
    """Return application version and build information."""
    import os
    
    return {
        "version": "0.1.0",
        "build": os.getenv("BUILD_NUMBER", "dev"),
        "commit": os.getenv("GIT_COMMIT", "unknown"),
        "environment": os.getenv("ENV", "development"),
    }

