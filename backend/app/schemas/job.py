"""Job schemas."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobType(str, Enum):
    """Job types."""

    VIDEO_GENERATION = "video_generation"
    LIVE_SESSION = "live_session"
    TTS_GENERATION = "tts_generation"
    AVATAR_TRAINING = "avatar_training"
    VOICE_CLONING = "voice_cloning"


class JobStatus(str, Enum):
    """Job status."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCreate(BaseModel):
    """Job creation schema."""

    type: JobType
    input_data: Optional[Dict[str, Any]] = None
    priority: int = Field(default=0, ge=0, le=10)


class JobResponse(BaseModel):
    """Job response schema."""

    id: UUID
    user_id: UUID
    type: str
    status: str
    priority: int
    progress: float
    current_step: Optional[str]
    input_data: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    credits_estimated: int
    credits_used: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Job list response."""

    jobs: List[JobResponse]
    total: int


class JobProgress(BaseModel):
    """Job progress update."""

    id: UUID
    status: str
    progress: float
    current_step: Optional[str]
    estimated_remaining: Optional[int]  # seconds


class CreditsHistoryResponse(BaseModel):
    """Credits history response."""

    id: UUID
    amount: int
    action: str
    description: Optional[str]
    balance_after: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditsHistoryListResponse(BaseModel):
    """Credits history list response."""

    history: List[CreditsHistoryResponse]
    total: int
    current_balance: int

