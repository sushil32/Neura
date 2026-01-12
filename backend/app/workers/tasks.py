"""Celery tasks for background processing."""
import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
import structlog

from app.config import settings
from app.workers.celery_app import celery_app

logger = structlog.get_logger()

# Service URLs
# Service URLs
TTS_SERVICE_URL = os.getenv("TTS_SERVICE_URL", settings.tts_service_url)
AVATAR_SERVICE_URL = os.getenv("AVATAR_SERVICE_URL", settings.avatar_service_url)



import re

def clean_text_for_tts(text: str) -> str:
    """Clean text before sending to TTS service."""
    if not text:
        return ""
        
    # Remove timestamps/section headers like [0:00 - 0:10 | Hook]
    text = re.sub(r'\[\d{1,2}:\d{2}.*?\]', '', text)
    
    # Remove visual cues like [VISUAL: ...]
    text = re.sub(r'\[vis.*?\]', '', text, flags=re.IGNORECASE)
    
    # Remove standalone headers (e.g. "Title | Topic")
    # Heuristic: line contains "|" and is short
    lines = []
    for line in text.split('\n'):
        if '|' in line and len(line) < 100:
            continue
        lines.append(line)
    text = '\n'.join(lines)
    
    # Replace [PAUSE] or similar tags with breaks
    text = re.sub(r'\[pause.*?\]', '... ', text, flags=re.IGNORECASE)
    
    # Clean extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


# Worker-safe database context that creates fresh engine per task
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

@asynccontextmanager
async def get_worker_db():
    """Create a fresh database session for Celery workers.
    
    This avoids the 'Future attached to different loop' error by creating
    a new engine bound to the current event loop.
    """
    from app.config import settings
    
    # Create fresh engine for this event loop
    engine = create_async_engine(
        settings.db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
    )
    
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    # Dispose engine after use
    await engine.dispose()


def run_async(coro):
    """Helper to run async code in Celery tasks."""
    # Always create a new event loop for Celery tasks
    # This ensures clean async execution in prefork workers
    try:
        # Close any existing loop in this thread
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            loop.close()
    except RuntimeError:
        pass
    
    # Create a fresh event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(coro)
    finally:
        # Clean up
        try:
            # Cancel any remaining tasks
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            if pending:
                for task in pending:
                    task.cancel()
                # Wait for cancellations
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()
            asyncio.set_event_loop(None)


