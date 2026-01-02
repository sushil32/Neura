"""Authentication schemas."""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(None, max_length=255)


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class LoginResponse(TokenResponse):
    """Login response with user info."""

    user_id: str
    email: str
    name: Optional[str] = None


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str

