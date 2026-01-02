"""Authentication router."""
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import Session, User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)

router = APIRouter()
logger = structlog.get_logger()


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Register a new user."""
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    # Create new user
    user = User(
        email=data.email,
        password_hash=get_password_hash(data.password),
        name=data.name,
        credits=100,  # Free starter credits
    )
    db.add(user)
    await db.flush()
    
    # Create tokens
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)
    
    # Store refresh token in session
    session = Session.create_session(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_days=settings.jwt_refresh_token_expire_days,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    
    logger.info("User registered", user_id=str(user.id), email=user.email)
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user_id=str(user.id),
        email=user.email,
        name=user.name,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Login with email and password."""
    # Find user
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    
    # Create tokens
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)
    
    # Store refresh token in session
    session = Session.create_session(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_days=settings.jwt_refresh_token_expire_days,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    
    logger.info("User logged in", user_id=str(user.id), email=user.email)
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user_id=str(user.id),
        email=user.email,
        name=user.name,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh access token using refresh token."""
    # Verify refresh token
    payload = verify_token(data.refresh_token, token_type="refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    
    # Find session
    result = await db.execute(
        select(Session)
        .where(Session.refresh_token == data.refresh_token)
        .where(Session.is_revoked == False)
        .where(Session.expires_at > datetime.utcnow())
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or expired",
        )
    
    # Get user
    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )
    
    # Create new access token
    access_token = create_access_token(user.id, user.email)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=data.refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Logout and revoke refresh token."""
    # Find and revoke session
    result = await db.execute(
        select(Session).where(Session.refresh_token == data.refresh_token)
    )
    session = result.scalar_one_or_none()
    
    if session:
        session.is_revoked = True
        logger.info("User logged out", user_id=str(session.user_id))