async def call_tts_service(
    text: str,
    voice_id: str = "default",
    language: str = "en",
    speed: float = 1.0,
) -> Dict[str, Any]:
    """Call TTS service to generate audio with retry logic."""
    max_retries = 3
    retry_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Check service health first
                try:
                    health_response = await client.get(f"{TTS_SERVICE_URL}/health", timeout=5.0)
                    if health_response.status_code != 200:
                        logger.warning(
                            "TTS service health check failed",
                            status=health_response.status_code,
                            attempt=attempt + 1,
                        )
                except Exception as e:
                    logger.warning(
                        "TTS service health check error",
                        error=str(e),
                        attempt=attempt + 1,
                    )
                
                response = await client.post(
                    f"{TTS_SERVICE_URL}/synthesize",
                    json={
                        "text": text,
                        "voice_id": voice_id,
                        "language": language,
                        "speed": speed,
                    },
                )
                
                if response.status_code == 200:
                    # Get metadata from headers
                    duration = float(response.headers.get("X-Duration", "0"))
                    sample_rate = int(response.headers.get("X-Sample-Rate", "22050"))
                    word_timings_str = response.headers.get("X-Word-Timings", "[]")
                    
                    # Parse word timings
                    import json
                    try:
                        word_timings = json.loads(word_timings_str.replace("'", '"'))
                    except:
                        word_timings = []
                    
                    return {
                        "audio_data": response.content,
                        "duration": duration,
                        "sample_rate": sample_rate,
                        "word_timings": word_timings,
                    }
                elif response.status_code == 503:
                    # Service unavailable - retry
                    if attempt < max_retries - 1:
                        logger.warning(
                            "TTS service unavailable, retrying",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                        )
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    raise Exception(f"TTS service unavailable after {max_retries} attempts: {response.text}")
                else:
                    raise Exception(f"TTS service error ({response.status_code}): {response.text}")
                    
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                logger.warning(
                    "TTS service timeout, retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            raise Exception(f"TTS service timeout after {max_retries} attempts")
        except httpx.ConnectError as e:
            if attempt < max_retries - 1:
                logger.warning(
                    "TTS service connection error, retrying",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            raise Exception(f"TTS service connection failed after {max_retries} attempts: {str(e)}")
    
    raise Exception("TTS service call failed after all retries")


async def call_avatar_service(
    job_id: str,
    avatar_id: str,
    audio_path: str,
    word_timings: List[Dict],
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    emotion: str = "neutral",
    expression_scale: float = 1.0,
    head_pose_scale: float = 1.0,
    use_sadtalker: bool = True,
) -> Dict[str, Any]:
    """Call Avatar service to render video with retry logic."""
    max_retries = 3
    retry_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                # Check service health first
                try:
                    health_response = await client.get(f"{AVATAR_SERVICE_URL}/health", timeout=5.0)
                    if health_response.status_code != 200:
                        logger.warning(
                            "Avatar service health check failed",
                            status=health_response.status_code,
                            attempt=attempt + 1,
                        )
                except Exception as e:
                    logger.warning(
                        "Avatar service health check error",
                        error=str(e),
                        attempt=attempt + 1,
                    )
                
                response = await client.post(
                    f"{AVATAR_SERVICE_URL}/render",
                    json={
                        "job_id": job_id,
                        "avatar_id": avatar_id,
                        "audio_url": audio_path,
                        "word_timings": word_timings,
                        "width": width,
                        "height": height,
                        "fps": fps,
                        "emotion": emotion,
                        "expression_scale": expression_scale,
                        "head_pose_scale": head_pose_scale,
                        "use_sadtalker": use_sadtalker,
                    },
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 503:
                    # Service unavailable - retry
                    if attempt < max_retries - 1:
                        logger.warning(
                            "Avatar service unavailable, retrying",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                        )
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    raise Exception(f"Avatar service unavailable after {max_retries} attempts: {response.text}")
                else:
                    raise Exception(f"Avatar service error ({response.status_code}): {response.text}")
                    
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                logger.warning(
                    "Avatar service timeout, retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            raise Exception(f"Avatar service timeout after {max_retries} attempts")
        except httpx.ConnectError as e:
            if attempt < max_retries - 1:
                logger.warning(
                    "Avatar service connection error, retrying",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            raise Exception(f"Avatar service connection failed after {max_retries} attempts: {str(e)}")
    
    raise Exception("Avatar service call failed after all retries")


async def wait_for_render(job_id: str, timeout: int = 600) -> Dict[str, Any]:
    """Wait for avatar render to complete."""
    start_time = datetime.utcnow()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout:
                raise Exception("Render timeout exceeded")
            
            response = await client.get(
                f"{AVATAR_SERVICE_URL}/render/{job_id}/status"
            )
            
            if response.status_code != 200:
                raise Exception(f"Status check failed: {response.text}")
            
            status = response.json()
            
            if status["status"] == "completed":
                return status
            elif status["current_step"] == "Failed":
                raise Exception("Render failed")
            
            await asyncio.sleep(2)


@celery_app.task(bind=True, max_retries=3)
def video_generation_task(self, job_id: str) -> Dict[str, Any]:
    """
    Generate a video from script.
    
    Pipeline:
    1. Load script and avatar config
    2. Generate audio via TTS service
    3. Process lip sync with Avatar service
    4. Render avatar video
    5. Upload to storage
    """
    logger.info("Starting video generation", job_id=job_id)
    
    async def process():
        # Import inside function to avoid module-level async issues
        from app.models.job import Job
        from app.models.video import Video
        from app.models.user import User
        from app.utils.storage import storage_client
        from sqlalchemy import select
        
        # Use worker-safe DB that creates fresh engine for this event loop
        async with get_worker_db() as db:
            # Get job
            result = await db.execute(select(Job).where(Job.id == UUID(job_id)))
            job = result.scalar_one_or_none()
            
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            # Update job status
            job.status = "processing"
            job.started_at = datetime.utcnow()
            job.current_step = "Initializing"
            await db.commit()
            
            video = None
            temp_dir = None
            
            try:
                # Get video
                video_id = job.input_data.get("video_id")
                result = await db.execute(select(Video).where(Video.id == UUID(video_id)))
                video = result.scalar_one_or_none()
                
                if not video:
                    raise ValueError(f"Video {video_id} not found")
                
                # Get user for credit deduction
                result = await db.execute(select(User).where(User.id == video.user_id))
                user = result.scalar_one_or_none()
                
                # Check credits
                estimated_credits = job.credits_estimated or 10
                if user and user.credits < estimated_credits:
                    raise ValueError(f"Insufficient credits. Required: {estimated_credits}, Available: {user.credits}")
                
                # Create temp directory in shared volume for communication with avatar service
                # We added a shared volume at /shared in docker-compose
                shared_root = Path("/shared")
                if shared_root.exists():
                    job_temp_dir = shared_root / "temp" / str(job_id)
                    job_temp_dir.mkdir(parents=True, exist_ok=True)
                    audio_path_for_avatar = f"/shared/temp/{job_id}/audio.wav"
                else:
                    # Fallback for local dev (no shared volume)
                    # Use a temp dir that hopefully works or is absolute
                    job_temp_dir = Path(tempfile.gettempdir()) / "neura_tasks" / str(job_id)
                    job_temp_dir.mkdir(parents=True, exist_ok=True)
                    audio_path_for_avatar = str(job_temp_dir / "audio.wav")
                
                audio_path = job_temp_dir / "audio.wav"
                video_path = job_temp_dir / "output.mp4"
                
                logger.info("Using temp dir", path=str(job_temp_dir), audio_path_for_service=audio_path_for_avatar)
                
                # ========================================
                # Step 1: Generate TTS Audio
                # ========================================
                job.current_step = "Generating audio"
                job.progress = 0.1
                await db.commit()
                
                # Get script (allow override for preview)
                script = job.input_data.get("script") or video.script
                is_preview = job.input_data.get("preview", False)
                
                logger.info("Starting video generation", 
                           video_id=video_id, 
                           is_preview=is_preview,
                           script_length=len(script),
                           script_preview=script[:100] if script else None)
                
                if not script or len(script.strip()) == 0:
                    raise ValueError("Script is empty or missing")
                
                # Detect emotion from script (for SadTalker)
                emotion = job.input_data.get("emotion")  # User override
                if not emotion:
                    try:
                        from app.utils.emotion import detect_emotion_from_text
                        emotion = detect_emotion_from_text(script, use_ml=False)
                        logger.info("Auto-detected emotion", emotion=emotion, script_preview=script[:50])
                    except Exception as e:
                        logger.warning("Emotion detection failed, using neutral", error=str(e))
                        emotion = "neutral"
                
                logger.info("Calling TTS service", video_id=video_id, script_length=len(script))
                
                try:
                    cleaned_script = clean_text_for_tts(script)
                    logger.info("Cleaned script for TTS", 
                               original_length=len(script),
                               cleaned_length=len(cleaned_script),
                               cleaned_preview=cleaned_script[:100])
                    
                    tts_result = await call_tts_service(
                        text=cleaned_script,
                        voice_id=job.input_data.get("voice_id", "default"),
                        language="en",
                        speed=1.0,
                    )
                    
                    # Save audio to temp file
                    audio_path.write_bytes(tts_result["audio_data"])
                    word_timings = tts_result["word_timings"]
                    audio_duration = tts_result["duration"]
                    
                    logger.info("TTS completed", duration=audio_duration)
                    
                except Exception as e:
                    logger.warning("TTS service unavailable, using fallback", error=str(e))
                    # Fallback: create a simple silent audio file
                    # Instead of importing services, create minimal audio
                    import wave
                    import struct
                    sample_rate = 22050
                    duration = len(script) / 15  # ~15 chars per second
                    num_samples = int(sample_rate * duration)
                    
                    with wave.open(str(audio_path), 'wb') as wav_file:
                        wav_file.setnchannels(1)  # Mono
                        wav_file.setsampwidth(2)  # 16-bit
                        wav_file.setframerate(sample_rate)
                        # Write silent audio
                        for _ in range(num_samples):
                            wav_file.writeframes(struct.pack('<h', 0))
                    
                    # Create simple word timings
                    words = script.split()
                    word_duration = duration / len(words) if words else duration
                    word_timings = []
                    current_time = 0.0
                    for word in words:
                        word_timings.append({
                            "word": word,
                            "start": current_time,
                            "end": current_time + word_duration
                        })
                        current_time += word_duration
                    
                    audio_duration = duration
                    logger.info("Created fallback silent audio", duration=audio_duration)
                
                job.progress = 0.3
                await db.commit()
                
                # ========================================
                # Step 2: Render Avatar Video
                # ========================================
                job.current_step = "Rendering avatar"
                job.progress = 0.4
                await db.commit()
                
                # Get resolution (from job input_data for previews, or from video record)
                resolution = job.input_data.get("resolution") or video.resolution or "1080p"
                resolution_map = {
                    "720p": (1280, 720),
                    "1080p": (1920, 1080),
                    "4k": (3840, 2160),
                }
                width, height = resolution_map.get(resolution, (1920, 1080))
                
                logger.info("Preparing avatar render", 
                           video_id=video_id,
                           avatar_id=video.avatar_id,
                           resolution=resolution,
                           width=width,
                           height=height,
                           audio_file_exists=audio_path.exists(),
                           audio_file_size=audio_path.stat().st_size if audio_path.exists() else 0)
                
                try:
                    # Start render job
                    render_job_id = f"{job_id}_render"
                    # Convert UUID to string
                    avatar_id_str = str(video.avatar_id) if video.avatar_id else "default"
                    
                    logger.info("Calling Avatar service", 
                               render_job_id=render_job_id,
                               avatar_id=avatar_id_str,
                               audio_path_for_avatar=audio_path_for_avatar,
                               emotion=emotion)
                    
                    await call_avatar_service(
                        job_id=render_job_id,
                        avatar_id=avatar_id_str,
                        audio_path=audio_path_for_avatar,
                        word_timings=word_timings,
                        width=width,
                        height=height,
                        fps=30,
                        emotion=emotion,
                        expression_scale=job.input_data.get("expression_scale", 1.0),
                        head_pose_scale=job.input_data.get("head_pose_scale", 1.0),
                        use_sadtalker=job.input_data.get("use_sadtalker", True),
                    )
                    
                    # Wait for render to complete
                    job.current_step = "Processing frames"
                    job.progress = 0.5
                    await db.commit()
                    
                    render_status = await wait_for_render(render_job_id, timeout=600)
                    
                    # Download rendered video
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"{AVATAR_SERVICE_URL}/render/{render_job_id}/download"
                        )
                        video_path.write_bytes(response.content)
                    
                    logger.info("Avatar render completed")
                    
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"AVATAR SERVICE FAILED: {e}")
                    print(error_detail)
                    logger.error("Avatar service failed", error=str(e))
                    logger.warning("Avatar service unavailable, using fallback", error=str(e))
                    # Fallback: create a simple placeholder video using ffmpeg
                    # Create a black video with the audio
                    import subprocess
                    try:
                        subprocess.run(
                            [
                                "ffmpeg",
                                "-f", "lavfi",
                                "-i", f"color=c=black:s={width}x{height}:d={audio_duration}",
                                "-i", str(audio_path),
                                "-c:v", "libx264",
                                "-c:a", "aac",
                                "-shortest",
                                "-y",
                                str(video_path),
                            ],
                            check=True,
                            capture_output=True,
                            timeout=300,
                        )
                        logger.info("Created fallback placeholder video")
                    except Exception as fallback_error:
                        logger.error("Fallback video creation failed", error=str(fallback_error))
                        # Create empty file as last resort
                        video_path.write_bytes(b"")
                
                job.progress = 0.8
                await db.commit()
                
                # ========================================
                # Step 3: Upload to Storage
                # ========================================
                job.current_step = "Uploading"
                job.progress = 0.9
                await db.commit()
                
                logger.info("Uploading to storage", video_id=video_id)
                
                # Upload to MinIO/S3
                video_key = f"videos/{video.user_id}/{video_id}.mp4"
                video_url = await storage_client.upload_file(
                    file_path=str(video_path),
                    bucket="neura-videos",
                    key=video_key,
                )
                
                # Also upload audio
                audio_key = f"audio/{video.user_id}/{video_id}.wav"
                audio_url = await storage_client.upload_file(
                    file_path=str(audio_path),
                    bucket="neura-videos",
                    key=audio_key,
                )
                
                logger.info("Upload completed", video_url=video_url)
                
                # ========================================
                # Step 4: Deduct Credits
                # ========================================
                # Check if this is a preview
                is_preview = job.input_data.get("preview", False)
                
                if user and not is_preview:
                    credits_used = estimated_credits
                    user.credits -= credits_used
                    logger.info("Credits deducted", user_id=str(user.id), credits_used=credits_used)
                
                # ========================================
                # Step 5: Update Records
                # ========================================
                if is_preview:
                    # For preview, only update preview_url, don't change main video status
                    video.preview_url = video_url
                    logger.info("Preview video generated", preview_url=video_url)
                else:
                    # For full video, update all fields
                    video.status = "completed"
                    video.video_url = video_url
                    video.audio_url = audio_url
                    video.duration = audio_duration
                    video.completed_at = datetime.utcnow()
                    video.video_metadata = {
                    "width": width,
                    "height": height,
                    "fps": 30,
                    "duration": audio_duration,
                    "word_timings": word_timings,
                }
                
                job.status = "completed"
                job.progress = 1.0
                job.current_step = "Complete"
                job.completed_at = datetime.utcnow()
                
                # Set job result with appropriate URL based on preview status
                if is_preview:
                    job.result = {
                        "video_url": video_url,  # Frontend expects this field
                        "preview_url": video_url,
                        "audio_url": audio_url,
                        "duration": audio_duration,
                    }
                else:
                    job.result = {
                        "video_url": video_url,
                        "audio_url": audio_url,
                        "duration": audio_duration,
                    }
                
                job.credits_used = estimated_credits if not is_preview else 0
                
                await db.commit()
                
                logger.info("Video generation completed", job_id=job_id, video_id=video_id, is_preview=is_preview)
                return {"status": "completed", "video_url": video_url}
                
            except Exception as e:
                # Update job with error
                job.status = "failed"
                job.error = str(e)
                job.completed_at = datetime.utcnow()
                
                # Update video
                if video:
                    video.status = "failed"
                    video.error_message = str(e)
                
                await db.commit()
                
                logger.error("Video generation failed", job_id=job_id, error=str(e))
                raise
                
            finally:
                # Cleanup temp directory
                try:
                    if 'job_temp_dir' in locals() and job_temp_dir.exists():
                        import shutil
                        shutil.rmtree(job_temp_dir)
                        logger.info("Cleaned up temp directory", path=str(job_temp_dir))
                except Exception as cleanup_error:
                    logger.warning("Failed to cleanup temp directory", error=str(cleanup_error))
    
    try:
        return run_async(process())
    except Exception as e:
        # Retry on failure
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@celery_app.task(bind=True, max_retries=3)
def tts_generation_task(self, text: str, voice_id: str = None) -> Dict[str, Any]:
    """Generate TTS audio standalone task."""
    logger.info("Starting TTS generation", text_length=len(text))
    
    async def generate():
        try:
            result = await call_tts_service(
                text=text,
                voice_id=voice_id or "default",
            )
            return {
                "status": "completed",
                "duration": result["duration"],
                "word_timings": result["word_timings"],
            }
        except Exception as e:
            # Fallback to local TTS
            from services.tts.engine import TTSEngine
            engine = TTSEngine()
            await engine.initialize()
            result = await engine.synthesize(text)
            return {
                "status": "completed",
                "duration": result.duration,
                "word_timings": [
                    {"word": t.word, "start": t.start_time, "end": t.end_time}
                    for t in result.word_timings
                ],
            }
    
    return run_async(generate())


@celery_app.task
def cleanup_expired_sessions():
    """Clean up expired user sessions."""
    logger.info("Cleaning up expired sessions")
    
    async def cleanup():
        from app.database import get_db_context
        from app.models.user import Session
        from sqlalchemy import delete
        
        async with get_db_context() as db:
            # Delete expired sessions
            result = await db.execute(
                delete(Session).where(Session.expires_at < datetime.utcnow())
            )
            deleted = result.rowcount
            await db.commit()
            
            logger.info("Cleaned up expired sessions", count=deleted)
            return deleted
    
    return run_async(cleanup())


@celery_app.task
def process_pending_jobs():
    """Process any stuck pending jobs."""
    logger.info("Processing pending jobs")
    
    async def process():
        from app.database import get_db_context
        from app.models.job import Job
        from sqlalchemy import select
        
        async with get_db_context() as db:
            # Find stuck jobs (pending for more than 5 minutes)
            cutoff = datetime.utcnow() - timedelta(minutes=5)
            result = await db.execute(
                select(Job).where(
                    Job.status == "pending",
                    Job.created_at < cutoff,
                )
            )
            stuck_jobs = result.scalars().all()
            
            for job in stuck_jobs:
                # Re-queue the job
                if job.type == "video_generation":
                    video_generation_task.delay(str(job.id))
                    job.status = "queued"
            
            await db.commit()
            
            logger.info("Re-queued stuck jobs", count=len(stuck_jobs))
            return len(stuck_jobs)
    
    return run_async(process())


@celery_app.task
def cleanup_old_temp_files():
    """Clean up old temporary files."""
    logger.info("Cleaning up old temp files")
    
    temp_dirs = ["/tmp", "/app/temp"]
    cutoff = datetime.utcnow() - timedelta(hours=24)
    cleaned = 0
    
    for temp_dir in temp_dirs:
        temp_path = Path(temp_dir)
        if not temp_path.exists():
            continue
            
        for item in temp_path.iterdir():
            try:
                if item.stat().st_mtime < cutoff.timestamp():
                    if item.is_dir():
                        import shutil
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    cleaned += 1
            except:
                pass
    
    logger.info("Cleaned up temp files", count=cleaned)
    return cleaned
