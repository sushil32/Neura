"""User schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """User creation schema."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(None, max_length=255)


class UserUpdate(BaseModel):
    """User update schema."""

    name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None


class UserResponse(BaseModel):
    """User response schema."""

    id: UUID
    email: str
    name: Optional[str]
    plan: str
    credits: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserProfile(BaseModel):
    """User profile for public display."""

    id: UUID
    name: Optional[str]
    plan: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    """Password change request."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class CreditsPurchase(BaseModel):
    """Credits purchase request."""

    amount: int = Field(..., gt=0, le=10000)
    payment_method: str

