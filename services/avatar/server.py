"""Avatar Service FastAPI Server."""
import asyncio
import io
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import structlog
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from renderer import AvatarRenderer, RenderConfig, RenderProgress

logger = structlog.get_logger()

app = FastAPI(
    title="NEURA Avatar Service",
    description="Avatar rendering service using Wav2Lip",
    version="1.0.0",
)

# Global renderer instance
avatar_renderer: Optional[AvatarRenderer] = None

# Store render progress
render_progress: Dict[str, RenderProgress] = {}


class RenderRequest(BaseModel):
    """Request for video rendering."""
    job_id: str
    avatar_id: str
    audio_url: str
    word_timings: List[Dict]
    width: int = 1920
    height: int = 1080
    fps: int = 30
    quality: str = "balanced"
    background_color: str = "#000000"


class RenderResponse(BaseModel):
    """Response from render request."""
    job_id: str
    status: str
    video_url: Optional[str] = None


class AvatarUploadResponse(BaseModel):
    """Response from avatar upload."""
    avatar_id: str
    status: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    device: str


@app.on_event("startup")
async def startup():
    """Initialize avatar renderer on startup."""
    global avatar_renderer
    logger.info("Starting Avatar service")
    
    avatar_renderer = AvatarRenderer(
        model_path=os.getenv("AVATAR_MODEL_PATH", "/app/models"),
        device=os.getenv("AVATAR_DEVICE", "auto"),
    )
    await avatar_renderer.initialize()
    logger.info("Avatar renderer initialized")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health."""
    return HealthResponse(
        status="healthy" if avatar_renderer and avatar_renderer._initialized else "unhealthy",
        model_loaded=avatar_renderer._initialized if avatar_renderer else False,
        device=avatar_renderer.device if avatar_renderer else "unknown",
    )


@app.post("/render", response_model=RenderResponse)
async def render_video(request: RenderRequest):
    """Start video rendering job."""
    if not avatar_renderer:
        raise HTTPException(status_code=503, detail="Avatar renderer not initialized")
    
    logger.info("Starting render job", job_id=request.job_id)
    
    # Check avatar exists
    avatar_path = Path(f"/app/avatars/{request.avatar_id}.png")
    if not avatar_path.exists():
        # Try jpg
        avatar_path = Path(f"/app/avatars/{request.avatar_id}.jpg")
        if not avatar_path.exists():
            raise HTTPException(status_code=404, detail="Avatar not found")
    
    # Download audio file
    # In production, this would download from the audio_url
    audio_path = Path(f"/app/temp/{request.job_id}_audio.wav")
    
    # Create output path
    output_path = Path(f"/app/temp/{request.job_id}_output.mp4")
    
    # Create render config
    config = RenderConfig(
        width=request.width,
        height=request.height,
        fps=request.fps,
        quality=request.quality,
        background_color=request.background_color,
    )
    
    # Progress callback
    async def progress_callback(progress: RenderProgress):
        render_progress[request.job_id] = progress
    
    try:
        # Start rendering in background
        asyncio.create_task(
            _render_video_task(
                request.job_id,
                {
                    "avatar_path": str(avatar_path),
                    "avatar_id": request.avatar_id,
                },
                str(audio_path),
                request.word_timings,
                str(output_path),
                config,
                progress_callback,
            )
        )
        
        return RenderResponse(
            job_id=request.job_id,
            status="processing",
        )
    except Exception as e:
        logger.error("Render failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def _render_video_task(
    job_id: str,
    avatar_config: Dict,
    audio_path: str,
    word_timings: List[Dict],
    output_path: str,
    config: RenderConfig,
    progress_callback,
):
    """Background task for video rendering."""
    try:
        result = await avatar_renderer.render_video(
            avatar_config=avatar_config,
            audio_path=audio_path,
            word_timings=word_timings,
            output_path=output_path,
            config=config,
            progress_callback=progress_callback,
        )
        logger.info("Render completed", job_id=job_id, output=result)
    except Exception as e:
        logger.error("Render task failed", job_id=job_id, error=str(e))
        render_progress[job_id] = RenderProgress(
            current_frame=0,
            total_frames=0,
            current_step="Failed",
            progress=0,
            estimated_remaining=0,
        )


@app.get("/render/{job_id}/status")
async def get_render_status(job_id: str):
    """Get render job status."""
    progress = render_progress.get(job_id)
    
    if not progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job_id,
        "current_frame": progress.current_frame,
        "total_frames": progress.total_frames,
        "current_step": progress.current_step,
        "progress": progress.progress,
        "estimated_remaining": progress.estimated_remaining,
        "status": "completed" if progress.progress >= 1.0 else "processing",
    }


@app.get("/render/{job_id}/download")
async def download_render(job_id: str):
    """Download completed render."""
    output_path = Path(f"/app/temp/{job_id}_output.mp4")
    
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    
    return FileResponse(
        path=str(output_path),
        media_type="video/mp4",
        filename=f"{job_id}.mp4",
    )


@app.post("/avatars/upload", response_model=AvatarUploadResponse)
async def upload_avatar(
    avatar_id: str = Form(...),
    image: UploadFile = File(...),
):
    """Upload an avatar image."""
    logger.info("Uploading avatar", avatar_id=avatar_id, filename=image.filename)
    
    # Determine file extension
    ext = Path(image.filename).suffix.lower() if image.filename else ".png"
    if ext not in [".png", ".jpg", ".jpeg"]:
        ext = ".png"
    
    try:
        # Read and save image
        image_data = await image.read()
        avatar_path = Path(f"/app/avatars/{avatar_id}{ext}")
        avatar_path.write_bytes(image_data)
        
        return AvatarUploadResponse(
            avatar_id=avatar_id,
            status="uploaded",
        )
    except Exception as e:
        logger.error("Avatar upload failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/avatars")
async def list_avatars():
    """List available avatars."""
    avatars_dir = Path("/app/avatars")
    avatars = []
    
    if avatars_dir.exists():
        for avatar_file in avatars_dir.glob("*.*"):
            if avatar_file.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                avatars.append({
                    "id": avatar_file.stem,
                    "filename": avatar_file.name,
                    "type": "custom",
                })
    
    # Add default avatars
    default_avatars = [
        {"id": "professional_male", "name": "Professional Male", "type": "default"},
        {"id": "professional_female", "name": "Professional Female", "type": "default"},
        {"id": "casual_male", "name": "Casual Male", "type": "default"},
        {"id": "casual_female", "name": "Casual Female", "type": "default"},
    ]
    
    return {"avatars": default_avatars + avatars}


@app.delete("/avatars/{avatar_id}")
async def delete_avatar(avatar_id: str):
    """Delete an avatar."""
    # Try different extensions
    for ext in [".png", ".jpg", ".jpeg"]:
        avatar_path = Path(f"/app/avatars/{avatar_id}{ext}")
        if avatar_path.exists():
            avatar_path.unlink()
            return {"status": "deleted", "avatar_id": avatar_id}
    
    raise HTTPException(status_code=404, detail="Avatar not found")

