import asyncio
import json
import logging
import uuid
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay

logger = structlog.get_logger()

app = FastAPI(title="Neura Live Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active peer connections
pcs = set()

@app.on_event("shutdown")
async def shutdown():
    # Close all active connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "live", "active_connections": len(pcs)}

@app.post("/offer")
async def offer(request: Request):
    """
    WebRTC Offer handler.
    Receives SDP offer from client, returns SDP answer.
    """
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    
    # Configure ICE servers for NAT traversal
    config = {
        "iceServers": [
            {"urls": ["stun:stun.l.google.com:19302"]},
            {"urls": ["stun:stun1.l.google.com:19302"]},
        ]
    }
    pc = RTCPeerConnection(configuration=config)
    pcs.add(pc)
    
    logger.info("New WebRTC connection created", pc_id=id(pc))
    
    # Prepare to record or process media
    # For now, just blackhole (consume) the media so it flows
    recorder = MediaBlackhole()

    # Create pipeline (unique per connection or shared?)
    # For a real scalable app, we need a better lifecycle management.
    from pipeline import AIPipeline
    from stream_track import TTSStreamTrack
    
    pipeline = AIPipeline()
    tts_track = TTSStreamTrack()
    
    # Add TTS track to PC so client can hear us
    pc.addTrack(tts_track)
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info("Connection state changed", state=pc.connectionState, pc_id=id(pc))
        if pc.connectionState == "connected":
           logger.info("Connection established, ready for interaction")
        elif pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)
        elif pc.connectionState == "closed":
            await pipeline.stop_stt()
            pcs.discard(pc)

    @pc.on("track")
    def on_track(track):
        logger.info("Track received", kind=track.kind, pc_id=id(pc))
        
        if track.kind == "audio":
            # Start STT processing
            async def on_transcript(text):
                logger.info("Transcript", text=text)
                # 1. Ask LLM
                response_gen = pipeline.generate_response(text)
                
                # 2. Stream response strings -> buffer full sentences -> TTS
                # For simplicity, we'll just wait for full chunks or process sentence by sentence
                # Naive: synthesize each chunk? No, too choppy. 
                # Better: Accumulate sentences.
                
                full_text = ""
                async for chunk in response_gen:
                    # simplistic buffering
                    full_text += chunk
                    # Logic to split by sentence would go here
                    
                # 3. Send to TTS
                logger.info("LLM Response", text=full_text)
                if full_text:
                    wav_data = await pipeline.synthesize_speech(full_text)
                    if wav_data:
                        logger.info("TTS Audio generated", bytes=len(wav_data))
                        await tts_track.add_audio(wav_data)

            # Start Deepgram listening
            asyncio.create_task(pipeline.start_stt(on_transcript))
            
            # Pipe audio to Deepgram
            # We need to read frames from track and send to pipeline
            async def process_audio_track():
                while True:
                    try:
                        frame = await track.recv()
                        # frame is an AudioFrame. 
                        # We need raw bytes for Deepgram? or specific format?
                        # AudioFrame.to_ndarray() -> convert to bytes
                        # Deepgram expects linear16.
                        
                        # Resample if needed? 
                        # If track is 48k and RG is 48k, just pass bytes?
                        # Using to_ndarray().tobytes() gives raw PCM
                        data = frame.to_ndarray().tobytes()
                        await pipeline.process_audio_frame(data)
                        
                    except Exception as e:
                        # logger.info("Track ended or error", error=str(e))
                        break
            
            asyncio.create_task(process_audio_track())
            
        @track.on("ended")
        async def on_ended():
            logger.info("Track ended", kind=track.kind, pc_id=id(pc))
            await pipeline.stop_stt()

    # Set remote description
    await pc.setRemoteDescription(offer)
    
    # Create answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    
    # Wait for ICE gathering to complete
    while pc.iceGatheringState != "complete":
        await asyncio.sleep(0.1)
    
    logger.info("ICE gathering complete", candidates_count="gathered")
    
    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }
