"""Videos router."""
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import Job
from app.models.user import User
from app.models.video import Video
from app.schemas.video import (
    VideoCreate,
    VideoGenerateRequest,
    VideoGenerateResponse,
    VideoResponse,
    VideoUpdate,
)
from app.utils.credits import CreditManager, get_credit_manager
from app.utils.deps import RequireCredits, get_current_active_user
from app.workers.tasks import video_generation_task

router = APIRouter()
logger = structlog.get_logger()


@router.post("", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def create_video(
    data: VideoCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VideoResponse:
    """Create a new video draft."""
    video = Video(
        user_id=user.id,
        title=data.title,
        description=data.description,
        type=data.type.value,
        script=data.script,
        prompt=data.prompt,
        avatar_id=data.avatar_id,
        status="draft",
    )
    db.add(video)
    await db.flush()
    
    logger.info("Video created", video_id=str(video.id), user_id=str(user.id))
    return VideoResponse.model_validate(video)


@router.get("", response_model=List[VideoResponse])
async def list_videos(
    status: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[VideoResponse]:
    """List user's videos."""
    query = select(Video).where(Video.user_id == user.id)
    
    if status:
        query = query.where(Video.status == status)
    if type:
        query = query.where(Video.type == type)
    
    query = query.order_by(Video.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    videos = result.scalars().all()
    
    return [VideoResponse.model_validate(v) for v in videos]


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VideoResponse:
    """Get a specific video."""
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == user.id)
    )
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )
    
    return VideoResponse.model_validate(video)


@router.patch("/{video_id}", response_model=VideoResponse)
async def update_video(
    video_id: UUID,
    data: VideoUpdate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VideoResponse:
    """Update a video."""
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == user.id)
    )
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )
    
    if video.status not in ["draft", "failed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only edit draft or failed videos",
        )
    
    if data.title is not None:
        video.title = data.title
    if data.description is not None:
        video.description = data.description
    if data.script is not None:
        video.script = data.script
    if data.prompt is not None:
        video.prompt = data.prompt
    if data.avatar_id is not None:
        video.avatar_id = data.avatar_id
    
    logger.info("Video updated", video_id=str(video.id))
    return VideoResponse.model_validate(video)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a video."""
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == user.id)
    )
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )
    
    await db.delete(video)
    logger.info("Video deleted", video_id=str(video_id))


@router.post("/{video_id}/generate", response_model=VideoGenerateResponse)
async def generate_video(
    video_id: UUID,
    data: VideoGenerateRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VideoGenerateResponse:
    """Start video generation."""
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == user.id)
    )
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )
    
    if video.status not in ["draft", "failed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video is already being processed",
        )
    
    if not video.script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Script is required for video generation",
        )
    
    
    # Estimate credits using CreditManager
    estimated_credits = CreditManager.estimate_video_credits(
        script_length=len(video.script),
        resolution=data.resolution,
    )
    
    # Handle Preview Mode
    script_to_process = video.script
    if data.preview:
        # Truncate script for preview (first 15 words approx)
        words = video.script.split()[:20]
        script_to_process = " ".join(words)
        
        # Force lower settings for speed
        data.resolution = "720p"
        data.quality = "fast"
        
        # Minimal credit cost or free
        estimated_credits = 0  # Free preview? Or small fee. 
        # Let's make it free for now to encourage usage.
        
        logger.info("Generating preview", original_len=len(video.script), preview_len=len(script_to_process))

    # Check credits
    if user.credits < estimated_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Required: {estimated_credits}, Available: {user.credits}",
        )
    
    # Check plan limits
    plan_limits = CreditManager.get_plan_limits(user.plan)
    estimated_duration = len(script_to_process) / 15  # ~15 chars per second
    
    if estimated_duration > plan_limits.get("max_video_length", 60) and not data.preview:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Video too long for {user.plan} plan. Max: {plan_limits['max_video_length']}s",
        )
    
    # Create job
    job = Job(
        user_id=user.id,
        type="video_generation",
        status="queued",
        input_data={
            "video_id": str(video.id),
            "quality": data.quality,
            "resolution": data.resolution,
            "avatar_id": str(video.avatar_id) if video.avatar_id else None,
            "script": script_to_process if data.preview else None,
            "preview": data.preview,
            # Avatar settings
            "emotion": data.emotion,
            "expression_scale": data.expression_scale,
            "head_pose_scale": data.head_pose_scale,
            "use_sadtalker": data.use_sadtalker,
            "voice_id": data.voice_id,
        },
        credits_estimated=estimated_credits,
    )
    db.add(job)
    await db.flush()
    
    # Update video with settings (ONLY if not preview, or update status is fine?)
    # If preview, we shouldn't change the video main resolution/status permanently?
    # Actually, preview is separate.
    # But video_generation_task requires video status to be processing?
    # No, it just updates it.
    
    if not data.preview:
        video.status = "queued"
        video.resolution = data.resolution
    
    await db.commit()
    
    # Queue Celery task for video generation
    try:
        task = video_generation_task.delay(str(job.id))
        job.celery_task_id = task.id
        await db.commit()
        logger.info(
            "Video generation task queued",
            video_id=str(video.id),
            job_id=str(job.id),
            task_id=task.id,
            preview=data.preview,
        )
    except Exception as e:
        logger.error("Failed to queue Celery task", error=str(e))
        # Still return success - task will be picked up by beat scheduler
    
    return VideoGenerateResponse(
        video_id=video.id,
        job_id=job.id,
        status="queued",
        estimated_time=int(estimated_duration * 2),  # Processing time estimate
        credits_estimated=estimated_credits,
    )

