"""Avatars router."""
from typing import List, Optional, Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status, File
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.avatar import Avatar
from app.models.user import User
from app.schemas.avatar import (
    AvatarCreate,
    AvatarListResponse,
    AvatarResponse,
    AvatarUpdate,
)
from app.utils.deps import get_current_active_user
from app.utils.storage import storage, BUCKETS
from app.config import settings
import httpx

router = APIRouter()
logger = structlog.get_logger()


@router.post("", response_model=AvatarResponse, status_code=status.HTTP_201_CREATED)
async def create_avatar(
    data: AvatarCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AvatarResponse:
    """Create a new avatar."""
    avatar = Avatar(
        user_id=user.id,
        name=data.name,
        description=data.description,
        voice_id=data.voice_id,
        config=data.config.model_dump() if data.config else None,
        is_default=data.is_default,
    )
    
    # If setting as default, unset other defaults
    if data.is_default:
        result = await db.execute(
            select(Avatar).where(Avatar.user_id == user.id, Avatar.is_default == True)
        )
        for existing in result.scalars().all():
            existing.is_default = False
    
    db.add(avatar)
    await db.flush()
    
    logger.info("Avatar created", avatar_id=str(avatar.id), user_id=str(user.id))
    return AvatarResponse.model_validate(avatar)


@router.get("", response_model=AvatarListResponse)
async def list_avatars(
    include_public: bool = True,
    include_premium: bool = False,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AvatarListResponse:
    """List available avatars (user's own + public)."""
    base_conditions = [Avatar.user_id == user.id]
    
    if include_public:
        base_conditions.append(Avatar.is_public == True)
        
    query = select(Avatar).where(or_(*base_conditions))
    
    if not include_premium:
        # If not requesting premium, filter out premium UNLESS it's user's own
        query = query.where(or_(Avatar.is_premium == False, Avatar.user_id == user.id))
    
    query = (
        query
        .order_by(Avatar.is_default.desc(), Avatar.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(query)
    avatars = result.scalars().all()
    
    # Get total count
    # Get total count
    count_query = select(Avatar).where(or_(*base_conditions))
    if not include_premium:
        count_query = count_query.where(or_(Avatar.is_premium == False, Avatar.user_id == user.id))
    
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    return AvatarListResponse(
        avatars=[AvatarResponse.model_validate(a) for a in avatars],
        total=total,
    )


@router.get("/{avatar_id}", response_model=AvatarResponse)
async def get_avatar(
    avatar_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AvatarResponse:
    """Get a specific avatar."""
    result = await db.execute(
        select(Avatar).where(
            Avatar.id == avatar_id,
            or_(Avatar.user_id == user.id, Avatar.is_public == True),
        )
    )
    avatar = result.scalar_one_or_none()
    
    if not avatar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        )
    
    return AvatarResponse.model_validate(avatar)


@router.patch("/{avatar_id}", response_model=AvatarResponse)
async def update_avatar(
    avatar_id: UUID,
    data: AvatarUpdate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AvatarResponse:
    """Update an avatar."""
    result = await db.execute(
        select(Avatar).where(Avatar.id == avatar_id, Avatar.user_id == user.id)
    )
    avatar = result.scalar_one_or_none()
    
    if not avatar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found or not owned by user",
        )
    
    if data.name is not None:
        avatar.name = data.name
    if data.description is not None:
        avatar.description = data.description
    if data.voice_id is not None:
        avatar.voice_id = data.voice_id
    if data.config is not None:
        avatar.config = data.config.model_dump()
    
    if data.is_default is True:
        # Unset other defaults
        result = await db.execute(
            select(Avatar).where(
                Avatar.user_id == user.id,
                Avatar.is_default == True,
                Avatar.id != avatar_id,
            )
        )
        for existing in result.scalars().all():
            existing.is_default = False
        avatar.is_default = True
    elif data.is_default is False:
        avatar.is_default = False
    
    logger.info("Avatar updated", avatar_id=str(avatar.id))
    return AvatarResponse.model_validate(avatar)


@router.delete("/{avatar_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(
    avatar_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an avatar."""
    result = await db.execute(
        select(Avatar).where(Avatar.id == avatar_id, Avatar.user_id == user.id)
    )
    avatar = result.scalar_one_or_none()
    
    if not avatar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found or not owned by user",
        )
    
    # 1. Delete from S3 (Best effort)
    if avatar.thumbnail_url:
        try:
            bucket = BUCKETS["avatars"]
            # Extract key from URL: .../bucket_name/key
            if f"/{bucket}/" in avatar.thumbnail_url:
                key = avatar.thumbnail_url.split(f"/{bucket}/")[-1]
                await storage.delete_file(bucket, key)
                logger.info("Avatar image deleted from S3", key=key)
        except Exception as e:
            logger.warning("Failed to delete avatar from S3", error=str(e))

    # 2. Delete from Avatar Service
    try:
        async with httpx.AsyncClient() as client:
            await client.delete(f"{settings.avatar_service_url}/avatars/{avatar_id}", timeout=5.0)
            logger.info("Avatar deleted from service", avatar_id=str(avatar_id))
    except Exception as e:
        logger.warning("Failed to delete avatar from service", error=str(e))

    await db.delete(avatar)
    logger.info("Avatar deleted", avatar_id=str(avatar_id))


@router.post("/{avatar_id}/thumbnail", response_model=AvatarResponse)
async def upload_avatar_thumbnail(
    avatar_id: UUID,
    file: Annotated[UploadFile, File()],
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AvatarResponse:
    """Upload avatar thumbnail image."""
    result = await db.execute(
        select(Avatar).where(Avatar.id == avatar_id, Avatar.user_id == user.id)
    )
    avatar = result.scalar_one_or_none()
    
    if not avatar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found or not owned by user",
        )
    
    # Validate file type
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: JPEG, PNG, WebP",
        )
    
    # Upload to storage
    key = storage.generate_key(f"avatars/{user.id}", file.filename or "thumbnail.jpg")
    content = await file.read()
    url = await storage.upload_bytes(content, BUCKETS["avatars"], key, file.content_type)
    
    avatar.thumbnail_url = url
    logger.info("Avatar thumbnail uploaded", avatar_id=str(avatar.id))
    
    # Sync to Avatar Service
    try:
        async with httpx.AsyncClient() as client:
            files = {'image': (file.filename or "image.png", content, file.content_type or "image/png")}
            data = {'avatar_id': str(avatar.id)}
            # Use internal service URL
            await client.post(f"{settings.avatar_service_url}/avatars/upload", data=data, files=files, timeout=10.0)
            logger.info("Avatar synced to service", avatar_id=str(avatar.id))
    except Exception as e:
        logger.warning("Failed to sync avatar to service", error=str(e))
        # Continue - don't fail user request
    
    return AvatarResponse.model_validate(avatar)

