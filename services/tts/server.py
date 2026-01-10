"""TTS Service FastAPI Server."""
import asyncio
import io
import os
import tempfile
from pathlib import Path
from typing import Optional

import structlog
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from engine import TTSEngine, TTSResult

logger = structlog.get_logger()

app = FastAPI(
    title="NEURA TTS Service",
    description="Text-to-Speech service using Coqui XTTS",
    version="1.0.0",
)

# Global TTS engine instance
tts_engine: Optional[TTSEngine] = None


class SynthesizeRequest(BaseModel):
    """Request for text synthesis."""
    text: str
    voice_id: Optional[str] = "default"
    language: str = "en"
    speed: float = 1.0
    pitch: float = 1.0


class SynthesizeResponse(BaseModel):
    """Response from synthesis."""
    audio_url: str
    duration: float
    sample_rate: int
    word_timings: list


class VoiceCloneRequest(BaseModel):
    """Request for voice cloning."""
    name: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    device: str


@app.on_event("startup")
async def startup():
    """Initialize TTS engine on startup."""
    global tts_engine
    logger.info("Starting TTS service")
    
    try:
        tts_engine = TTSEngine(
            model_path=os.getenv("TTS_MODEL_PATH", "/app/models"),
            device=os.getenv("TTS_DEVICE", "auto"),
        )
        await tts_engine.initialize()
        logger.info("TTS engine initialized", device=tts_engine.device)
    except Exception as e:
        logger.warning("TTS engine initialization failed, will use fallback", error=str(e))
        # Create engine instance but mark as not initialized
        # This allows service to start and use fallback mechanisms
        tts_engine = TTSEngine(
            model_path=os.getenv("TTS_MODEL_PATH", "/app/models"),
            device=os.getenv("TTS_DEVICE", "auto"),
        )
        tts_engine._initialized = False


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health."""
    if not tts_engine:
        return HealthResponse(
            status="unhealthy",
            model_loaded=False,
            device="unknown",
        )
    
    # Service is healthy even if models aren't loaded (can use fallback)
    is_healthy = hasattr(tts_engine, '_initialized')
    model_loaded = getattr(tts_engine, '_initialized', False)
    device = getattr(tts_engine, 'device', 'unknown')
    
    return HealthResponse(
        status="healthy" if is_healthy else "degraded",
        model_loaded=model_loaded,
        device=device,
    )


@app.post("/synthesize")
async def synthesize(request: SynthesizeRequest):
    """Synthesize speech from text."""
    if not tts_engine:
        raise HTTPException(
            status_code=503,
            detail="TTS engine not available. Service is starting up or models are not loaded."
        )
    
    # Check if engine is initialized, if not, try to initialize
    if not getattr(tts_engine, '_initialized', False):
        try:
            await tts_engine.initialize()
            logger.info("TTS engine initialized on first request")
        except Exception as e:
            logger.warning("Failed to initialize TTS engine, using fallback", error=str(e))
    
    logger.info("Synthesizing speech", text_length=len(request.text))
    
    try:
        # Get voice sample path if using cloned voice
        voice_sample = None
        if request.voice_id and request.voice_id != "default":
            voice_path = Path(f"/app/voices/{request.voice_id}.wav")
            if voice_path.exists():
                voice_sample = str(voice_path)
        
        result = await tts_engine.synthesize(
            text=request.text,
            voice_sample=voice_sample,
            language=request.language,
            speed=request.speed,
            pitch=request.pitch,
        )
        
        # Return audio as streaming response
        return StreamingResponse(
            io.BytesIO(result.audio_data),
            media_type="audio/wav",
            headers={
                "X-Duration": str(result.duration),
                "X-Sample-Rate": str(result.sample_rate),
                "X-Word-Timings": str([
                    {"word": t.word, "start": t.start_time, "end": t.end_time}
                    for t in result.word_timings
                ]),
            },
        )
    except Exception as e:
        logger.error("Synthesis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/synthesize/stream")
async def synthesize_stream(request: SynthesizeRequest):
    """Stream synthesized speech in chunks."""
    if not tts_engine:
        raise HTTPException(status_code=503, detail="TTS engine not initialized")
    
    async def audio_generator():
        voice_sample = None
        if request.voice_id and request.voice_id != "default":
            voice_path = Path(f"/app/voices/{request.voice_id}.wav")
            if voice_path.exists():
                voice_sample = str(voice_path)
        
        async for chunk, timings in tts_engine.synthesize_stream(
            text=request.text,
            voice_sample=voice_sample,
            language=request.language,
        ):
            yield chunk
    
    return StreamingResponse(
        audio_generator(),
        media_type="audio/wav",
    )


@app.post("/voices/clone")
async def clone_voice(
    name: str = Form(...),
    audio: UploadFile = File(...),
):
    """Clone a voice from an audio sample."""
    if not tts_engine:
        raise HTTPException(status_code=503, detail="TTS engine not initialized")
    
    logger.info("Cloning voice", name=name, filename=audio.filename)
    
    try:
        # Read audio data
        audio_data = await audio.read()
        
        # Save voice sample
        voice_path = Path(f"/app/voices/{name}.wav")
        voice_path.write_bytes(audio_data)
        
        # Create voice profile
        result = await tts_engine.clone_voice(audio_data, name)
        
        return {
            "voice_id": name,
            "status": "created",
            **result,
        }
    except Exception as e:
        logger.error("Voice cloning failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voices")
async def list_voices():
    """List available voices."""
    if not tts_engine:
        raise HTTPException(status_code=503, detail="TTS engine not initialized")
    
    voices = tts_engine.get_available_voices()
    
    # Add custom cloned voices
    voices_dir = Path("/app/voices")
    if voices_dir.exists():
        for voice_file in voices_dir.glob("*.wav"):
            voices.append({
                "id": voice_file.stem,
                "name": voice_file.stem.replace("_", " ").title(),
                "language": "en",
                "type": "cloned",
            })
    
    return {"voices": voices}


@app.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    """Delete a cloned voice."""
    voice_path = Path(f"/app/voices/{voice_id}.wav")
    
    if not voice_path.exists():
        raise HTTPException(status_code=404, detail="Voice not found")
    
    voice_path.unlink()
    
    return {"status": "deleted", "voice_id": voice_id}

