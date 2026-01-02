"""WebRTC stream management for live avatar with real-time TTS and avatar generation."""
import asyncio
import base64
import io
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

import numpy as np
import structlog

logger = structlog.get_logger()

# Import services
try:
    from services.tts.engine import TTSEngine
    from services.avatar.renderer import AvatarRenderer, RenderConfig
    from services.avatar.lipsync import LipSyncProcessor
    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False
    logger.warning("Avatar services not available for streaming")


@dataclass
class StreamConfig:
    """Configuration for video stream."""
    width: int = 1280
    height: int = 720
    fps: int = 30
    video_bitrate: int = 2_000_000  # 2 Mbps
    audio_bitrate: int = 128_000  # 128 kbps
    codec: str = "VP8"
    latency_target_ms: int = 500  # Target <500ms latency


@dataclass
class StreamSession:
    """Active streaming session."""
    session_id: str
    user_id: str
    config: StreamConfig
    avatar_id: str = "default"
    voice_id: str = "default"
    started_at: datetime = field(default_factory=datetime.utcnow)
    frames_sent: int = 0
    bytes_sent: int = 0
    audio_bytes_sent: int = 0
    messages_processed: int = 0
    is_active: bool = True
    is_speaking: bool = False
    current_viseme: str = "sil"
    current_intensity: float = 0.0


@dataclass 
class LiveResponse:
    """Response from live avatar processing."""
    text: str
    audio_data: Optional[bytes] = None
    audio_duration: float = 0.0
    word_timings: List[Dict] = field(default_factory=list)
    lip_sync_frames: List[Dict] = field(default_factory=list)


