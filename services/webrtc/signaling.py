"""WebRTC signaling server with full SDP negotiation."""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

import structlog
from fastapi import WebSocket, WebSocketDisconnect

logger = structlog.get_logger()

# Try to import aiortc for proper WebRTC support
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
    from aiortc.contrib.media import MediaPlayer, MediaRelay
    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    logger.warning("aiortc not available, using fallback signaling")


@dataclass
class RTCSession:
    """WebRTC session information."""
    session_id: str
    user_id: str
    websocket: WebSocket
    created_at: datetime = field(default_factory=datetime.utcnow)
    ice_candidates: List[Dict] = field(default_factory=list)
    sdp_offer: Optional[str] = None
    sdp_answer: Optional[str] = None
    is_connected: bool = False
    peer_connection: Any = None  # RTCPeerConnection
    avatar_id: Optional[str] = None
    voice_id: Optional[str] = None
    last_activity: datetime = field(default_factory=datetime.utcnow)


class SignalingServer:
    """
    WebRTC signaling server for live avatar sessions.
    
    Handles:
    - Session management
    - SDP offer/answer exchange  
    - ICE candidate exchange
    - Connection state tracking
    - Media track management
    """

    def __init__(self):
        self.sessions: Dict[str, RTCSession] = {}
        self.user_sessions: Dict[str, Set[str]] = {}
        self._on_message_callback: Optional[Callable] = None
        self._on_audio_callback: Optional[Callable] = None
        self._media_relay = None
        
        if AIORTC_AVAILABLE:
            self._media_relay = MediaRelay()

    def set_message_callback(self, callback: Callable):
        """Set callback for handling text messages."""
        self._on_message_callback = callback

    def set_audio_callback(self, callback: Callable):
        """Set callback for handling audio input."""
        self._on_audio_callback = callback

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str,
        avatar_id: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> None:
        """Handle a new WebSocket connection."""
        await websocket.accept()
        
        # Create session
        session = RTCSession(
            session_id=session_id,
            user_id=user_id,
            websocket=websocket,
            avatar_id=avatar_id,
            voice_id=voice_id,
        )
        self.sessions[session_id] = session
        
        # Track user sessions
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = set()
        self.user_sessions[user_id].add(session_id)
        
        logger.info(
            "WebRTC session created",
            session_id=session_id,
            user_id=user_id,
            avatar_id=avatar_id,
        )
        
        try:
            # Send session info to client
            await self._send(session, {
                "type": "session_created",
                "session_id": session_id,
                "ice_servers": self._get_ice_servers(),
                "capabilities": {
                    "webrtc": AIORTC_AVAILABLE,
                    "audio_input": True,
                    "video_output": True,
                },
            })
            
            # Handle messages
            await self._message_loop(session)
            
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected", session_id=session_id)
        except Exception as e:
            logger.error("WebSocket error", session_id=session_id, error=str(e))
        finally:
            await self._cleanup_session(session_id)

    async def _message_loop(self, session: RTCSession) -> None:
        """Process incoming WebSocket messages."""
        while True:
            try:
                data = await session.websocket.receive_json()
                message_type = data.get("type")
                session.last_activity = datetime.utcnow()
                
                logger.debug(
                    "Received signaling message",
                    session_id=session.session_id,
                    type=message_type,
                )
                
                handlers = {
                    "offer": self._handle_offer,
                    "answer": self._handle_answer,
                    "ice_candidate": self._handle_ice_candidate,
                    "message": self._handle_user_message,
                    "audio": self._handle_audio_message,
                    "start_stream": self._handle_start_stream,
                    "stop_stream": self._handle_stop_stream,
                    "ping": self._handle_ping,
                    "config": self._handle_config,
                }
                
                handler = handlers.get(message_type)
                if handler:
                    await handler(session, data)
                else:
                    logger.warning(
                        "Unknown message type",
                        session_id=session.session_id,
                        type=message_type,
                    )
                    
            except WebSocketDisconnect:
                raise
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON", session_id=session.session_id, error=str(e))
                await self._send(session, {
                    "type": "error",
                    "error": "Invalid JSON format",
                })
            except Exception as e:
                logger.error(
                    "Error processing message",
                    session_id=session.session_id,
                    error=str(e),
                )
                await self._send(session, {
                    "type": "error",
                    "error": str(e),
                })

    async def _handle_offer(self, session: RTCSession, data: dict) -> None:
        """Handle SDP offer from client."""
        sdp = data.get("sdp")
        sdp_type = data.get("sdp_type", "offer")
        
        session.sdp_offer = sdp
        
        if AIORTC_AVAILABLE:
            try:
                # Create peer connection
                pc = RTCPeerConnection()
                session.peer_connection = pc
                
                # Handle connection state changes
                @pc.on("connectionstatechange")
                async def on_connectionstatechange():
                    logger.info(
                        "Connection state changed",
                        session_id=session.session_id,
                        state=pc.connectionState,
                    )
                    if pc.connectionState == "connected":
                        session.is_connected = True
                        await self._send(session, {
                            "type": "connection_ready",
                            "session_id": session.session_id,
                        })
                    elif pc.connectionState in ["failed", "closed"]:
                        session.is_connected = False
                
                # Handle ICE candidates
                @pc.on("icecandidate")
                async def on_icecandidate(candidate):
                    if candidate:
                        await self._send(session, {
                            "type": "ice_candidate",
                            "candidate": {
                                "candidate": candidate.candidate,
                                "sdpMid": candidate.sdpMid,
                                "sdpMLineIndex": candidate.sdpMLineIndex,
                            },
                        })
                
                # Handle incoming tracks (audio from client)
                @pc.on("track")
                async def on_track(track):
                    logger.info(
                        "Received track",
                        session_id=session.session_id,
                        kind=track.kind,
                    )
                    if track.kind == "audio" and self._on_audio_callback:
                        asyncio.create_task(
                            self._process_audio_track(session, track)
                        )
                
                # Set remote description (client's offer)
                offer = RTCSessionDescription(sdp=sdp, type=sdp_type)
                await pc.setRemoteDescription(offer)
                
                # Create answer
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)
                
                session.sdp_answer = pc.localDescription.sdp
                
                await self._send(session, {
                    "type": "answer",
                    "sdp": session.sdp_answer,
                    "sdp_type": "answer",
                })
                
            except Exception as e:
                logger.error("Failed to handle offer", error=str(e))
                await self._send(session, {
                    "type": "error",
                    "error": f"WebRTC setup failed: {str(e)}",
                })
        else:
            # Fallback: send placeholder answer
            session.sdp_answer = self._generate_fallback_sdp()
            await self._send(session, {
                "type": "answer",
                "sdp": session.sdp_answer,
                "sdp_type": "answer",
            })

    async def _handle_answer(self, session: RTCSession, data: dict) -> None:
        """Handle SDP answer from client."""
        sdp = data.get("sdp")
        session.sdp_answer = sdp
        
        if session.peer_connection and AIORTC_AVAILABLE:
            try:
                answer = RTCSessionDescription(sdp=sdp, type="answer")
                await session.peer_connection.setRemoteDescription(answer)
            except Exception as e:
                logger.error("Failed to set remote description", error=str(e))
        
        session.is_connected = True
        await self._send(session, {
            "type": "connection_ready",
            "session_id": session.session_id,
        })

    async def _handle_ice_candidate(self, session: RTCSession, data: dict) -> None:
        """Handle ICE candidate from client."""
        candidate_data = data.get("candidate", {})
        
        if isinstance(candidate_data, str):
            candidate_data = {"candidate": candidate_data}
        
        session.ice_candidates.append(candidate_data)
        
        if session.peer_connection and AIORTC_AVAILABLE:
            try:
                candidate = RTCIceCandidate(
                    candidate=candidate_data.get("candidate"),
                    sdpMid=candidate_data.get("sdpMid"),
                    sdpMLineIndex=candidate_data.get("sdpMLineIndex"),
                )
                await session.peer_connection.addIceCandidate(candidate)
            except Exception as e:
                logger.warning("Failed to add ICE candidate", error=str(e))

    async def _handle_user_message(self, session: RTCSession, data: dict) -> None:
        """Handle user text message for avatar processing."""
        content = data.get("content", "")
        
        if self._on_message_callback:
            try:
                response = await self._on_message_callback(
                    session.session_id,
                    session.user_id,
                    content,
                    session.avatar_id,
                    session.voice_id,
                )
                
                await self._send(session, {
                    "type": "avatar_response",
                    "content": response.get("text", ""),
                    "audio_url": response.get("audio_url"),
                    "frames": response.get("frames", []),
                })
            except Exception as e:
                logger.error("Message processing failed", error=str(e))
                await self._send(session, {
                    "type": "error",
                    "error": f"Processing failed: {str(e)}",
                })

    async def _handle_audio_message(self, session: RTCSession, data: dict) -> None:
        """Handle audio data sent via WebSocket (fallback for WebRTC)."""
        audio_data = data.get("audio")  # Base64 encoded
        
        if audio_data and self._on_audio_callback:
            import base64
            try:
                audio_bytes = base64.b64decode(audio_data)
                response = await self._on_audio_callback(
                    session.session_id,
                    session.user_id,
                    audio_bytes,
                )
                
                await self._send(session, {
                    "type": "avatar_response",
                    "content": response.get("text", ""),
                    "audio": response.get("audio"),  # Base64 response audio
                })
            except Exception as e:
                logger.error("Audio processing failed", error=str(e))

    async def _handle_start_stream(self, session: RTCSession, data: dict) -> None:
        """Handle request to start avatar stream."""
        session.avatar_id = data.get("avatar_id", session.avatar_id)
        session.voice_id = data.get("voice_id", session.voice_id)
        
        await self._send(session, {
            "type": "stream_started",
            "session_id": session.session_id,
            "avatar_id": session.avatar_id,
            "voice_id": session.voice_id,
        })

    async def _handle_stop_stream(self, session: RTCSession, data: dict) -> None:
        """Handle request to stop avatar stream."""
        session.is_connected = False
        
        if session.peer_connection:
            await session.peer_connection.close()
            session.peer_connection = None
        
        await self._send(session, {
            "type": "stream_stopped",
            "session_id": session.session_id,
        })

    async def _handle_ping(self, session: RTCSession, data: dict) -> None:
        """Handle ping message."""
        await self._send(session, {
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _handle_config(self, session: RTCSession, data: dict) -> None:
        """Handle configuration update."""
        if "avatar_id" in data:
            session.avatar_id = data["avatar_id"]
        if "voice_id" in data:
            session.voice_id = data["voice_id"]
        
        await self._send(session, {
            "type": "config_updated",
            "avatar_id": session.avatar_id,
            "voice_id": session.voice_id,
        })

    async def _process_audio_track(self, session: RTCSession, track) -> None:
        """Process incoming audio track from WebRTC."""
        while True:
            try:
                frame = await track.recv()
                
                if self._on_audio_callback:
                    # Convert frame to bytes and process
                    audio_data = frame.to_ndarray().tobytes()
                    await self._on_audio_callback(
                        session.session_id,
                        session.user_id,
                        audio_data,
                    )
            except Exception as e:
                logger.error("Audio track processing error", error=str(e))
                break

    def _generate_fallback_sdp(self) -> str:
        """Generate fallback SDP when aiortc is not available."""
        return f"""v=0
o=- {uuid4().int} 1 IN IP4 127.0.0.1
s=NEURA Avatar Stream
t=0 0
a=group:BUNDLE 0 1
m=video 9 UDP/TLS/RTP/SAVPF 96
c=IN IP4 0.0.0.0
a=rtcp:9 IN IP4 0.0.0.0
a=rtpmap:96 VP8/90000
a=sendonly
a=mid:0
m=audio 9 UDP/TLS/RTP/SAVPF 111
c=IN IP4 0.0.0.0
a=rtpmap:111 opus/48000/2
a=sendonly
a=mid:1
"""

    def _get_ice_servers(self) -> List[Dict]:
        """Get ICE server configuration."""
        return [
            {"urls": ["stun:stun.l.google.com:19302"]},
            {"urls": ["stun:stun1.l.google.com:19302"]},
            {"urls": ["stun:stun2.l.google.com:19302"]},
            # Add TURN servers for production NAT traversal
            # {
            #     "urls": ["turn:turn.neura.ai:3478"],
            #     "username": "neura",
            #     "credential": "secret"
            # }
        ]

    async def _send(self, session: RTCSession, data: dict) -> None:
        """Send message to client."""
        try:
            await session.websocket.send_json(data)
        except Exception as e:
            logger.error(
                "Failed to send message",
                session_id=session.session_id,
                error=str(e),
            )

    async def send_to_session(self, session_id: str, data: dict) -> bool:
        """Send message to a specific session."""
        session = self.sessions.get(session_id)
        if session:
            await self._send(session, data)
            return True
        return False

    async def send_frame(
        self,
        session_id: str,
        frame_data: bytes,
        timestamp: float,
    ) -> bool:
        """Send video frame to session (via WebRTC data channel or WebSocket)."""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        import base64
        
        # Send via WebSocket as fallback
        await self._send(session, {
            "type": "frame",
            "data": base64.b64encode(frame_data).decode(),
            "timestamp": timestamp,
        })
        return True

    async def send_audio(
        self,
        session_id: str,
        audio_data: bytes,
    ) -> bool:
        """Send audio data to session."""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        import base64
        
        await self._send(session, {
            "type": "audio",
            "data": base64.b64encode(audio_data).decode(),
        })
        return True

    async def broadcast_to_user(self, user_id: str, data: dict) -> int:
        """Broadcast message to all sessions of a user."""
        session_ids = self.user_sessions.get(user_id, set())
        count = 0
        for session_id in session_ids:
            if await self.send_to_session(session_id, data):
                count += 1
        return count

    async def _cleanup_session(self, session_id: str) -> None:
        """Clean up a session."""
        session = self.sessions.pop(session_id, None)
        if session:
            # Close peer connection
            if session.peer_connection:
                try:
                    await session.peer_connection.close()
                except:
                    pass
            
            # Remove from user sessions
            user_sessions = self.user_sessions.get(session.user_id)
            if user_sessions:
                user_sessions.discard(session_id)
                if not user_sessions:
                    del self.user_sessions[session.user_id]
            
            logger.info("Session cleaned up", session_id=session_id)

    def get_session(self, session_id: str) -> Optional[RTCSession]:
        """Get session by ID."""
        return self.sessions.get(session_id)

    def get_user_sessions(self, user_id: str) -> Set[str]:
        """Get all session IDs for a user."""
        return self.user_sessions.get(user_id, set())

    def get_active_session_count(self) -> int:
        """Get count of active sessions."""
        return len(self.sessions)


# Singleton instance
signaling_server = SignalingServer()
