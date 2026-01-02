"""Jobs router."""
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobListResponse, JobResponse
from app.utils.deps import get_current_active_user

router = APIRouter()
logger = structlog.get_logger()


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """List user's jobs."""
    query = select(Job).where(Job.user_id == user.id)
    
    if status:
        query = query.where(Job.status == status)
    if type:
        query = query.where(Job.type == type)
    
    # Get total count
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())
    
    # Get paginated results
    query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return JobListResponse(
        jobs=[JobResponse.model_validate(j) for j in jobs],
        total=total,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Get a specific job."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    return JobResponse.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Cancel a pending or processing job."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    if job.status not in ["pending", "queued", "processing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status}",
        )
    
    # Cancel the Celery task if running
    if job.celery_task_id:
        # TODO: Revoke Celery task
        # from app.workers.celery_app import celery_app
        # celery_app.control.revoke(job.celery_task_id, terminate=True)
        pass
    
    job.status = "cancelled"
    logger.info("Job cancelled", job_id=str(job.id))
    
    return JobResponse.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a completed or cancelled job."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    if job.status in ["pending", "queued", "processing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete active job. Cancel it first.",
        )
    
    await db.delete(job)
    logger.info("Job deleted", job_id=str(job_id))

