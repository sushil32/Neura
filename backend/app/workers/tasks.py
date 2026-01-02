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
TTS_SERVICE_URL = os.getenv("TTS_SERVICE_URL", "http://tts-service:8001")
AVATAR_SERVICE_URL = os.getenv("AVATAR_SERVICE_URL", "http://avatar-service:8002")


def run_async(coro):
    """Helper to run async code in Celery tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def call_tts_service(
    text: str,
    voice_id: str = "default",
    language: str = "en",
    speed: float = 1.0,
) -> Dict[str, Any]:
    """Call TTS service to generate audio."""
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{TTS_SERVICE_URL}/synthesize",
            json={
                "text": text,
                "voice_id": voice_id,
                "language": language,
                "speed": speed,
            },
        )
        
        if response.status_code != 200:
            raise Exception(f"TTS service error: {response.text}")
        
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


async def call_avatar_service(
    job_id: str,
    avatar_id: str,
    audio_path: str,
    word_timings: List[Dict],
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> Dict[str, Any]:
    """Call Avatar service to render video."""
    async with httpx.AsyncClient(timeout=600.0) as client:
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
            },
        )
        
        if response.status_code != 200:
            raise Exception(f"Avatar service error: {response.text}")
        
        return response.json()


async def wait_for_render(job_id: str, timeout: int = 600) -> Dict[str, Any]:
    """Wait for avatar render to complete."""
    start_time = datetime.utcnow()
    
    async with httpx.AsyncClient() as client:
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
        from app.database import get_db_context
        from app.models.job import Job
        from app.models.video import Video
        from app.models.user import User
        from app.utils.storage import storage_client
        from sqlalchemy import select
        
        async with get_db_context() as db:
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
                
                # Create temp directory
                temp_dir = tempfile.mkdtemp()
                audio_path = Path(temp_dir) / "audio.wav"
                video_path = Path(temp_dir) / "output.mp4"
                
                # ========================================
                # Step 1: Generate TTS Audio
                # ========================================
                job.current_step = "Generating audio"
                job.progress = 0.1
                await db.commit()
                
                logger.info("Calling TTS service", video_id=video_id)
                
                try:
                    tts_result = await call_tts_service(
                        text=video.script,
                        voice_id=video.voice_id or "default",
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
                    # Fallback: generate silent audio
                    from services.tts.engine import TTSEngine
                    engine = TTSEngine()
                    await engine.initialize()
                    result = await engine.synthesize(video.script)
                    audio_path.write_bytes(result.audio_data)
                    word_timings = [
                        {"word": t.word, "start": t.start_time, "end": t.end_time}
                        for t in result.word_timings
                    ]
                    audio_duration = result.duration
                
                job.progress = 0.3
                await db.commit()
                
                # ========================================
                # Step 2: Render Avatar Video
                # ========================================
                job.current_step = "Rendering avatar"
                job.progress = 0.4
                await db.commit()
                
                logger.info("Calling Avatar service", video_id=video_id)
                
                # Get resolution
                resolution_map = {
                    "720p": (1280, 720),
                    "1080p": (1920, 1080),
                    "4k": (3840, 2160),
                }
                width, height = resolution_map.get(video.resolution, (1920, 1080))
                
                try:
                    # Start render job
                    render_job_id = f"{job_id}_render"
                    await call_avatar_service(
                        job_id=render_job_id,
                        avatar_id=video.avatar_id or "default",
                        audio_path=str(audio_path),
                        word_timings=word_timings,
                        width=width,
                        height=height,
                        fps=30,
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
                    logger.warning("Avatar service unavailable, using fallback", error=str(e))
                    # Fallback: generate placeholder video
                    from services.avatar.renderer import AvatarRenderer, RenderConfig
                    renderer = AvatarRenderer()
                    await renderer.initialize()
                    
                    config = RenderConfig(width=width, height=height)
                    await renderer.render_video(
                        avatar_config={"avatar_id": video.avatar_id or "default"},
                        audio_path=str(audio_path),
                        word_timings=word_timings,
                        output_path=str(video_path),
                        config=config,
                    )
                
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
                if user:
                    credits_used = estimated_credits
                    user.credits -= credits_used
                    logger.info("Credits deducted", user_id=str(user.id), credits_used=credits_used)
                
                # ========================================
                # Step 5: Update Records
                # ========================================
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
                job.result = {
                    "video_url": video_url,
                    "audio_url": audio_url,
                    "duration": audio_duration,
                }
                job.credits_used = estimated_credits
                
                await db.commit()
                
                logger.info("Video generation completed", job_id=job_id, video_id=video_id)
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
                # Cleanup temp files
                if temp_dir:
                    import shutil
                    try:
                        shutil.rmtree(temp_dir)
                    except:
                        pass
    
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
