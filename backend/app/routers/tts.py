"""Text-to-Speech router."""
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.voice import VoiceProfile
from app.schemas.voice import (
    VoiceCloneRequest,
    VoiceCreate,
    VoiceListResponse,
    VoiceResponse,
    VoiceUpdate,
)
from app.utils.deps import RequireCredits, get_current_active_user

router = APIRouter()
logger = structlog.get_logger()

# TTS costs
TTS_CREDITS_PER_1000_CHARS = 1


class TTSRequest(BaseModel):
    """Text-to-speech request."""
    text: str = Field(..., min_length=1, max_length=5000)
    voice_id: Optional[UUID] = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=2.0)
    format: str = Field(default="mp3", pattern="^(mp3|wav|ogg)$")


class TTSResponse(BaseModel):
    """Text-to-speech response."""
    audio_url: str
    duration: float  # seconds
    word_timings: list  # For lip sync
    credits_used: int


class TTSStreamRequest(BaseModel):
    """Request for streaming TTS."""
    text: str = Field(..., min_length=1, max_length=5000)
    voice_id: Optional[UUID] = None


# Voice profile endpoints

@router.get("/voices", response_model=VoiceListResponse)
async def list_voices(
    include_public: bool = True,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VoiceListResponse:
    """List available voice profiles."""
    from sqlalchemy import or_
    
    conditions = [VoiceProfile.user_id == user.id]
    if include_public:
        conditions.append(VoiceProfile.is_public == True)
    
    query = (
        select(VoiceProfile)
        .where(or_(*conditions))
        .order_by(VoiceProfile.is_default.desc(), VoiceProfile.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(query)
    voices = result.scalars().all()
    
    # Get total count
    count_query = select(VoiceProfile).where(or_(*conditions))
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    return VoiceListResponse(
        voices=[VoiceResponse.model_validate(v) for v in voices],
        total=total,
    )


@router.post("/voices", response_model=VoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_voice(
    data: VoiceCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VoiceResponse:
    """Create a new voice profile."""
    voice = VoiceProfile(
        user_id=user.id,
        name=data.name,
        description=data.description,
        language=data.language,
        gender=data.gender,
        config=data.config.model_dump() if data.config else None,
        is_default=data.is_default,
    )
    
    if data.is_default:
        # Unset other defaults
        result = await db.execute(
            select(VoiceProfile).where(
                VoiceProfile.user_id == user.id,
                VoiceProfile.is_default == True,
            )
        )
        for existing in result.scalars().all():
            existing.is_default = False
    
    db.add(voice)
    await db.flush()
    
    logger.info("Voice profile created", voice_id=str(voice.id))
    return VoiceResponse.model_validate(voice)


@router.get("/voices/{voice_id}", response_model=VoiceResponse)
async def get_voice(
    voice_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VoiceResponse:
    """Get a specific voice profile."""
    from sqlalchemy import or_
    
    result = await db.execute(
        select(VoiceProfile).where(
            VoiceProfile.id == voice_id,
            or_(VoiceProfile.user_id == user.id, VoiceProfile.is_public == True),
        )
    )
    voice = result.scalar_one_or_none()
    
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice profile not found",
        )
    
    return VoiceResponse.model_validate(voice)


@router.patch("/voices/{voice_id}", response_model=VoiceResponse)
async def update_voice(
    voice_id: UUID,
    data: VoiceUpdate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VoiceResponse:
    """Update a voice profile."""
    result = await db.execute(
        select(VoiceProfile).where(
            VoiceProfile.id == voice_id,
            VoiceProfile.user_id == user.id,
        )
    )
    voice = result.scalar_one_or_none()
    
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice profile not found or not owned by user",
        )
    
    if data.name is not None:
        voice.name = data.name
    if data.description is not None:
        voice.description = data.description
    if data.language is not None:
        voice.language = data.language
    if data.gender is not None:
        voice.gender = data.gender
    if data.config is not None:
        voice.config = data.config.model_dump()
    
    if data.is_default is True:
        result = await db.execute(
            select(VoiceProfile).where(
                VoiceProfile.user_id == user.id,
                VoiceProfile.is_default == True,
                VoiceProfile.id != voice_id,
            )
        )
        for existing in result.scalars().all():
            existing.is_default = False
        voice.is_default = True
    elif data.is_default is False:
        voice.is_default = False
    
    logger.info("Voice profile updated", voice_id=str(voice.id))
    return VoiceResponse.model_validate(voice)


@router.delete("/voices/{voice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice(
    voice_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a voice profile."""
    result = await db.execute(
        select(VoiceProfile).where(
            VoiceProfile.id == voice_id,
            VoiceProfile.user_id == user.id,
        )
    )
    voice = result.scalar_one_or_none()
    
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice profile not found or not owned by user",
        )
    
    await db.delete(voice)
    logger.info("Voice profile deleted", voice_id=str(voice_id))


# TTS generation endpoints

@router.post("/generate", response_model=TTSResponse)
async def generate_tts(
    data: TTSRequest,
    user: User = Depends(RequireCredits(TTS_CREDITS_PER_1000_CHARS)),
    db: AsyncSession = Depends(get_db),
) -> TTSResponse:
    """Generate speech from text."""
    # Calculate credits
    credits_needed = max(1, len(data.text) // 1000 * TTS_CREDITS_PER_1000_CHARS)
    
    if user.credits < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {credits_needed}, have {user.credits}",
        )
    
    # Get voice profile if specified
    voice = None
    if data.voice_id:
        from sqlalchemy import or_
        
        result = await db.execute(
            select(VoiceProfile).where(
                VoiceProfile.id == data.voice_id,
                or_(VoiceProfile.user_id == user.id, VoiceProfile.is_public == True),
            )
        )
        voice = result.scalar_one_or_none()
        if not voice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice profile not found",
            )
    
    # TODO: Integrate with actual TTS service
    # For now, return placeholder response
    logger.info(
        "TTS generation requested",
        text_length=len(data.text),
        voice_id=str(data.voice_id) if data.voice_id else None,
    )
    
    # Deduct credits
    user.credits -= credits_needed
    
    return TTSResponse(
        audio_url="https://storage.example.com/audio/generated.mp3",
        duration=len(data.text) / 15,  # Rough estimate: 15 chars per second
        word_timings=[],  # Would contain actual word timings
        credits_used=credits_needed,
    )


@router.post("/stream")
async def stream_tts(
    data: TTSStreamRequest,
    user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    """Stream TTS audio in real-time."""
    
    async def audio_generator():
        """Generate audio chunks."""
        # TODO: Integrate with actual TTS streaming
        # This is a placeholder that would yield audio chunks
        yield b""
    
    return StreamingResponse(
        audio_generator(),
        media_type="audio/mpeg",
        headers={
            "Transfer-Encoding": "chunked",
            "X-Content-Duration": str(len(data.text) / 15),
        },
    )

