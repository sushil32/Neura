"""Users router."""
from typing import List
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import CreditsHistory
from app.models.user import User
from app.schemas.job import CreditsHistoryListResponse, CreditsHistoryResponse
from app.schemas.user import PasswordChange, UserResponse, UserUpdate
from app.utils.deps import get_current_active_user
from app.utils.security import get_password_hash, verify_password

router = APIRouter()
logger = structlog.get_logger()


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Get current user's profile."""
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    data: UserUpdate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update current user's profile."""
    if data.name is not None:
        user.name = data.name
    
    if data.email is not None and data.email != user.email:
        # Check if email is already taken
        result = await db.execute(select(User).where(User.email == data.email))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )
        user.email = data.email
        user.is_verified = False  # Require re-verification
    
    logger.info("User profile updated", user_id=str(user.id))
    return UserResponse.model_validate(user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChange,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change current user's password."""
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    
    user.password_hash = get_password_hash(data.new_password)
    logger.info("User password changed", user_id=str(user.id))


@router.get("/me/credits", response_model=CreditsHistoryListResponse)
async def get_credits_history(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreditsHistoryListResponse:
    """Get current user's credits history."""
    # Get total count
    count_result = await db.execute(
        select(CreditsHistory).where(CreditsHistory.user_id == user.id)
    )
    total = len(count_result.scalars().all())
    
    # Get paginated history
    result = await db.execute(
        select(CreditsHistory)
        .where(CreditsHistory.user_id == user.id)
        .order_by(CreditsHistory.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    history = result.scalars().all()
    
    return CreditsHistoryListResponse(
        history=[CreditsHistoryResponse.model_validate(h) for h in history],
        total=total,
        current_balance=user.credits,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete current user's account."""
    # Soft delete - just deactivate
    user.is_active = False
    logger.info("User account deleted", user_id=str(user.id))

