"""WebRTC stream management for live avatar."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator, Callable, Dict, Optional
from uuid import uuid4

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class StreamConfig:
    """Configuration for video stream."""
    width: int = 1280
    height: int = 720
    fps: int = 30
    video_bitrate: int = 2_000_000  # 2 Mbps
    audio_bitrate: int = 128_000  # 128 kbps
    codec: str = "VP8"


@dataclass
class StreamSession:
    """Active streaming session."""
    session_id: str
    user_id: str
    config: StreamConfig
    started_at: datetime = field(default_factory=datetime.utcnow)
    frames_sent: int = 0
    bytes_sent: int = 0
    is_active: bool = True


class StreamManager:
    """
    Manages WebRTC video/audio streams for live avatars.
    
    Features:
    - Real-time frame encoding
    - Adaptive bitrate
    - Audio/video synchronization
    - Frame rate control
    """

    def __init__(self):
        self.sessions: Dict[str, StreamSession] = {}
        self._frame_generators: Dict[str, asyncio.Task] = {}

    async def start_stream(
        self,
        session_id: str,
        user_id: str,
        config: Optional[StreamConfig] = None,
        frame_callback: Optional[Callable] = None,
    ) -> StreamSession:
        """Start a new stream session."""
        config = config or StreamConfig()
        
        session = StreamSession(
            session_id=session_id,
            user_id=user_id,
            config=config,
        )
        self.sessions[session_id] = session
        
        logger.info(
            "Stream started",
            session_id=session_id,
            resolution=f"{config.width}x{config.height}",
            fps=config.fps,
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
            
            duration = (datetime.utcnow() - session.started_at).total_seconds()
            
            stats = {
                "session_id": session_id,
                "duration": duration,
                "frames_sent": session.frames_sent,
                "bytes_sent": session.bytes_sent,
                "avg_fps": session.frames_sent / duration if duration > 0 else 0,
                "avg_bitrate": session.bytes_sent * 8 / duration if duration > 0 else 0,
            }
            
            logger.info("Stream stopped", **stats)
            return stats
        
        return None

    async def generate_frames(
        self,
        session_id: str,
        avatar_renderer: "AvatarRenderer",
        avatar_config: Dict,
    ) -> AsyncGenerator[bytes, None]:
        """Generate avatar frames for streaming."""
        session = self.sessions.get(session_id)
        if not session:
            return
        
        frame_interval = 1.0 / session.config.fps
        
        while session.is_active:
            start_time = asyncio.get_event_loop().time()
            
            try:
                # Render frame
                frame_data = await avatar_renderer._render_frame(
                    avatar_config,
                    {},  # Current lip sync params
                    type('Config', (), {
                        'width': session.config.width,
                        'height': session.config.height,
                        'background_color': '#000000',
                    })(),
                )
                
                # Encode frame for WebRTC
                encoded = await self._encode_frame(frame_data, session.config)
                
                session.frames_sent += 1
                session.bytes_sent += len(encoded)
                
                yield encoded
                
            except Exception as e:
                logger.error("Frame generation error", error=str(e))
            
            # Frame rate control
            elapsed = asyncio.get_event_loop().time() - start_time
            sleep_time = max(0, frame_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    async def push_audio(
        self,
        session_id: str,
        audio_data: bytes,
        timestamp: float,
    ) -> bool:
        """Push audio data to stream."""
        session = self.sessions.get(session_id)
        if not session or not session.is_active:
            return False
        
        # In production, this would:
        # 1. Encode audio (Opus)
        # 2. Package as RTP
        # 3. Send through WebRTC
        
        session.bytes_sent += len(audio_data)
        return True

    async def update_lip_sync(
        self,
        session_id: str,
        viseme: str,
        intensity: float,
    ) -> None:
        """Update lip sync state for the stream."""
        # This would update the avatar renderer's lip sync state
        pass

    async def _encode_frame(
        self,
        frame_data: bytes,
        config: StreamConfig,
    ) -> bytes:
        """Encode frame for WebRTC transmission."""
        # In production, this would:
        # 1. Convert to YUV420
        # 2. Encode with VP8/VP9/H264
        # 3. Package as RTP
        
        # For now, return raw data (would need proper encoding)
        return frame_data

    def get_stats(self, session_id: str) -> Optional[Dict]:
        """Get stream statistics."""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        duration = (datetime.utcnow() - session.started_at).total_seconds()
        
        return {
            "session_id": session_id,
            "is_active": session.is_active,
            "duration": duration,
            "frames_sent": session.frames_sent,
            "bytes_sent": session.bytes_sent,
            "current_fps": session.frames_sent / duration if duration > 0 else 0,
            "current_bitrate": session.bytes_sent * 8 / duration if duration > 0 else 0,
            "resolution": f"{session.config.width}x{session.config.height}",
            "target_fps": session.config.fps,
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
        
        # Calculate optimal settings based on bandwidth
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
        )

