"""Voice profile schemas."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VoiceStyle(str, Enum):
    """Voice speaking styles."""

    CONVERSATIONAL = "conversational"
    FORMAL = "formal"
    NEWS = "news"
    STORYTELLING = "storytelling"


class VoiceEmotion(str, Enum):
    """Voice emotion options."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"


class VoiceConfig(BaseModel):
    """Voice configuration."""

    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=2.0)
    style: VoiceStyle = VoiceStyle.CONVERSATIONAL
    emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    provider: str = "coqui"


class VoiceCreate(BaseModel):
    """Voice profile creation schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    language: str = Field(default="en", max_length=10)
    gender: Optional[str] = Field(None, pattern="^(male|female|neutral)$")
    config: Optional[VoiceConfig] = None
    is_default: bool = False


class VoiceUpdate(BaseModel):
    """Voice profile update schema."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    language: Optional[str] = Field(None, max_length=10)
    gender: Optional[str] = Field(None, pattern="^(male|female|neutral)$")
    config: Optional[VoiceConfig] = None
    is_default: Optional[bool] = None


class VoiceResponse(BaseModel):
    """Voice profile response schema."""

    id: UUID
    user_id: Optional[UUID]
    name: str
    description: Optional[str]
    language: str
    gender: Optional[str]
    sample_path: Optional[str]
    model_path: Optional[str]
    config: Optional[Dict[str, Any]]
    preview_url: Optional[str]
    is_default: bool
    is_public: bool
    is_cloned: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VoiceListResponse(BaseModel):
    """Voice list response."""

    voices: List[VoiceResponse]
    total: int


class VoiceCloneRequest(BaseModel):
    """Voice cloning request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    language: str = "en"
    # Audio file will be uploaded separately

