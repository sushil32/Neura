"""Credit management utilities."""
from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = structlog.get_logger()

# Credit costs for different operations
CREDIT_COSTS = {
    # Video generation
    "video_per_minute": 10,
    "video_minimum": 5,
    "video_4k_multiplier": 2.0,
    "video_1080p_multiplier": 1.0,
    "video_720p_multiplier": 0.5,
    
    # TTS
    "tts_per_1000_chars": 2,
    "voice_clone": 20,
    
    # Live streaming
    "live_per_minute": 5,
    
    # Storage
    "storage_per_gb_month": 10,
}

# Plan credit allocations (monthly)
PLAN_CREDITS = {
    "free": 100,
    "starter": 500,
    "pro": 2000,
    "enterprise": 10000,
}

# Plan limits
PLAN_LIMITS = {
    "free": {
        "max_video_length": 60,  # seconds
        "max_resolution": "720p",
        "concurrent_jobs": 1,
        "storage_gb": 1,
    },
    "starter": {
        "max_video_length": 300,
        "max_resolution": "1080p",
        "concurrent_jobs": 2,
        "storage_gb": 10,
    },
    "pro": {
        "max_video_length": 900,
        "max_resolution": "4k",
        "concurrent_jobs": 5,
        "storage_gb": 100,
    },
    "enterprise": {
        "max_video_length": 3600,
        "max_resolution": "4k",
        "concurrent_jobs": 20,
        "storage_gb": 1000,
    },
}


class CreditManager:
    """Manager for user credits and billing."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_credits(self, user_id: UUID) -> int:
        """Get user's current credit balance."""
        result = await self.db.execute(
            select(User.credits).where(User.id == user_id)
        )
        credits = result.scalar_one_or_none()
        return credits or 0
    
    async def has_credits(self, user_id: UUID, amount: int) -> bool:
        """Check if user has enough credits."""
        credits = await self.get_user_credits(user_id)
        return credits >= amount
    
    async def deduct_credits(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        reference_id: Optional[str] = None,
    ) -> bool:
        """
        Deduct credits from user account.
        
        Args:
            user_id: User ID
            amount: Credits to deduct
            reason: Reason for deduction
            reference_id: Optional reference (job_id, video_id, etc.)
        
        Returns:
            True if successful, False if insufficient credits
        """
        # Atomic update with check
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id, User.credits >= amount)
            .values(credits=User.credits - amount)
            .returning(User.credits)
        )
        
        new_balance = result.scalar_one_or_none()
        
        if new_balance is None:
            logger.warning(
                "Credit deduction failed - insufficient credits",
                user_id=str(user_id),
                amount=amount,
            )
            return False
        
        logger.info(
            "Credits deducted",
            user_id=str(user_id),
            amount=amount,
            new_balance=new_balance,
            reason=reason,
            reference_id=reference_id,
        )
        
        return True
    
    async def add_credits(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        reference_id: Optional[str] = None,
    ) -> int:
        """
        Add credits to user account.
        
        Returns:
            New credit balance
        """
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(credits=User.credits + amount)
            .returning(User.credits)
        )
        
        new_balance = result.scalar_one_or_none()
        
        logger.info(
            "Credits added",
            user_id=str(user_id),
            amount=amount,
            new_balance=new_balance,
            reason=reason,
            reference_id=reference_id,
        )
        
        return new_balance or 0
    
    async def refund_credits(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        reference_id: Optional[str] = None,
    ) -> int:
        """Refund credits (alias for add_credits with logging)."""
        logger.info(
            "Processing credit refund",
            user_id=str(user_id),
            amount=amount,
            reason=reason,
        )
        return await self.add_credits(user_id, amount, f"Refund: {reason}", reference_id)
    
    @staticmethod
    def estimate_video_credits(
        script_length: int,
        resolution: str = "1080p",
    ) -> int:
        """
        Estimate credits for video generation.
        
        Args:
            script_length: Number of characters in script
            resolution: Video resolution
        
        Returns:
            Estimated credits
        """
        # Estimate duration (~15 chars per second of speech)
        estimated_seconds = script_length / 15
        estimated_minutes = estimated_seconds / 60
        
        # Base cost
        base_credits = int(estimated_minutes * CREDIT_COSTS["video_per_minute"])
        base_credits = max(base_credits, CREDIT_COSTS["video_minimum"])
        
        # Resolution multiplier
        resolution_multipliers = {
            "720p": CREDIT_COSTS["video_720p_multiplier"],
            "1080p": CREDIT_COSTS["video_1080p_multiplier"],
            "4k": CREDIT_COSTS["video_4k_multiplier"],
        }
        multiplier = resolution_multipliers.get(resolution, 1.0)
        
        return int(base_credits * multiplier)
    
    @staticmethod
    def estimate_tts_credits(text_length: int) -> int:
        """Estimate credits for TTS generation."""
        return max(1, text_length // 1000 * CREDIT_COSTS["tts_per_1000_chars"])
    
    @staticmethod
    def estimate_live_credits(duration_minutes: float) -> int:
        """Estimate credits for live streaming."""
        return int(duration_minutes * CREDIT_COSTS["live_per_minute"])
    
    @staticmethod
    def get_plan_credits(plan: str) -> int:
        """Get monthly credit allocation for a plan."""
        return PLAN_CREDITS.get(plan, PLAN_CREDITS["free"])
    
    @staticmethod
    def get_plan_limits(plan: str) -> dict:
        """Get limits for a plan."""
        return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    
    @staticmethod
    def check_plan_limit(
        plan: str,
        limit_type: str,
        value: float,
    ) -> tuple[bool, str]:
        """
        Check if a value is within plan limits.
        
        Returns:
            Tuple of (is_allowed, error_message)
        """
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
        limit = limits.get(limit_type)
        
        if limit is None:
            return True, ""
        
        if value > limit:
            return False, f"Exceeds {plan} plan limit for {limit_type} ({limit})"
        
        return True, ""


async def get_credit_manager(db: AsyncSession) -> CreditManager:
    """Dependency to get credit manager."""
    return CreditManager(db)

