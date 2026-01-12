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

# Configuration
AVATAR_PATH = os.getenv("AVATAR_PATH", "/app/avatars")
print(f"DEBUG: Startup AVATAR_PATH={AVATAR_PATH}")
# Create avatar directory
Path(AVATAR_PATH).mkdir(parents=True, exist_ok=True)

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
    
    # SadTalker emotion parameters
    emotion: Optional[str] = "neutral"
    expression_scale: float = 1.0
    head_pose_scale: float = 1.0
    use_sadtalker: bool = True  # False = fallback to Wav2Lip


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
    
    # Determine model path
    model_path = os.getenv("AVATAR_MODEL_PATH")
    if not model_path:
        # Check local models dir
        local_models = Path(__file__).parent / "models"
        if local_models.exists():
            model_path = str(local_models)
            logger.info(f"Detected local model path: {model_path}")
        else:
            model_path = "/app/models"
            
    try:
        avatar_renderer = AvatarRenderer(
            model_path=model_path,
            device=os.getenv("AVATAR_DEVICE", "auto"),
        )
        await avatar_renderer.initialize()
        logger.info("Avatar renderer initialized", device=avatar_renderer.device)
    except Exception as e:
        logger.warning("Avatar renderer initialization failed, will use fallback", error=str(e))
        # Create renderer instance but mark as not initialized
        # This allows service to start and use fallback mechanisms
        avatar_renderer = AvatarRenderer(
            model_path=model_path,
            device=os.getenv("AVATAR_DEVICE", "auto"),
        )
        avatar_renderer._initialized = False

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health."""
    if not avatar_renderer:
        return HealthResponse(
            status="unhealthy",
            model_loaded=False,
            device="unknown",
        )
    
    # Service is healthy even if models aren't loaded (can use fallback)
    is_healthy = hasattr(avatar_renderer, '_initialized')
    model_loaded = getattr(avatar_renderer, '_initialized', False)
    device = getattr(avatar_renderer, 'device', 'unknown')
    
    return HealthResponse(
        status="healthy" if is_healthy else "degraded",
        model_loaded=model_loaded,
        device=device,
    )


@app.post("/render", response_model=RenderResponse)
async def render_video(request: RenderRequest):
    """Start video rendering job."""
    if not avatar_renderer:
        raise HTTPException(
            status_code=503,
            detail="Avatar renderer not available. Service is starting up or models are not loaded."
        )
    
    # Check if renderer is initialized, if not, try to initialize
    if not getattr(avatar_renderer, '_initialized', False):
        try:
            await avatar_renderer.initialize()
            logger.info("Avatar renderer initialized on first request")
        except Exception as e:
            logger.warning("Failed to initialize Avatar renderer, using fallback", error=str(e))
    
    logger.info("Starting render job", job_id=request.job_id)
    
    # Check avatar exists
    # Check avatar exists
    # Support both docker path and local path
    avatar_paths = [
        Path(f"/app/avatars/{request.avatar_id}.png"),
        Path(f"/app/avatars/{request.avatar_id}.jpg"),
        Path(f"avatars/{request.avatar_id}.png"),
        Path(f"avatars/{request.avatar_id}.jpg"),
        Path(f"services/avatar/avatars/{request.avatar_id}.png"),
        Path(f"services/avatar/avatars/{request.avatar_id}.jpg"),
    ]
    
    avatar_path = None
    for path in avatar_paths:
        if path.exists():
            avatar_path = path
            break
            
    if not avatar_path:
        # Fallback to absolute path search if simple relative failed
        # This handles running from root or other dirs
        root_dir = Path(__file__).parent.parent.parent
        avatar_paths_abs = [
            root_dir / f"services/avatar/avatars/{request.avatar_id}.png",
            root_dir / f"services/avatar/avatars/{request.avatar_id}.jpg"
        ]
        for path in avatar_paths_abs:
            if path.exists():
                avatar_path = path
                break

    if not avatar_path:
        debug_info = {
            "cwd": os.getcwd(),
            "checked_paths": [str(p.absolute()) for p in avatar_paths],
            "abs_checked": [str(p) for p in avatar_paths_abs]
        }
        logger.error("Avatar lookup failed", **debug_info)
        raise HTTPException(status_code=404, detail=f"Avatar not found: {request.avatar_id}. Debug: {debug_info}")
    
    # Setup temp directory
    try:
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        print(f"DEBUG: Temp dir created at {temp_dir.absolute()}")

        # Download/Copy audio file
        audio_source = request.audio_url
        audio_path = temp_dir / f"{request.job_id}_audio.wav"
        
        import shutil
        
        if audio_source.startswith("http"):
             # Download from URL using urllib (standard lib)
             import urllib.request
             print(f"DEBUG: Downloading audio from {audio_source}")
             urllib.request.urlretrieve(audio_source, str(audio_path))
        else:
            # Assume local path
            source_path = Path(audio_source)
            
            # Map /shared paths if running locally
            shared_path_env = os.getenv("SHARED_PATH")
            if shared_path_env and str(source_path).startswith("/shared"):
                # Replace prefix /shared with actual local path
                rel_path = str(source_path)[len("/shared"):]
                if rel_path.startswith("/"): rel_path = rel_path[1:]
                source_path = Path(shared_path_env) / rel_path
                print(f"DEBUG: Mapped path {audio_source} to {source_path}")
            
            print(f"DEBUG: Copying audio from {source_path}")
            if not source_path.exists():
                raise HTTPException(status_code=400, detail=f"Audio file not found at {source_path}")
            shutil.copy(source_path, audio_path)
        
        # Create output path
        output_path = temp_dir / f"{request.job_id}_output.mp4"
        
        # Create render config
        config = RenderConfig(
            width=request.width,
            height=request.height,
            fps=request.fps,
            quality=request.quality,
            background_color=request.background_color,
            # SadTalker config
            emotion=request.emotion,
            expression_scale=request.expression_scale,
            head_pose_scale=request.head_pose_scale,
            use_sadtalker=request.use_sadtalker,
        )
    except Exception as e:
        print(f"CRITICAL ERROR in render_video setup: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")
    
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
            error=str(e)
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
        "status": "failed" if progress.error or progress.current_step == "Failed" else ("completed" if progress.progress >= 1.0 else "processing"),
        "error": progress.error
    }


@app.get("/render/{job_id}/download")
async def download_render(job_id: str):
    """Download completed render."""
    output_path = Path(f"temp/{job_id}_output.mp4")
    
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
        avatar_path = Path(AVATAR_PATH) / f"{avatar_id}{ext}"
        print(f"DEBUG: Saving avatar to {avatar_path}")
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
    avatars_dir = Path(AVATAR_PATH)
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
        avatar_path = Path(AVATAR_PATH) / f"{avatar_id}{ext}"
        if avatar_path.exists():
            avatar_path.unlink()
            return {"status": "deleted", "avatar_id": avatar_id}
    
    raise HTTPException(status_code=404, detail="Avatar not found")

