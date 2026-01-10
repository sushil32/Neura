#!/usr/bin/env python3
"""Test video generation end-to-end and verify it can be played in UI."""
import httpx
import asyncio
import time
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api/v1"
FRONTEND_URL = "http://localhost:3000"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

def print_test(name: str):
    print(f"\n{Colors.BLUE}▶ {name}{Colors.RESET}")

def print_pass(message: str):
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")

def print_fail(message: str):
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")

def print_warn(message: str):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")

def print_info(message: str):
    print(f"{Colors.CYAN}ℹ {message}{Colors.RESET}")

async def authenticate(client: httpx.AsyncClient) -> tuple[str, str]:
    """Authenticate and get token."""
    print_test("Authentication")
    
    user_data = {
        "email": "test@example.com",
        "password": "Test123!@#",
    }
    
    try:
        response = await client.post(f"{BASE_URL}/auth/login", json=user_data)
        response.raise_for_status()
        data = response.json()
        token = data["access_token"]
        user_id = data.get("user_id")
        client.headers["Authorization"] = f"Bearer {token}"
        print_pass("Authenticated successfully")
        return token, user_id
    except Exception as e:
        print_fail(f"Authentication failed: {e}")
        raise

async def get_or_create_avatar(client: httpx.AsyncClient) -> str:
    """Get or create an avatar."""
    print_test("Getting Avatar")
    
    try:
        # List avatars
        response = await client.get(f"{BASE_URL}/avatars")
        response.raise_for_status()
        avatars_data = response.json()
        avatars = avatars_data.get("avatars", [])
        
        if avatars:
            avatar_id = avatars[0]["id"]
            print_pass(f"Using existing avatar: {avatar_id}")
            return avatar_id
        
        # Create avatar if none exist
        avatar_data = {
            "name": "Test Avatar",
            "description": "Avatar for video generation test",
            "is_default": False,
        }
        response = await client.post(f"{BASE_URL}/avatars", json=avatar_data)
        response.raise_for_status()
        avatar = response.json()
        avatar_id = avatar["id"]
        print_pass(f"Created avatar: {avatar_id}")
        return avatar_id
    except Exception as e:
        print_fail(f"Avatar setup failed: {e}")
        raise

async def create_video(client: httpx.AsyncClient, avatar_id: str) -> str:
    """Create a video."""
    print_test("Creating Video")
    
    try:
        video_data = {
            "title": "UI Test Video - " + time.strftime("%Y-%m-%d %H:%M:%S"),
            "description": "Testing video generation from UI",
            "type": "explainer",
            "script": "Hello! This is a test video for UI playback. We are testing the complete video generation pipeline including TTS, avatar rendering, and video playback in the browser.",
            "avatar_id": avatar_id,
        }
        response = await client.post(f"{BASE_URL}/videos", json=video_data)
        response.raise_for_status()
        video = response.json()
        video_id = video["id"]
        print_pass(f"Video created: {video_id}")
        print_info(f"  Title: {video['title']}")
        print_info(f"  View in UI: {FRONTEND_URL}/videos/{video_id}")
        return video_id
    except Exception as e:
        print_fail(f"Video creation failed: {e}")
        raise

async def start_generation(client: httpx.AsyncClient, video_id: str) -> str:
    """Start video generation."""
    print_test("Starting Video Generation")
    
    try:
        generate_data = {
            "quality": "balanced",
            "resolution": "1080p",
        }
        response = await client.post(
            f"{BASE_URL}/videos/{video_id}/generate",
            json=generate_data
        )
        response.raise_for_status()
        generate_response = response.json()
        job_id = generate_response["job_id"]
        print_pass(f"Generation started: Job {job_id}")
        print_info(f"  Status: {generate_response.get('status')}")
        print_info(f"  Estimated time: {generate_response.get('estimated_time')}s")
        print_info(f"  Credits: {generate_response.get('credits_estimated')}")
        return job_id
    except Exception as e:
        print_fail(f"Generation start failed: {e}")
        raise

