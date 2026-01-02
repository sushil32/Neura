"""Avatar schemas."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AvatarStyle(str, Enum):
    """Avatar visual styles."""

    REALISTIC = "realistic"
    CARTOON = "cartoon"
    THREE_D = "3d"


class AvatarGender(str, Enum):
    """Avatar gender options."""

    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class BackgroundConfig(BaseModel):
    """Background configuration."""

    type: str = Field(
        default="solid", pattern="^(solid|gradient|image|video|transparent)$"
    )
    value: str = "#FFFFFF"


class LipSyncConfig(BaseModel):
    """Lip sync configuration."""

    model: str = Field(default="wav2lip", pattern="^(wav2lip|sadtalker)$")
    quality: str = Field(default="balanced", pattern="^(fast|balanced|high)$")


class AvatarConfig(BaseModel):
    """Full avatar configuration."""

    style: AvatarStyle = AvatarStyle.REALISTIC
    gender: AvatarGender = AvatarGender.NEUTRAL
    age_range: str = Field(default="adult", pattern="^(young|adult|senior)$")
    background: BackgroundConfig = BackgroundConfig()
    expressions: Dict[str, Any] = {
        "default": "neutral",
        "available": ["neutral", "happy", "sad", "surprised"],
    }
    lip_sync: LipSyncConfig = LipSyncConfig()


class AvatarCreate(BaseModel):
    """Avatar creation schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    voice_id: Optional[UUID] = None
    config: Optional[AvatarConfig] = None
    is_default: bool = False


class AvatarUpdate(BaseModel):
    """Avatar update schema."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    voice_id: Optional[UUID] = None
    config: Optional[AvatarConfig] = None
    is_default: Optional[bool] = None


class AvatarResponse(BaseModel):
    """Avatar response schema."""

    id: UUID
    user_id: Optional[UUID]
    voice_id: Optional[UUID]
    name: str
    description: Optional[str]
    model_path: Optional[str]
    thumbnail_url: Optional[str]
    config: Optional[Dict[str, Any]]
    is_default: bool
    is_public: bool
    is_premium: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AvatarListResponse(BaseModel):
    """Avatar list response."""

    avatars: List[AvatarResponse]
    total: int

