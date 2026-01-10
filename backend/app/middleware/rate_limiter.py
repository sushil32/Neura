"""Rate limiting middleware using Redis."""
import time
from typing import Callable, Optional

import structlog
from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = structlog.get_logger()

# Rate limit configurations per endpoint type
RATE_LIMITS = {
    # Format: (requests, window_seconds)
    "default": (100, 60),           # 100 req/min
    "auth": (20, 60),               # 20 req/min for auth endpoints
    "generate": (10, 60),           # 10 req/min for generation
    "upload": (20, 60),             # 20 req/min for uploads
    "live": (60, 60),               # 60 req/min for live sessions
    "api_key": (1000, 60),          # 1000 req/min for API key auth
}

# Endpoint patterns and their rate limit types
ENDPOINT_PATTERNS = {
    "/api/auth/": "auth",
    "/api/videos/": "generate",
    "/api/uploads/": "upload",
    "/api/live/": "live",
    "/ws/": "live",
}


class RateLimiter:
    """Redis-backed rate limiter with sliding window."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.
        
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = time.time()
        window_start = now - window
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests in window
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiry
        pipe.expire(key, window)
        
        results = await pipe.execute()
        request_count = results[1]
        
        remaining = max(0, limit - request_count - 1)
        reset_at = int(now + window)
        
        info = {
            "limit": limit,
            "remaining": remaining,
            "reset": reset_at,
            "window": window,
        }
        
        return request_count < limit, info


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""
    
    def __init__(
        self,
        app,
        redis_url: Optional[str] = None,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.enabled = enabled
        self._redis = None
        self._redis_url = redis_url or settings.redis_url
        self._limiter = None
    
    async def _get_redis(self):
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                self._limiter = RateLimiter(self._redis)
            except Exception as e:
                logger.warning("Redis not available for rate limiting", error=str(e))
        return self._redis
    
    def _get_rate_limit_type(self, path: str) -> str:
        """Get rate limit type for a path."""
        for pattern, limit_type in ENDPOINT_PATTERNS.items():
            if path.startswith(pattern):
                return limit_type
        return "default"
    
    def _get_client_key(self, request: Request) -> str:
        """Get rate limit key for client."""
        # Try to get user ID from auth
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"rate:user:{user_id}"
        
        # Fall back to IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check for proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        return f"rate:ip:{client_ip}"
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request with rate limiting."""
        if not self.enabled:
            return await call_next(request)
        
        # Skip rate limiting for certain paths
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        redis = await self._get_redis()
        if not redis or not self._limiter:
            # If Redis unavailable, allow request
            return await call_next(request)
        
        # Determine rate limit
        limit_type = self._get_rate_limit_type(request.url.path)
        limit, window = RATE_LIMITS.get(limit_type, RATE_LIMITS["default"])
        
        # Get client key
        client_key = self._get_client_key(request)
        rate_key = f"{client_key}:{limit_type}"
        
        try:
            is_allowed, info = await self._limiter.is_allowed(rate_key, limit, window)
            
            # Add rate limit headers to response
            headers = {
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
                "X-RateLimit-Reset": str(info["reset"]),
            }
            
            if not is_allowed:
                logger.warning(
                    "Rate limit exceeded",
                    client_key=client_key,
                    limit_type=limit_type,
                    path=request.url.path,
                )
                
                return Response(
                    content='{"detail": "Rate limit exceeded. Please try again later."}',
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={
                        **headers,
                        "Retry-After": str(info["window"]),
                        "Content-Type": "application/json",
                    },
                )
            
            response = await call_next(request)
            
            # Add headers to successful response
            for key, value in headers.items():
                response.headers[key] = value
            
            return response
            
        except Exception as e:
            logger.error("Rate limiting error", error=str(e), exc_info=True)
            # On error, bypass rate limiting and proceed with request
            try:
                return await call_next(request)
            except Exception as inner_e:
                logger.error("Error in call_next after rate limit error", error=str(inner_e))
                # Last resort: return a 500 error
                return Response(
                    content='{"detail": "Internal server error"}',
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    headers={"Content-Type": "application/json"},
                )

