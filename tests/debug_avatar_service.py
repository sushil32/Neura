
import asyncio
import httpx
import json
import os
from pathlib import Path

# Configuration
AVATAR_SERVICE_URL = "http://localhost:8002"

async def test_direct_render():
    print("🔹 Testing Avatar Service Directly")
    
    # 1. Health check
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AVATAR_SERVICE_URL}/health")
            print(f"✅ Health Check: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Health Check Failed: {e}")
            return

    # 2. Render Request
    # Use a dummy audio file path that hopefully exists or create one
    # If running locally, we need an absolute path that the container can access?
    # No, the container needs a path inside its volume.
    # But wait, how does the worker pass audio path? It passes a path that is shared mounted?
    # backend/app/workers/tasks.py passes `audio_path`.
    
    # Let's try to use a simple text instead if we can't easily pass audio.
    # But /render endpoint expects audio_path.
    
    # We will assume there is some audio in the container or we can't easily test this way without shared volume knowledge.
    # Actually, the worker and avatar service share `./services/avatar` volume? No.
    # They share `neura_audio` volume? No.
    
    # Docker compose volumes:
    # backend: ./backend:/app
    # avatar-service: ./services/avatar:/app
    
    # They don't share a tmp directory!
    # Wait, how does backend pass audio to avatar service?
    
    # backend/app/workers/tasks.py:
    # `audio_path_for_avatar` 
    # It seems they DON'T share volumes for temp files?
    
    # Let's check tasks.py again properly.
    pass

if __name__ == "__main__":
    asyncio.run(test_direct_render())
