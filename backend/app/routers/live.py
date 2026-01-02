"""Live streaming router for real-time avatar sessions."""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.avatar import Avatar
from app.models.job import Job
from app.models.user import User
from app.utils.deps import get_current_active_user, RequireCredits

router = APIRouter()
logger = structlog.get_logger()

# Live session cost
LIVE_CREDITS_PER_MINUTE = 5


class LiveSessionCreate(BaseModel):
    """Live session creation request."""
    avatar_id: Optional[UUID] = None


class LiveSessionResponse(BaseModel):
    """Live session response."""
    session_id: str
    avatar_id: Optional[UUID]
    websocket_url: str
    status: str
    credits_per_minute: int


class LiveMessage(BaseModel):
    """Message for live session."""
    type: str  # "text", "audio", "control"
    content: str
    metadata: Optional[dict] = None


# Active sessions storage (in production, use Redis)
active_sessions: dict = {}


@router.post("/start", response_model=LiveSessionResponse)
async def start_live_session(
    data: LiveSessionCreate,
    user: User = Depends(RequireCredits(LIVE_CREDITS_PER_MINUTE)),
    db: AsyncSession = Depends(get_db),
) -> LiveSessionResponse:
    """Start a new live avatar session."""
    # Validate avatar if provided
    avatar = None
    if data.avatar_id:
        result = await db.execute(
            select(Avatar).where(
                Avatar.id == data.avatar_id,
                (Avatar.user_id == user.id) | (Avatar.is_public == True),
            )
        )
        avatar = result.scalar_one_or_none()
        if not avatar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Avatar not found",
            )
    
    # Create session
    session_id = str(uuid4())
    
    # Create job for tracking
    job = Job(
        user_id=user.id,
        type="live_session",
        status="processing",
        input_data={
            "session_id": session_id,
            "avatar_id": str(data.avatar_id) if data.avatar_id else None,
        },
        started_at=datetime.utcnow(),
    )
    db.add(job)
    await db.flush()
    
    # Store session
    active_sessions[session_id] = {
        "user_id": str(user.id),
        "avatar_id": str(data.avatar_id) if data.avatar_id else None,
        "job_id": str(job.id),
        "started_at": datetime.utcnow(),
        "credits_used": 0,
    }
    
    logger.info(
        "Live session started",
        session_id=session_id,
        user_id=str(user.id),
    )
    
    return LiveSessionResponse(
        session_id=session_id,
        avatar_id=data.avatar_id,
        websocket_url=f"/api/v1/live/ws/{session_id}",
        status="active",
        credits_per_minute=LIVE_CREDITS_PER_MINUTE,
    )


@router.post("/{session_id}/stop")
async def stop_live_session(
    session_id: str,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Stop a live session."""
    session = active_sessions.get(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    if session["user_id"] != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to stop this session",
        )
    
    # Calculate duration and credits
    duration = (datetime.utcnow() - session["started_at"]).total_seconds()
    credits_used = int((duration / 60) * LIVE_CREDITS_PER_MINUTE)
    
    # Update job
    result = await db.execute(
        select(Job).where(Job.id == UUID(session["job_id"]))
    )
    job = result.scalar_one_or_none()
    if job:
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.credits_used = credits_used
        job.result = {
            "duration_seconds": duration,
            "credits_used": credits_used,
        }
    
    # Deduct credits
    user.credits = max(0, user.credits - credits_used)
    
    # Remove session
    del active_sessions[session_id]
    
    logger.info(
        "Live session stopped",
        session_id=session_id,
        duration=duration,
        credits_used=credits_used,
    )
    
    return {
        "session_id": session_id,
        "duration_seconds": duration,
        "credits_used": credits_used,
    }


@router.get("/{session_id}/status")
async def get_session_status(
    session_id: str,
    user: User = Depends(get_current_active_user),
) -> dict:
    """Get live session status."""
    session = active_sessions.get(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    if session["user_id"] != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this session",
        )
    
    duration = (datetime.utcnow() - session["started_at"]).total_seconds()
    
    return {
        "session_id": session_id,
        "status": "active",
        "duration_seconds": duration,
        "credits_used": int((duration / 60) * LIVE_CREDITS_PER_MINUTE),
    }


@router.websocket("/ws/{session_id}")
async def live_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """WebSocket endpoint for live avatar streaming."""
    session = active_sessions.get(session_id)
    
    if not session:
        await websocket.close(code=4004)
        return
    
    await websocket.accept()
    logger.info("WebSocket connected", session_id=session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message = LiveMessage(**data)
            
            if message.type == "text":
                # Process text input through LLM -> TTS -> Avatar pipeline
                # This is a placeholder - actual implementation would integrate services
                response = {
                    "type": "avatar_frame",
                    "status": "processing",
                    "message": f"Processing: {message.content}",
                }
                await websocket.send_json(response)
                
            elif message.type == "audio":
                # Process audio input (speech-to-text -> LLM -> TTS -> Avatar)
                response = {
                    "type": "avatar_frame",
                    "status": "processing",
                    "message": "Processing audio input",
                }
                await websocket.send_json(response)
                
            elif message.type == "control":
                # Handle control messages (pause, resume, etc.)
                response = {
                    "type": "control_ack",
                    "status": "ok",
                    "command": message.content,
                }
                await websocket.send_json(response)
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", session_id=session_id)
    except Exception as e:
        logger.error("WebSocket error", session_id=session_id, error=str(e))
        await websocket.close(code=1011)

