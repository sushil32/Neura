"""Video schemas."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VideoType(str, Enum):
    """Video types."""

    EXPLAINER = "explainer"
    TRAINING = "training"
    MARKETING = "marketing"
    PRESENTATION = "presentation"
    CUSTOM = "custom"


class VideoStatus(str, Enum):
    """Video generation status."""

    DRAFT = "draft"
    QUEUED = "queued"
    PROCESSING = "processing"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoCreate(BaseModel):
    """Video creation schema."""

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    type: VideoType = VideoType.CUSTOM
    script: Optional[str] = None
    prompt: Optional[str] = None
    avatar_id: Optional[UUID] = None


class VideoUpdate(BaseModel):
    """Video update schema."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    script: Optional[str] = None
    prompt: Optional[str] = None
    avatar_id: Optional[UUID] = None


class VideoResponse(BaseModel):
    """Video response schema."""

    id: UUID
    user_id: UUID
    avatar_id: Optional[UUID]
    title: str
    description: Optional[str] = None
    type: str
    status: str
    script: Optional[str] = None
    prompt: Optional[str] = None
    video_url: Optional[str] = None
    preview_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    audio_url: Optional[str] = None
    duration: Optional[int] = None
    resolution: Optional[str] = None
    file_size: Optional[int] = None
    video_metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    credits_used: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class VideoGenerateRequest(BaseModel):
    """Request to start video generation."""

    quality: str = Field(default="balanced", pattern="^(fast|balanced|high)$")
    resolution: str = Field(default="1080p", pattern="^(720p|1080p|4k)$")
    preview: bool = False
    
    # Avatar settings (SadTalker)
    emotion: Optional[str] = Field(default=None, pattern="^(neutral|happy|sad|angry|surprised)$")
    expression_scale: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    head_pose_scale: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    use_sadtalker: bool = True  # False = fallback to Wav2Lip
    voice_id: Optional[str] = "default"
    avatar_id: Optional[str] = None


class VideoGenerateResponse(BaseModel):
    """Response for video generation request."""

    video_id: UUID
    job_id: UUID
    status: str
    estimated_time: int  # seconds
    credits_estimated: int

