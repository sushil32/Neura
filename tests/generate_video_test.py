import asyncio
import httpx
import json
import os
from pathlib import Path
import re

# --- Configuration ---
TTS_URL = "http://localhost:8001"
AVATAR_URL = "http://localhost:8002"
OUTPUT_DIR = "/Users/sushildubey/AI/Neura/output"
SCRIPT = """[0:00 - 0:05 | Intro]
Hello! We are testing the full video generation pipeline.
[VISUAL: Wave hand]
This test verifies script cleaning, audio synthesis, and video rendering.
Hope it works perfectly!"""

# --- Helpers ---
def clean_text_for_tts(text: str) -> str:
    """Duplicate of backend logic for standalone testing."""
    if not text: return ""
    text = re.sub(r'\[\d{1,2}:\d{2}.*?\]', '', text)
    text = re.sub(r'\[vis.*?\]', '', text, flags=re.IGNORECASE)
    lines = []
    for line in text.split('\n'):
        if '|' in line and len(line) < 100: continue
        lines.append(line)
    text = '\n'.join(lines)
    text = re.sub(r'\[pause.*?\]', '... ', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --- Helpers ---
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

def start_file_server(directory, port=8888):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)
        def log_message(self, format, *args): pass # specific logging silence
            
    server = HTTPServer(('0.0.0.0', port), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server

async def run_test():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    # Start local file server for audio
    # Use /tmp for storage
    audio_dir = "/tmp"
    server = start_file_server(audio_dir, 8099)
    print(f"🔹 Started local file server on port 8099 serving {audio_dir}")

    print(f"🔹 Starting End-to-End Test")
    print(f"🔹 Output Directory: {OUTPUT_DIR}")
    
    # 1. Clean Script
    cleaned_text = clean_text_for_tts(SCRIPT)
    print(f"✅ Cleaned Script: '{cleaned_text}'")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # 1.5 Upload Avatar (to ensure it exists in service)
        print("🔹 Uploading Avatar...")
        avatar_file = Path("services/avatar/avatars/default.jpg")
        if not avatar_file.exists():
             print(f"❌ Default avatar file not found at {avatar_file}")
             pass
        else:
            try:
                files = {"image": ("default.jpg", avatar_file.read_bytes(), "image/jpeg")}
                data = {"avatar_id": "default"}
                up_resp = await client.post(f"{AVATAR_URL}/avatars/upload", data=data, files=files)
                if up_resp.status_code == 200:
                    print(f"✅ Avatar uploaded successfully")
                else:
                    print(f"⚠️ Avatar upload failed: {up_resp.text} (Proceeding, maybe it exists)")
            except Exception as e:
                print(f"⚠️ Avatar upload error: {e}")

        # 2. Generate Audio (TTS)
        print("🔹 Calling TTS Service...")
        try:
            tts_resp = await client.post(
                f"{TTS_URL}/synthesize",
                json={
                    "text": cleaned_text,
                    "voice_id": "default",
                    "language": "en",
                    "speed": 1.0
                }
            )
            if tts_resp.status_code != 200:
                print(f"❌ TTS Failed: {tts_resp.text}")
                return
            
            # Extract headers
            word_timings = json.loads(tts_resp.headers.get("X-Word-Timings", "[]").replace("'", '"'))
            
            # Save to /tmp for serving
            audio_filename = "test_audio_for_neura.wav"
            audio_path = Path(audio_dir) / audio_filename
            audio_path.write_bytes(tts_resp.content)
            print(f"✅ Audio generated: {audio_path} ({len(tts_resp.content)} bytes)")
            
            # Construct URL
            # Use host.docker.internal for Docker for Mac to access host
            # Fallback to localhost if running natively
            audio_url = f"http://host.docker.internal:8099/{audio_filename}"
            print(f"🔹 Served Audio URL: {audio_url}")
            
        except Exception as e:
            print(f"❌ TTS Connection Error: {e}")
            return

        # 3. Render Video (Avatar)
        print("🔹 Calling Avatar Service...")
        try:
            render_resp = await client.post(
                f"{AVATAR_URL}/render",
                json={
                    "job_id": "test_job_manual_001",
                    "avatar_id": "default",
                    "audio_url": audio_url, 
                    "word_timings": word_timings,
                    "width": 1280,
                    "height": 720,
                    "fps": 30
                }
            )
            
            if render_resp.status_code != 200:
                 print(f"❌ Avatar Render Request Failed: {render_resp.status_code} - {render_resp.content}")
                 return

            job_data = render_resp.json()
            
            # Since we manually invoked, let's just poll status
            print("🔹 Waiting for Render...")
            import time
            while True:
                status_resp = await client.get(f"{AVATAR_URL}/render/test_job_manual_001/status")
                if status_resp.status_code != 200:
                    print(f"❌ Status Check Failed: {status_resp.text}")
                    break
                
                status = status_resp.json()
                print(f"   Status: {status.get('status')} - {status.get('current_step', '')}")
                
                if status.get("status") == "completed":
                    break
                if status.get("status") == "failed":
                    print(f"❌ Render Failed: {status.get('error')}")
                    return
                
                await asyncio.sleep(2)
            
            # 4. Download Video
            print("🔹 Downloading Video...")
            dl_resp = await client.get(f"{AVATAR_URL}/render/test_job_manual_001/download")
            if dl_resp.status_code == 200:
                out_path = Path(OUTPUT_DIR) / "final_test_video.mp4"
                out_path.write_bytes(dl_resp.content)
                print(f"✅ SUCCESS! Video saved to: {out_path}")
            else:
                 print(f"❌ Download Failed: {dl_resp.text}")

        except Exception as e:
            print(f"❌ Avatar Service Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
