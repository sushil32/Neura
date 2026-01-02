"""FastAPI dependencies for authentication and authorization."""
from typing import Optional
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.utils.security import verify_token

logger = structlog.get_logger()

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None
    
    return await _get_user_from_token(credentials.credentials, db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user. Raises 401 if not authenticated."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await _get_user_from_token(credentials.credentials, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Get current active user. Raises 403 if user is inactive."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    return user


async def get_current_verified_user(
    user: User = Depends(get_current_active_user),
) -> User:
    """Get current verified user. Raises 403 if user is not verified."""
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    return user


async def _get_user_from_token(token: str, db: AsyncSession) -> Optional[User]:
    """Extract and validate user from JWT token."""
    payload = verify_token(token, token_type="access")
    
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return None
    
    result = await db.execute(select(User).where(User.id == user_uuid))
    return result.scalar_one_or_none()


class RequireCredits:
    """Dependency to check if user has enough credits."""
    
    def __init__(self, amount: int):
        self.amount = amount
    
    async def __call__(self, user: User = Depends(get_current_active_user)) -> User:
        if user.credits < self.amount:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient credits. Required: {self.amount}, Available: {user.credits}",
            )
        return user


class RequirePlan:
    """Dependency to check if user has required plan."""
    
    PLAN_LEVELS = {"free": 0, "starter": 1, "pro": 2, "enterprise": 3}
    
    def __init__(self, min_plan: str):
        self.min_plan = min_plan
    
    async def __call__(self, user: User = Depends(get_current_active_user)) -> User:
        user_level = self.PLAN_LEVELS.get(user.plan, 0)
        required_level = self.PLAN_LEVELS.get(self.min_plan, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Plan '{self.min_plan}' or higher required",
            )
        return user

