"""NEURA Backend API - Main Application Entry Point."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import close_db, init_db
from app.middleware import RateLimitMiddleware, SecurityMiddleware
from app.routers import auth, avatars, jobs, live, llm, tts, users, videos, monitoring
from app.utils.logging import setup_logging
from app.utils.monitoring import MetricsMiddleware, init_sentry, capture_exception

# Setup structured logging
setup_logging()
logger = structlog.get_logger()

# Initialize Sentry for error tracking
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting NEURA backend", env=settings.env)
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down NEURA backend")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="NEURA API",
    description="Real-Time AI Avatar & Video Generation Platform",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# ====================
# Middleware Stack
# ====================
# Note: Middleware is applied in reverse order (last added = first executed)

# 1. CORS - Must be first (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    ],
)

# 2. Trusted Host (prevent host header attacks)
if settings.env == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts_list if hasattr(settings, 'allowed_hosts_list') else ["*"],
    )

# 3. GZip compression for responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 4. Security headers
app.add_middleware(SecurityMiddleware)

# 5. Rate limiting
app.add_middleware(
    RateLimitMiddleware,
    redis_url=settings.redis_url,
    enabled=settings.env != "test",  # Disable in tests
)

# 6. Prometheus metrics collection
app.add_middleware(MetricsMiddleware)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(videos.router, prefix="/api/v1/videos", tags=["Videos"])
app.include_router(avatars.router, prefix="/api/v1/avatars", tags=["Avatars"])
app.include_router(live.router, prefix="/api/v1/live", tags=["Live Streaming"])
app.include_router(tts.router, prefix="/api/v1/tts", tags=["Text-to-Speech"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["LLM"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(monitoring.router, prefix="/v1/monitoring", tags=["Monitoring"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "NEURA API",
        "tagline": "Where AI Comes Alive",
        "version": "0.1.0",
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "env": settings.env}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    
    # Capture exception in Sentry
    capture_exception(
        exc,
        path=request.url.path,
        method=request.method,
    )
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

