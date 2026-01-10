import os
import asyncio
import json
import logging
import structlog
import httpx
from typing import Optional, AsyncGenerator, List, Dict

# Third-party integrations
try:
    from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions
except ImportError:
    DeepgramClient = None

import google.generativeai as genai

logger = structlog.get_logger()

class AIPipeline:
    """
    Manages the bi-directional audio Conversation.
    Audio Input -> STT -> LLM -> TTS -> Audio Output
    """
    def __init__(self):
        self.deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.tts_url = os.getenv("TTS_SERVICE_URL", "http://neura-tts:8001")
        
        self.dg_client = None
        self.dg_connection = None
        
        self.llm_history: List[Dict[str, str]] = []
        self.system_prompt = "You are Neura, a helpful AI assistant. Keep your responses concise and conversational."

        # State
        self.is_listening = False
        self.processing_audio = False
        
        # Initialize
        self.model = None  # Explicit initialization
        self._setup_stt()
        self._setup_llm()

    def _setup_stt(self):
        if self.deepgram_key and DeepgramClient:
            try:
                config = DeepgramClientOptions(verbose=logging.INFO)
                self.dg_client = DeepgramClient(self.deepgram_key, config)
                logger.info("Deepgram client initialized")
            except Exception as e:
                logger.error("Failed to initialize Deepgram", error=str(e))
        else:
            logger.warning("Deepgram API key missing or SDK not installed. STT will be disabled.")

    def _setup_llm(self):
        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.model = genai.GenerativeModel('gemini-pro')
            logger.info("Gemini LLM initialized")
        else:
            logger.warning("Gemini API key missing. LLM will be disabled.")

    async def start_stt(self, on_transcript):
        """
        Connects to Deepgram Live Stream.
        on_transcript: callback(text: str, is_final: bool)
        """
        if not self.dg_client:
            return

        try:
            self.dg_connection = self.dg_client.listen.asyncwebsocket.v("1")

            async def on_message(result, **kwargs):
                sentence = result.channel.alternatives[0].transcript
                if len(sentence) == 0:
                    return
                    
                is_final = result.is_final
                # logger.info("STT Transcript", text=sentence, is_final=is_final)
                if is_final:
                    await on_transcript(sentence)

            self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

            options = LiveOptions(
                model="nova-2", 
                language="en-US", 
                smart_format=True, 
                encoding="linear16", 
                channels=1, 
                sample_rate=48000, 
                interim_results=True
            )

            await self.dg_connection.start(options)
            self.is_listening = True
            logger.info("Deepgram Live STT started")

        except Exception as e:
            logger.error("Failed to start Deepgram STT", error=str(e))

    async def stop_stt(self):
        if self.dg_connection:
            await self.dg_connection.finish()
            self.dg_connection = None
            self.is_listening = False
            logger.info("Deepgram Live STT stopped")

    async def process_audio_frame(self, data: bytes):
        """
        Push raw audio bytes to STT.
        Expected format: 16-bit PCM, 48kHz (or whatever matches STT options)
        """
        if self.dg_connection and self.is_listening:
            await self.dg_connection.send(data)

    async def generate_response(self, text: str) -> AsyncGenerator[str, None]:
        """
        Send text to LLM and stream response text.
        """
        if not self.model:
            yield "I'm sorry, my brain is not connected right now."
            return

        # Simple memory management
        self.llm_history.append({"role": "user", "parts": [text]})
        
        # Construct context with system prompt if possible, or just prepend
        input_messages = [{"role": "user", "parts": [self.system_prompt + "\n\nUser: " + text]}]
        # Note: A real implementation would manage history better to avoid context limits
        
        try:
            response = await self.model.generate_content_async(text, stream=True)
            
            full_response = ""
            async for chunk in response:
                content = chunk.text
                full_response += content
                yield content
            
            self.llm_history.append({"role": "model", "parts": [full_response]})
            
        except Exception as e:
            logger.error("LLM Generation failed", error=str(e))
            yield "I encountered an error thinking of a response."

    async def synthesize_speech(self, text: str) -> Optional[bytes]:
        """
        Convert text to audio using Neura TTS service.
        Returns bytes (Audio data wav).
        """
        # We can hit the /synthesize endpoint
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "text": text,
                    "voice_id": "default", # or customizable
                    "language": "en",
                    "speed": 1.0
                }
                response = await client.post(f"{self.tts_url}/synthesize", json=payload, timeout=10.0)
                if response.status_code == 200:
                    return response.content
                else:
                    logger.error("TTS failed", status=response.status_code, body=response.text)
            except Exception as e:
                logger.error("TTS Request failed", error=str(e))
        return None
