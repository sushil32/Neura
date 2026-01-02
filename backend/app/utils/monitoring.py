"""Monitoring and observability utilities."""
import os
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Callable, Dict, Optional

import structlog

from app.config import settings

logger = structlog.get_logger()

# =====================
# Prometheus Metrics
# =====================

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed, metrics disabled")

if PROMETHEUS_AVAILABLE:
    # Request metrics
    REQUEST_COUNT = Counter(
        "neura_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    
    REQUEST_LATENCY = Histogram(
        "neura_http_request_duration_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    
    # Video generation metrics
    VIDEO_GENERATION_COUNT = Counter(
        "neura_video_generations_total",
        "Total video generation jobs",
        ["status", "resolution"],
    )
    
    VIDEO_GENERATION_DURATION = Histogram(
        "neura_video_generation_duration_seconds",
        "Video generation duration",
        ["resolution"],
        buckets=[10, 30, 60, 120, 300, 600, 1200, 1800, 3600],
    )
    
    # Live session metrics
    LIVE_SESSIONS_ACTIVE = Gauge(
        "neura_live_sessions_active",
        "Number of active live sessions",
    )
    
    LIVE_SESSION_MESSAGES = Counter(
        "neura_live_session_messages_total",
        "Total messages in live sessions",
        ["type"],
    )
    
    # TTS metrics
    TTS_REQUESTS = Counter(
        "neura_tts_requests_total",
        "Total TTS requests",
        ["voice", "status"],
    )
    
    TTS_DURATION = Histogram(
        "neura_tts_duration_seconds",
        "TTS generation duration",
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    )
    
    # User metrics
    ACTIVE_USERS = Gauge(
        "neura_active_users",
        "Number of active users (24h)",
    )
    
    USER_REGISTRATIONS = Counter(
        "neura_user_registrations_total",
        "Total user registrations",
    )
    
    # Credit metrics
    CREDITS_USED = Counter(
        "neura_credits_used_total",
        "Total credits used",
        ["operation"],
    )
    
    # System info
    SYSTEM_INFO = Info(
        "neura_system",
        "System information",
    )
    SYSTEM_INFO.info({
        "version": "0.1.0",
        "environment": settings.env,
    })


class MetricsMiddleware:
    """FastAPI middleware for collecting request metrics."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not PROMETHEUS_AVAILABLE:
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        
        # Capture response status
        status_code = 500
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            
            # Get path
            path = scope.get("path", "/")
            method = scope.get("method", "GET")
            
            # Normalize path (remove IDs)
            normalized_path = self._normalize_path(path)
            
            # Record metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=normalized_path,
                status=str(status_code),
            ).inc()
            
            REQUEST_LATENCY.labels(
                method=method,
                endpoint=normalized_path,
            ).observe(duration)
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing IDs with placeholders."""
        import re
        
        # Replace UUIDs
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            path,
        )
        
        # Replace numeric IDs
        path = re.sub(r"/\d+(/|$)", "/{id}\\1", path)
        
        return path


def get_metrics():
    """Get Prometheus metrics as text."""
    if not PROMETHEUS_AVAILABLE:
        return ""
    return generate_latest()


def get_metrics_content_type():
    """Get content type for metrics response."""
    if not PROMETHEUS_AVAILABLE:
        return "text/plain"
    return CONTENT_TYPE_LATEST


# =====================
# Sentry Integration
# =====================

_sentry_initialized = False

def init_sentry(dsn: Optional[str] = None) -> bool:
    """Initialize Sentry error tracking."""
    global _sentry_initialized
    
    if _sentry_initialized:
        return True
    
    dsn = dsn or os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("Sentry DSN not configured, error tracking disabled")
        return False
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        
        sentry_sdk.init(
            dsn=dsn,
            environment=settings.env,
            release=f"neura@0.1.0",
            traces_sample_rate=0.1 if settings.env == "production" else 1.0,
            profiles_sample_rate=0.1 if settings.env == "production" else 0.0,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration(),
            ],
            before_send=_sentry_before_send,
        )
        
        _sentry_initialized = True
        logger.info("Sentry initialized", environment=settings.env)
        return True
        
    except ImportError:
        logger.warning("sentry_sdk not installed, error tracking disabled")
        return False
    except Exception as e:
        logger.error("Failed to initialize Sentry", error=str(e))
        return False


def _sentry_before_send(event, hint):
    """Filter events before sending to Sentry."""
    # Filter out certain exceptions
    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]
        
        # Don't report 4xx errors
        from fastapi import HTTPException
        if isinstance(exc_value, HTTPException) and exc_value.status_code < 500:
            return None
    
    # Scrub sensitive data
    if "request" in event:
        headers = event["request"].get("headers", {})
        if "Authorization" in headers:
            headers["Authorization"] = "[FILTERED]"
        if "Cookie" in headers:
            headers["Cookie"] = "[FILTERED]"
    
    return event


def capture_exception(exc: Exception, **context):
    """Capture exception to Sentry."""
    if not _sentry_initialized:
        return
    
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except ImportError:
        pass


def capture_message(message: str, level: str = "info", **context):
    """Capture message to Sentry."""
    if not _sentry_initialized:
        return
    
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_message(message, level=level)
    except ImportError:
        pass


# =====================
# Performance Tracking
# =====================

def track_video_generation(resolution: str, status: str, duration: float):
    """Track video generation metrics."""
    if not PROMETHEUS_AVAILABLE:
        return
    
    VIDEO_GENERATION_COUNT.labels(
        status=status,
        resolution=resolution,
    ).inc()
    
    if status == "completed":
        VIDEO_GENERATION_DURATION.labels(
            resolution=resolution,
        ).observe(duration)


def track_tts_request(voice: str, status: str, duration: float):
    """Track TTS request metrics."""
    if not PROMETHEUS_AVAILABLE:
        return
    
    TTS_REQUESTS.labels(voice=voice, status=status).inc()
    
    if status == "success":
        TTS_DURATION.observe(duration)


def track_live_session(active: bool):
    """Track live session count."""
    if not PROMETHEUS_AVAILABLE:
        return
    
    if active:
        LIVE_SESSIONS_ACTIVE.inc()
    else:
        LIVE_SESSIONS_ACTIVE.dec()


def track_live_message(message_type: str):
    """Track live session message."""
    if not PROMETHEUS_AVAILABLE:
        return
    
    LIVE_SESSION_MESSAGES.labels(type=message_type).inc()


def track_credits_used(operation: str, amount: int):
    """Track credits usage."""
    if not PROMETHEUS_AVAILABLE:
        return
    
    CREDITS_USED.labels(operation=operation).inc(amount)


def track_user_registration():
    """Track user registration."""
    if not PROMETHEUS_AVAILABLE:
        return
    
    USER_REGISTRATIONS.inc()


def set_active_users(count: int):
    """Set active users gauge."""
    if not PROMETHEUS_AVAILABLE:
        return
    
    ACTIVE_USERS.set(count)


# =====================
# Timing Decorator
# =====================

def timed(metric_name: str = None):
    """Decorator to measure function execution time."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start
                logger.debug(
                    "Function executed",
                    function=func.__name__,
                    duration=duration,
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                logger.debug(
                    "Function executed",
                    function=func.__name__,
                    duration=duration,
                )
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

