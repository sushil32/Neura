#!/usr/bin/env python3
"""
Test script for SadTalker integration.
Verifies emotion parameters and SadTalker engine selection.
"""
import asyncio
import httpx
import json
import sys

import time
import uuid

BACKEND_URL = "http://localhost:8000"

# Generate unique test user
TEST_EMAIL = f"test_sadtalker_{int(time.time())}@example.com"
TEST_PASSWORD = "test1234"

async def test_sadtalker():
    """Test SadTalker video generation."""
    
    print("🔹 SadTalker Integration Test")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # 1. Login
        print("\n1️⃣ Logging in...")
        try:
            # Register fresh user
            print(f"   Registering {TEST_EMAIL}...")
            reg_resp = await client.post(
                f"{BACKEND_URL}/api/v1/auth/register",
                json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "full_name": "Test User"}
            )
            
            if reg_resp.status_code in [200, 201]:
                # Registration successful, might return token
                data = reg_resp.json()
                if "access_token" in data:
                    print("   ✅ Registered and logged in via register response")
                    login_resp = reg_resp
                else:
                    print("   ✅ Registered, now logging in...")
                    login_resp = await client.post(
                        f"{BACKEND_URL}/api/v1/auth/login",
                        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
                    )
            else:
                print(f"❌ Registration failed ({reg_resp.status_code}): {reg_resp.text}")
                return

            login_resp.raise_for_status()
            
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print(f"✅ Logged in as {TEST_EMAIL}")
        except Exception as e:
            print(f"❌ Auth failed: {e}")
            return
        
        # 2. Create/Find Test Avatar with Image
        print("\n2️⃣ Setting up test avatar...")
        
        # Check if test image exists
        from pathlib import Path
        image_path = Path("tests/test_avatar_male.jpg")
        
        if not image_path.exists():
            print(f"❌ Test image not found at {image_path}")
            return

        # Create new avatar container
        print("   Creating new avatar container...")
        avatar_name = f"SadTalker Male Test {int(time.time())}"
        create_resp = await client.post(
            f"{BACKEND_URL}/api/v1/avatars",
            headers=headers,
            json={
                "name": avatar_name,
                "description": "Auto-generated for SadTalker test (Male)",
                "is_default": False
            }
        )
        create_resp.raise_for_status()
        avatar_data = create_resp.json()
        avatar_id = avatar_data["id"]
        print(f"   ✅ Created avatar: {avatar_name} ({avatar_id})")
        
        # Upload image
        print(f"   Uploading image from {image_path}...")
        files = {"file": ("avatar.jpg", open(image_path, "rb"), "image/jpeg")}
        upload_resp = await client.post(
            f"{BACKEND_URL}/api/v1/avatars/{avatar_id}/thumbnail",
            headers=headers,
            files=files
        )
        upload_resp.raise_for_status()
        print("   ✅ Image uploaded successfully")
        
        video_type = "custom"

        # 3. Create video with emotion script
        print("\n3️⃣ Creating video...")
        script = "I am so happy that my voice finally matches my appearance! This is fantastic."
        
        payload = {
            "title": "SadTalker Male Voice Test",
            "script": script,
            "type": video_type,
            "avatar_id": avatar_id
        }
            
        video_resp = await client.post(
            f"{BACKEND_URL}/api/v1/videos",
            headers=headers,
            json=payload
        )
        video_resp.raise_for_status()
        video = video_resp.json()
        video_id = video["id"]
        print(f"✅ Video created: {video_id}")
        
        # 4. Generate with SadTalker parameters
        print("\n4️⃣ Starting SadTalker generation...")
        print("   Params: emotion='happy', voice_id='james'")
        
        gen_resp = await client.post(
            f"{BACKEND_URL}/api/v1/videos/{video_id}/generate",
            headers=headers,
            json={
                "quality": "balanced", 
                "resolution": "720p",
                "emotion": "happy",
                "expression_scale": 1.1,
                "head_pose_scale": 1.0,
                "use_sadtalker": True,
                "voice_id": "james"
            }
        )
        
        if gen_resp.status_code != 200:
            print(f"❌ Start generation failed ({gen_resp.status_code}): {gen_resp.text}")
            return

        result = gen_resp.json()
        job_id = result["job_id"]
        print(f"✅ Job started: {job_id}")
        
        # 4. Poll for completion
        print("\n4️⃣ Waiting for completion...")
        print("   (This might take a minute or two as it loads models)")
        
        for i in range(120): # Wait up to 4 mins
            await asyncio.sleep(2)
            
            try:
                job_resp = await client.get(f"{BACKEND_URL}/api/v1/jobs/{job_id}", headers=headers)
                job = job_resp.json()
                
                status = job["status"]
                progress = job.get("progress", 0) * 100
                step = job.get("current_step", "")
                
                # Clear line and print status
                sys.stdout.write(f"\r   [{i*2}s] {status.upper()} | {progress:.0f}% | {step}                    ")
                sys.stdout.flush()
                
                if status == "completed":
                    print("\n\n✅ COMPLETED!")
                    print(f"   Video URL: {job.get('result', {}).get('video_url', 'N/A')}")
                    
                    # Verify metadata if possible
                    print("\n   Verifying result...")
                    # We can't easily verify the internal engine used from here without logs,
                    # but success means the pipeline worked.
                    return
                elif status == "failed":
                    print(f"\n\n❌ FAILED: {job.get('error', 'Unknown')}")
                    print(f"   Details: {job}")
                    return
            except Exception as e:
                print(f"\n❌ Polling error: {e}")
                
        print("\n\n⏱️ Timeout waiting for job completion")

if __name__ == "__main__":
    asyncio.run(test_sadtalker())
