
import asyncio
import httpx
import os
import sys
import time
from pathlib import Path

TTS_URL = "http://localhost:8001"
AVATAR_URL = "http://localhost:8002"
AVATAR_ID = "272422d1-e4b1-413d-8311-621bd9b63881"
SCRIPT = "Hello! This is a direct test of the avatar system running on high quality. We expect teeth visibility and face enhancement."

async def test_direct():
    print("🔹 Direct Avatar Service Test")
    print("=" * 60)
    
    cwd = os.getcwd()
    audio_file = Path(cwd) / "tests/test_direct_audio.wav"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Generate TTS Audio
        print("\n1️⃣ Generating TTS Audio...")
        try:
            resp = await client.post(
                f"{TTS_URL}/synthesize",
                json={
                    "text": SCRIPT,
                    "voice_id": "james", # Male voice
                    "language": "en"
                }
            )
            resp.raise_for_status()
            audio_data = resp.content
            audio_file.write_bytes(audio_data)
            print(f"   ✅ Audio generated at {audio_file}")
            
            # Extract word timings (mocked or real)
            word_timings = []
            if "X-Word-Timings" in resp.headers:
                import json
                try:
                    word_timings = json.loads(resp.headers["X-Word-Timings"].replace("'", '"'))
                except:
                    pass
            
        except Exception as e:
            print(f"❌ TTS Failed: {e}")
            return

        # 2. Call Avatar Service Render
        print("\n2️⃣ Requesting Avatar Render (1080p + GFPGAN)...")
        job_id = f"direct_test_{int(time.time())}"
        
        payload = {
            "job_id": job_id,
            "avatar_id": AVATAR_ID,
            "audio_url": str(audio_file),
            "word_timings": word_timings,
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "quality": "high",
            "emotion": "happy",
            "expression_scale": 1.3,
            "head_pose_scale": 1.0,
            "use_sadtalker": True
        }
        
        try:
            resp = await client.post(f"{AVATAR_URL}/render", json=payload)
            resp.raise_for_status()
            print(f"   ✅ Render job started: {job_id}")
        except Exception as e:
            print(f"❌ Render Request Failed: {e}")
            print(f"   Response: {resp.text if 'resp' in locals() else 'N/A'}")
            return
            
        # 3. Poll Status
        print("\n3️⃣ Waiting for completion...")
        print("   (This might take ~10 mins for 1080p enhancement)")
        
        for i in range(300): # 10 mins
            try:
                resp = await client.get(f"{AVATAR_URL}/render/{job_id}/status")
                if resp.status_code == 404:
                    print(f"\r   [{i*2}s] Job not found yet...", end="")
                else:
                    data = resp.json()
                    status = data["status"]
                    progress = data.get("progress", 0) * 100
                    step = data.get("current_step", "Unknown")
                    error = data.get("error", "")
                    
                    sys.stdout.write(f"\r   [{i*2}s] {status.upper()} | {progress:.0f}% | {step}                    ")
                    sys.stdout.flush()
                    
                    if status == "completed":
                        print(f"\n\n✅ COMPLETED!")
                        # Download URL
                        download_url = f"{AVATAR_URL}/render/{job_id}/download"
                        print(f"   Download URL: {download_url}")
                        
                        # Verify file exists where service put it
                        # The service puts it in `services/avatar/temp/{job_id}_output.mp4`
                        # We can verify that path directly too if we want
                        service_output = Path(cwd) / f"services/avatar/temp/{job_id}_output.mp4"
                        if service_output.exists():
                            print(f"   ✅ File verified on disk: {service_output}")
                        else:
                            print(f"   ⚠️ File not found on disk at expected path: {service_output}")
                            
                        return
                    elif status == "failed":
                        print(f"\n\n❌ FAILED: {error}")
                        return
                        
            except Exception as e:
                print(f"\n❌ Poll Error: {e}")
            
            await asyncio.sleep(2)
            
        print("\n\n⏱️ Timeout waiting for completion")

if __name__ == "__main__":
    asyncio.run(test_direct())
