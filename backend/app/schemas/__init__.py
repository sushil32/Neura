"""Pydantic schemas for NEURA."""
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.avatar import (
    AvatarConfig,
    AvatarCreate,
    AvatarResponse,
    AvatarUpdate,
)
from app.schemas.job import JobCreate, JobResponse, JobStatus
from app.schemas.user import UserCreate, UserProfile, UserResponse, UserUpdate
from app.schemas.video import VideoCreate, VideoResponse, VideoStatus, VideoUpdate
from app.schemas.voice import VoiceConfig, VoiceCreate, VoiceResponse, VoiceUpdate

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "RefreshRequest",
    "TokenResponse",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserProfile",
    # Video
    "VideoCreate",
    "VideoUpdate",
    "VideoResponse",
    "VideoStatus",
    # Avatar
    "AvatarCreate",
    "AvatarUpdate",
    "AvatarResponse",
    "AvatarConfig",
    # Voice
    "VoiceCreate",
    "VoiceUpdate",
    "VoiceResponse",
    "VoiceConfig",
    # Job
    "JobCreate",
    "JobResponse",
    "JobStatus",
]