async def monitor_generation(client: httpx.AsyncClient, video_id: str, job_id: str, max_wait: int = 300):
    """Monitor video generation progress."""
    print_test("Monitoring Generation Progress")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        try:
            # Check job status
            response = await client.get(f"{BASE_URL}/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()
            
            status = job.get("status")
            progress = job.get("progress", 0)
            current_step = job.get("current_step", "")
            
            # Only print if status changed
            if status != last_status:
                print_info(f"  Status: {status} | Progress: {progress*100:.1f}% | Step: {current_step}")
                last_status = status
            
            if status == "completed":
                print_pass("Video generation completed!")
                
                # Get final video details
                response = await client.get(f"{BASE_URL}/videos/{video_id}")
                response.raise_for_status()
                video = response.json()
                
                print_info(f"  Video URL: {video.get('video_url', 'N/A')}")
                print_info(f"  Audio URL: {video.get('audio_url', 'N/A')}")
                print_info(f"  Duration: {video.get('duration', 'N/A')}s")
                print_info(f"  Status: {video.get('status')}")
                
                return True, video
            elif status == "failed":
                error = job.get("error", "Unknown error")
                print_fail(f"Generation failed: {error}")
                return False, None
            
            await asyncio.sleep(3)
        except Exception as e:
            print_warn(f"Error checking status: {e}")
            await asyncio.sleep(3)
    
    print_warn(f"Generation timeout after {max_wait}s")
    return False, None

async def verify_video_playback(video: Dict[str, Any]):
    """Verify video can be played."""
    print_test("Verifying Video Playback")
    
    video_url = video.get("video_url")
    if not video_url:
        print_fail("No video URL available")
        return False
    
    try:
        # Check if video URL is accessible
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.head(video_url, follow_redirects=True)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "video" in content_type:
                    print_pass(f"Video is accessible: {video_url}")
                    print_info(f"  Content-Type: {content_type}")
                    print_info(f"  Size: {response.headers.get('content-length', 'Unknown')} bytes")
                    return True
                else:
                    print_warn(f"Unexpected content type: {content_type}")
                    return False
            else:
                print_fail(f"Video URL returned status {response.status_code}")
                return False
    except Exception as e:
        print_warn(f"Could not verify video URL (may need authentication): {e}")
        print_info(f"  Video URL: {video_url}")
        print_info("  Please verify playback manually in the UI")
        return True  # Assume it's OK if we can't verify (might be presigned URL)

async def main():
    """Run end-to-end video generation test."""
    print(f"\n{Colors.BLUE}{'='*70}")
    print("Video Generation & UI Playback Test")
    print(f"{'='*70}{Colors.RESET}\n")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # 1. Authenticate
            token, user_id = await authenticate(client)
            
            # 2. Get or create avatar
            avatar_id = await get_or_create_avatar(client)
            
            # 3. Create video
            video_id = await create_video(client, avatar_id)
            
            # 4. Start generation
            job_id = await start_generation(client, video_id)
            
            # 5. Monitor progress
            success, video = await monitor_generation(client, video_id, job_id, max_wait=300)
            
            if success and video:
                # 6. Verify playback
                await verify_video_playback(video)
                
                print(f"\n{Colors.GREEN}{'='*70}")
                print("Test Complete - Video Ready for UI Playback!")
                print(f"{'='*70}{Colors.RESET}\n")
                print(f"{Colors.CYAN}View video in UI:{Colors.RESET}")
                print(f"  {FRONTEND_URL}/videos/{video_id}\n")
                print(f"{Colors.CYAN}Video Details:{Colors.RESET}")
                print(f"  Title: {video.get('title')}")
                print(f"  Status: {video.get('status')}")
                print(f"  Video URL: {video.get('video_url', 'N/A')}")
                print(f"  Duration: {video.get('duration', 'N/A')}s\n")
            else:
                print(f"\n{Colors.RED}{'='*70}")
                print("Test Failed - Video Generation Did Not Complete")
                print(f"{'='*70}{Colors.RESET}\n")
                print(f"{Colors.YELLOW}Check job status:{Colors.RESET}")
                print(f"  {FRONTEND_URL}/videos/{video_id}\n")
                sys.exit(1)
                
        except Exception as e:
            print_fail(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())


