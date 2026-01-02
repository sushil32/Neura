"""WebRTC signaling server."""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Optional, Set
from uuid import uuid4

import structlog
from fastapi import WebSocket, WebSocketDisconnect

logger = structlog.get_logger()


@dataclass
class RTCSession:
    """WebRTC session information."""
    session_id: str
    user_id: str
    websocket: WebSocket
    created_at: datetime = field(default_factory=datetime.utcnow)
    ice_candidates: list = field(default_factory=list)
    sdp_offer: Optional[str] = None
    sdp_answer: Optional[str] = None
    is_connected: bool = False


class SignalingServer:
    """
    WebRTC signaling server for live avatar sessions.
    
    Handles:
    - Session management
    - SDP offer/answer exchange
    - ICE candidate exchange
    - Connection state tracking
    """

    def __init__(self):
        self.sessions: Dict[str, RTCSession] = {}
        self.user_sessions: Dict[str, Set[str]] = {}
        self._on_message_callback: Optional[Callable] = None

    def set_message_callback(self, callback: Callable):
        """Set callback for handling incoming messages."""
        self._on_message_callback = callback

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str,
    ) -> None:
        """Handle a new WebSocket connection."""
        await websocket.accept()
        
        # Create session
        session = RTCSession(
            session_id=session_id,
            user_id=user_id,
            websocket=websocket,
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
        )
        
        try:
            # Send session info to client
            await self._send(session, {
                "type": "session_created",
                "session_id": session_id,
                "ice_servers": self._get_ice_servers(),
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
                
                logger.debug(
                    "Received signaling message",
                    session_id=session.session_id,
                    type=message_type,
                )
                
                if message_type == "offer":
                    await self._handle_offer(session, data)
                elif message_type == "answer":
                    await self._handle_answer(session, data)
                elif message_type == "ice_candidate":
                    await self._handle_ice_candidate(session, data)
                elif message_type == "message":
                    await self._handle_user_message(session, data)
                elif message_type == "ping":
                    await self._send(session, {"type": "pong"})
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
            except Exception as e:
                logger.error(
                    "Error processing message",
                    session_id=session.session_id,
                    error=str(e),
                )

    async def _handle_offer(self, session: RTCSession, data: dict) -> None:
        """Handle SDP offer from client."""
        session.sdp_offer = data.get("sdp")
        
        # Generate server's SDP answer
        # In production, this would involve:
        # 1. Creating PeerConnection
        # 2. Setting remote description
        # 3. Creating answer
        # 4. Setting local description
        
        # For now, send a placeholder answer
        answer_sdp = self._generate_server_sdp()
        session.sdp_answer = answer_sdp
        
        await self._send(session, {
            "type": "answer",
            "sdp": answer_sdp,
        })

    async def _handle_answer(self, session: RTCSession, data: dict) -> None:
        """Handle SDP answer (if server initiated)."""
        session.sdp_answer = data.get("sdp")
        session.is_connected = True
        
        await self._send(session, {
            "type": "connection_ready",
            "session_id": session.session_id,
        })

    async def _handle_ice_candidate(self, session: RTCSession, data: dict) -> None:
        """Handle ICE candidate from client."""
        candidate = data.get("candidate")
        if candidate:
            session.ice_candidates.append(candidate)
            
            # In production, add candidate to PeerConnection
            # For now, just acknowledge
            await self._send(session, {
                "type": "ice_candidate_received",
            })

    async def _handle_user_message(self, session: RTCSession, data: dict) -> None:
        """Handle user message for avatar processing."""
        content = data.get("content", "")
        message_type = data.get("message_type", "text")
        
        if self._on_message_callback:
            response = await self._on_message_callback(
                session.session_id,
                session.user_id,
                content,
                message_type,
            )
            
            await self._send(session, {
                "type": "avatar_response",
                "content": response,
            })

    def _generate_server_sdp(self) -> str:
        """Generate server SDP for WebRTC connection."""
        # In production, this would be generated by the WebRTC library
        # This is a simplified placeholder
        return f"""v=0
o=- {uuid4().int} 1 IN IP4 127.0.0.1
s=NEURA Avatar Stream
t=0 0
m=video 9 UDP/TLS/RTP/SAVPF 96
c=IN IP4 0.0.0.0
a=rtcp:9 IN IP4 0.0.0.0
a=rtpmap:96 VP8/90000
a=sendonly
m=audio 9 UDP/TLS/RTP/SAVPF 111
c=IN IP4 0.0.0.0
a=rtpmap:111 opus/48000/2
a=sendonly
"""

    def _get_ice_servers(self) -> list:
        """Get ICE server configuration."""
        return [
            {"urls": "stun:stun.l.google.com:19302"},
            {"urls": "stun:stun1.l.google.com:19302"},
            # In production, add TURN servers for NAT traversal
            # {
            #     "urls": "turn:turn.example.com:3478",
            #     "username": "user",
            #     "credential": "pass"
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

