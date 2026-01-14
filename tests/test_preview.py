#!/usr/bin/env python3
"""
Simplified test script to check preview video generation.
Run this after restarting the backend with the new logging.
"""
import asyncio
import httpx

BACKEND_URL = "http://localhost:8000"

# Update these with your test credentials
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test123"

async def test_preview():
    """Test preview generation and show detailed logs."""
    
    print("🔹 Preview Generation Test")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Login
        print("\n1️⃣ Logging in...")
        try:
            login_resp = await client.post(
                f"{BACKEND_URL}/auth/login",
                json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
            )
            login_resp.raise_for_status()
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("✅ Logged in")
        except Exception as e:
            print(f"❌ Login failed: {e}")
            print("\n💡 Update TEST_EMAIL and TEST_PASSWORD in the script")
            return
        
        # Create video
        print("\n2️⃣ Creating video...")
        video_resp = await client.post(
            f"{BACKEND_URL}/videos",
            headers=headers,
            json={
                "title": "Preview Test",
                "script": "Hello! This is a comprehensive test of the preview video generation feature. We are testing if the avatar appears correctly and if the audio is properly synchronized with the lip movements. This script should be truncated to approximately twenty words for the preview generation.",
                "type": "custom"
            }
        )
        video_resp.raise_for_status()
        video = video_resp.json()
        video_id = video["id"]
        print(f"✅ Video created: {video_id}")
        print(f"   Script: {len(video['script'])} chars")
        
        # Generate preview
        print("\n3️⃣ Starting preview generation...")
        gen_resp = await client.post(
            f"{BACKEND_URL}/videos/{video_id}/generate",
            headers=headers,
            json={"quality": "fast", "resolution": "720p", "preview": True}
        )
        gen_resp.raise_for_status()
        result = gen_resp.json()
        job_id = result["job_id"]
        print(f"✅ Job started: {job_id}")
        
        # Poll for completion
        print("\n4️⃣ Waiting for completion...")
        for i in range(60):
            await asyncio.sleep(2)
            
            job_resp = await client.get(f"{BACKEND_URL}/jobs/{job_id}", headers=headers)
            job = job_resp.json()
            
            status = job["status"]
            progress = job.get("progress", 0) * 100
            step = job.get("current_step", "")
            
            print(f"   [{i+1}/60] {status} | {progress:.0f}% | {step}")
            
            if status == "completed":
                print("\n✅ COMPLETED!")
                print(f"   Video URL: {job.get('result', {}).get('video_url', 'N/A')}")
                
                # Get video details
                video_resp = await client.get(f"{BACKEND_URL}/videos/{video_id}", headers=headers)
                video = video_resp.json()
                print(f"   Preview URL: {video.get('preview_url', 'N/A')}")
                print(f"   Audio URL: {video.get('audio_url', 'N/A')}")
                
                if video.get('preview_url'):
                    print("\n✅ Preview URL is set!")
                else:
                    print("\n❌ Preview URL is missing!")
                
                return
            elif status == "failed":
                print(f"\n❌ FAILED: {job.get('error', 'Unknown')}")
                return
        
        print("\n⏱️ Timeout")

if __name__ == "__main__":
    print("\n⚠️  Make sure to:")
    print("   1. Update TEST_EMAIL and TEST_PASSWORD in this script")
    print("   2. Restart the backend to load new logging")
    print("   3. Check backend logs while this runs\n")
    
    input("Press Enter to continue...")
    asyncio.run(test_preview())