class LiveAvatarPipeline:
    """
    Real-time pipeline: Text → LLM → TTS → Lip Sync → Avatar → Stream
    
    Optimized for <500ms latency with:
    - Streaming TTS
    - Pre-computed avatar frames
    - Pipelined processing
    """
    
    def __init__(self):
        self._tts_engine: Optional[TTSEngine] = None
        self._avatar_renderer: Optional[AvatarRenderer] = None
        self._lipsync_processor: Optional[LipSyncProcessor] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all pipeline components."""
        if self._initialized:
            return
        
        logger.info("Initializing live avatar pipeline")
        
        if SERVICES_AVAILABLE:
            # Initialize TTS
            self._tts_engine = TTSEngine()
            await self._tts_engine.initialize()
            
            # Initialize Avatar Renderer
            self._avatar_renderer = AvatarRenderer()
            await self._avatar_renderer.initialize()
            
            # Initialize Lip Sync
            self._lipsync_processor = LipSyncProcessor()
            await self._lipsync_processor.initialize()
        
        self._initialized = True
        logger.info("Live avatar pipeline initialized")
    
    async def process_text(
        self,
        text: str,
        voice_id: str = "default",
        avatar_id: str = "default",
        language: str = "en",
    ) -> LiveResponse:
        """
        Process text through the full pipeline.
        
        Returns audio and lip sync data for streaming.
        """
        if not self._initialized:
            await self.initialize()
        
        logger.info("Processing text for live avatar", text_length=len(text))
        
        if not self._tts_engine:
            return LiveResponse(text=text)
        
        try:
            # Generate TTS audio with word timings
            tts_result = await self._tts_engine.synthesize(
                text=text,
                voice_sample=None if voice_id == "default" else f"/app/voices/{voice_id}.wav",
                language=language,
            )
            
            # Generate lip sync frames
            word_timings = [
                {"word": t.word, "start": t.start_time, "end": t.end_time}
                for t in tts_result.word_timings
            ]
            
            lip_sync_frames = await self._lipsync_processor.process_audio(
                audio_data=np.frombuffer(tts_result.audio_data[44:], dtype=np.int16).astype(np.float32) / 32768.0,
                sample_rate=tts_result.sample_rate,
                word_timings=word_timings,
                fps=30,
            )
            
            return LiveResponse(
                text=text,
                audio_data=tts_result.audio_data,
                audio_duration=tts_result.duration,
                word_timings=word_timings,
                lip_sync_frames=lip_sync_frames,
            )
            
        except Exception as e:
            logger.error("Pipeline processing failed", error=str(e))
            return LiveResponse(text=text)
    
    async def stream_response(
        self,
        text: str,
        voice_id: str = "default",
        avatar_id: str = "default",
        fps: int = 30,
    ) -> AsyncGenerator[Tuple[bytes, Dict], None]:
        """
        Stream avatar frames with audio.
        
        Yields tuples of (frame_data, metadata).
        """
        response = await self.process_text(text, voice_id, avatar_id)
        
        if not response.audio_data or not self._avatar_renderer:
            return
        
        frame_interval = 1.0 / fps
        total_frames = int(response.audio_duration * fps)
        
        # Pre-load avatar image
        avatar_config = {"avatar_id": avatar_id}
        config = RenderConfig(width=1280, height=720, fps=fps)
        
        for frame_idx in range(total_frames):
            timestamp = frame_idx / fps
            
            # Get lip sync params for this frame
            lip_params = self._get_lip_params_at_frame(
                response.lip_sync_frames, frame_idx
            )
            
            # Render frame
            # In production, this would use pre-rendered frames or GPU acceleration
            frame_data = await self._render_frame_fast(avatar_config, lip_params, config)
            
            yield frame_data, {
                "frame": frame_idx,
                "timestamp": timestamp,
                "lip_params": lip_params,
            }
            
            await asyncio.sleep(frame_interval)
    
    def _get_lip_params_at_frame(
        self,
        lip_sync_frames: List[Dict],
        frame_idx: int,
    ) -> Dict:
        """Get lip sync parameters for a specific frame."""
        if not lip_sync_frames or frame_idx >= len(lip_sync_frames):
            return {"mouth_open": 0.1, "viseme": "sil"}
        return lip_sync_frames[frame_idx]
    
    async def _render_frame_fast(
        self,
        avatar_config: Dict,
        lip_params: Dict,
        config: RenderConfig,
    ) -> bytes:
        """Fast frame rendering for real-time streaming."""
        if self._avatar_renderer:
            return await self._avatar_renderer._render_frame(
                avatar_config.get("avatar_image"),
                np.zeros(100),  # No audio needed for frame rendering
                lip_params,
                config,
            )
        
        # Fallback: generate simple frame
        return await self._generate_simple_frame(lip_params, config)
    
    async def _generate_simple_frame(
        self,
        lip_params: Dict,
        config: RenderConfig,
    ) -> bytes:
        """Generate a simple animated frame without ML models."""
        try:
            from PIL import Image, ImageDraw
            
            # Create frame
            img = Image.new("RGB", (config.width, config.height), "#1a1a2e")
            draw = ImageDraw.Draw(img)
            
            # Draw avatar circle
            cx, cy = config.width // 2, config.height // 2
            radius = min(config.width, config.height) // 3
            
            # Face
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill="#e8c39e",
                outline="#c9a87e",
            )
            
            # Eyes
            eye_y = cy - radius // 3
            eye_radius = radius // 8
            for ex in [cx - radius // 2, cx + radius // 2]:
                draw.ellipse(
                    [ex - eye_radius, eye_y - eye_radius,
                     ex + eye_radius, eye_y + eye_radius],
                    fill="white",
                )
                draw.ellipse(
                    [ex - eye_radius // 2, eye_y - eye_radius // 2,
                     ex + eye_radius // 2, eye_y + eye_radius // 2],
                    fill="#3a2a1a",
                )
            
            # Animated mouth
            mouth_y = cy + radius // 2
            mouth_open = lip_params.get("mouth_open", 0.1)
            mouth_width = int(radius // 2 * lip_params.get("mouth_wide", 0.8))
            mouth_height = int(radius // 4 * max(mouth_open, 0.1))
            
            draw.ellipse(
                [cx - mouth_width, mouth_y - mouth_height,
                 cx + mouth_width, mouth_y + mouth_height],
                fill="#8b4557",
            )
            
            # Convert to bytes
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=False)
            return buffer.getvalue()
            
        except Exception as e:
            logger.warning(f"Frame generation failed: {e}")
            return b""


class StreamManager:
    """
    Manages WebRTC video/audio streams for live avatars.
    
    Features:
    - Real-time frame encoding
    - Adaptive bitrate
    - Audio/video synchronization
    - Frame rate control
    - <500ms latency target
    """

    def __init__(self):
        self.sessions: Dict[str, StreamSession] = {}
        self._frame_generators: Dict[str, asyncio.Task] = {}
        self._pipeline = LiveAvatarPipeline()
        self._frame_callback: Optional[Callable] = None
        self._audio_callback: Optional[Callable] = None

    async def initialize(self) -> None:
        """Initialize stream manager and pipeline."""
        await self._pipeline.initialize()

    def set_frame_callback(self, callback: Callable) -> None:
        """Set callback for sending frames to clients."""
        self._frame_callback = callback

    def set_audio_callback(self, callback: Callable) -> None:
        """Set callback for sending audio to clients."""
        self._audio_callback = callback

    async def start_stream(
        self,
        session_id: str,
        user_id: str,
        avatar_id: str = "default",
        voice_id: str = "default",
        config: Optional[StreamConfig] = None,
    ) -> StreamSession:
        """Start a new stream session."""
        config = config or StreamConfig()
        
        session = StreamSession(
            session_id=session_id,
            user_id=user_id,
            config=config,
            avatar_id=avatar_id,
            voice_id=voice_id,
        )
        self.sessions[session_id] = session
        
        logger.info(
            "Stream started",
            session_id=session_id,
            resolution=f"{config.width}x{config.height}",
            fps=config.fps,
            avatar_id=avatar_id,
        )
        
        return session

    async def stop_stream(self, session_id: str) -> Optional[Dict]:
        """Stop a stream session and return stats."""
        session = self.sessions.pop(session_id, None)
        
        if session:
            session.is_active = False
            
            # Cancel frame generator if running
            task = self._frame_generators.pop(session_id, None)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            duration = (datetime.utcnow() - session.started_at).total_seconds()
            
            stats = {
                "session_id": session_id,
                "duration": duration,
                "frames_sent": session.frames_sent,
                "bytes_sent": session.bytes_sent,
                "audio_bytes_sent": session.audio_bytes_sent,
                "messages_processed": session.messages_processed,
                "avg_fps": session.frames_sent / duration if duration > 0 else 0,
                "avg_bitrate": session.bytes_sent * 8 / duration if duration > 0 else 0,
            }
            
            logger.info("Stream stopped", **stats)
            return stats
        
        return None

    async def process_message(
        self,
        session_id: str,
        text: str,
    ) -> Optional[LiveResponse]:
        """
        Process a user message and generate avatar response.
        
        This is the main entry point for live interaction.
        """
        session = self.sessions.get(session_id)
        if not session or not session.is_active:
            return None
        
        session.messages_processed += 1
        session.is_speaking = True
        
        try:
            # Process through pipeline
            response = await self._pipeline.process_text(
                text=text,
                voice_id=session.voice_id,
                avatar_id=session.avatar_id,
            )
            
            # Stream frames if callback is set
            if self._frame_callback and response.lip_sync_frames:
                asyncio.create_task(
                    self._stream_response(session, response)
                )
            
            return response
            
        except Exception as e:
            logger.error("Message processing failed", session_id=session_id, error=str(e))
            return None
        finally:
            session.is_speaking = False

    async def _stream_response(
        self,
        session: StreamSession,
        response: LiveResponse,
    ) -> None:
        """Stream avatar frames for a response."""
        if not response.lip_sync_frames:
            return
        
        frame_interval = 1.0 / session.config.fps
        
        # Send audio first (or in parallel)
        if self._audio_callback and response.audio_data:
            await self._audio_callback(
                session.session_id,
                response.audio_data,
            )
            session.audio_bytes_sent += len(response.audio_data)
        
        # Stream frames synchronized with audio
        for frame_idx, lip_params in enumerate(response.lip_sync_frames):
            if not session.is_active:
                break
            
            start_time = asyncio.get_event_loop().time()
            
            # Update session state
            session.current_viseme = lip_params.get("viseme", "sil")
            session.current_intensity = lip_params.get("intensity", 0.0)
            
            # Render and send frame
            frame_data = await self._pipeline._generate_simple_frame(
                lip_params,
                RenderConfig(
                    width=session.config.width,
                    height=session.config.height,
                ),
            )
            
            if self._frame_callback and frame_data:
                await self._frame_callback(
                    session.session_id,
                    frame_data,
                    lip_params.get("timestamp", frame_idx / session.config.fps),
                )
                session.frames_sent += 1
                session.bytes_sent += len(frame_data)
            
            # Frame rate control
            elapsed = asyncio.get_event_loop().time() - start_time
            sleep_time = max(0, frame_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    async def push_audio(
        self,
        session_id: str,
        audio_data: bytes,
    ) -> bool:
        """Push audio data to stream."""
        session = self.sessions.get(session_id)
        if not session or not session.is_active:
            return False
        
        if self._audio_callback:
            await self._audio_callback(session_id, audio_data)
        
        session.audio_bytes_sent += len(audio_data)
        return True

    async def update_lip_sync(
        self,
        session_id: str,
        viseme: str,
        intensity: float,
    ) -> None:
        """Update lip sync state for the stream."""
        session = self.sessions.get(session_id)
        if session:
            session.current_viseme = viseme
            session.current_intensity = intensity

    def get_stats(self, session_id: str) -> Optional[Dict]:
        """Get stream statistics."""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        duration = (datetime.utcnow() - session.started_at).total_seconds()
        
        return {
            "session_id": session_id,
            "is_active": session.is_active,
            "is_speaking": session.is_speaking,
            "duration": duration,
            "frames_sent": session.frames_sent,
            "bytes_sent": session.bytes_sent,
            "audio_bytes_sent": session.audio_bytes_sent,
            "messages_processed": session.messages_processed,
            "current_fps": session.frames_sent / duration if duration > 0 else 0,
            "current_bitrate": session.bytes_sent * 8 / duration if duration > 0 else 0,
            "resolution": f"{session.config.width}x{session.config.height}",
            "target_fps": session.config.fps,
            "avatar_id": session.avatar_id,
            "voice_id": session.voice_id,
        }

    async def adjust_quality(
        self,
        session_id: str,
        bandwidth: int,
    ) -> None:
        """Adjust stream quality based on available bandwidth."""
        session = self.sessions.get(session_id)
        if not session:
            return
        
        # Quality presets based on bandwidth
        if bandwidth < 500_000:  # < 500 kbps
            session.config.width = 640
            session.config.height = 360
            session.config.fps = 15
            session.config.video_bitrate = 300_000
        elif bandwidth < 1_000_000:  # < 1 Mbps
            session.config.width = 854
            session.config.height = 480
            session.config.fps = 24
            session.config.video_bitrate = 700_000
        elif bandwidth < 2_500_000:  # < 2.5 Mbps
            session.config.width = 1280
            session.config.height = 720
            session.config.fps = 30
            session.config.video_bitrate = 1_500_000
        else:  # >= 2.5 Mbps
            session.config.width = 1920
            session.config.height = 1080
            session.config.fps = 30
            session.config.video_bitrate = 3_000_000
        
        logger.info(
            "Stream quality adjusted",
            session_id=session_id,
            resolution=f"{session.config.width}x{session.config.height}",
            fps=session.config.fps,
            bitrate=session.config.video_bitrate,
        )

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return [
            sid for sid, session in self.sessions.items()
            if session.is_active
        ]

    def get_user_sessions(self, user_id: str) -> List[str]:
        """Get all sessions for a user."""
        return [
            sid for sid, session in self.sessions.items()
            if session.user_id == user_id
        ]


# Singleton instances
stream_manager = StreamManager()
live_pipeline = LiveAvatarPipeline()
