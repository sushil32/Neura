#!/usr/bin/env python3
"""Test frontend-backend integration end-to-end."""
import httpx
import asyncio
import time
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api/v1"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_test(name: str):
    print(f"\n{Colors.BLUE}▶ Testing: {name}{Colors.RESET}")

def print_pass(message: str):
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")

def print_fail(message: str):
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")

def print_warn(message: str):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")

async def test_auth(client: httpx.AsyncClient) -> tuple[str, str]:
    """Test authentication."""
    print_test("Authentication")
    
    # Register/Login
    user_data = {
        "email": "test@example.com",
        "password": "Test123!@#",
        "name": "Test User",
    }
    
    try:
        response = await client.post(f"{BASE_URL}/auth/register", json=user_data)
        if response.status_code == 201:
            print_pass("User registered")
        elif response.status_code == 409:
            # User exists, try login
            response = await client.post(f"{BASE_URL}/auth/login", json={
                "email": user_data["email"],
                "password": user_data["password"],
            })
            response.raise_for_status()
            print_pass("User logged in")
        else:
            response.raise_for_status()
        
        data = response.json()
        token = data["access_token"]
        user_id = data.get("user_id")
        
        client.headers["Authorization"] = f"Bearer {token}"
        return token, user_id
    except Exception as e:
        print_fail(f"Authentication failed: {e}")
        raise

async def test_user_profile(client: httpx.AsyncClient):
    """Test user profile endpoints."""
    print_test("User Profile")
    
    try:
        # Get profile
        response = await client.get(f"{BASE_URL}/users/me")
        response.raise_for_status()
        profile = response.json()
        print_pass(f"Profile retrieved: {profile.get('email')}")
        
        # Update profile
        response = await client.patch(f"{BASE_URL}/users/me", json={"name": "Updated Name"})
        response.raise_for_status()
        print_pass("Profile updated")
        
        # Get credits history
        response = await client.get(f"{BASE_URL}/users/me/credits")
        response.raise_for_status()
        history = response.json()
        print_pass(f"Credits history retrieved: {history.get('total', 0)} entries")
        
    except Exception as e:
        print_fail(f"User profile test failed: {e}")

async def test_avatars(client: httpx.AsyncClient) -> str:
    """Test avatar endpoints."""
    print_test("Avatars API")
    
    try:
        # List avatars
        response = await client.get(f"{BASE_URL}/avatars")
        response.raise_for_status()
        avatars_data = response.json()
        avatars = avatars_data.get("avatars", [])
        print_pass(f"Avatars listed: {len(avatars)} found")
        
        # Create avatar
        avatar_data = {
            "name": "Test Avatar",
            "description": "Test avatar for integration testing",
            "is_default": False,
        }
        response = await client.post(f"{BASE_URL}/avatars", json=avatar_data)
        response.raise_for_status()
        avatar = response.json()
        avatar_id = avatar["id"]
        print_pass(f"Avatar created: {avatar_id}")
        
        # Get avatar
        response = await client.get(f"{BASE_URL}/avatars/{avatar_id}")
        response.raise_for_status()
        print_pass("Avatar retrieved")
        
        return avatar_id
    except Exception as e:
        print_fail(f"Avatars test failed: {e}")
        return None

async def test_voices(client: httpx.AsyncClient) -> str:
    """Test TTS/Voices API."""
    print_test("Voices API")
    
    try:
        # List voices
        response = await client.get(f"{BASE_URL}/tts/voices")
        response.raise_for_status()
        voices_data = response.json()
        voices = voices_data.get("voices", [])
        print_pass(f"Voices listed: {len(voices)} found")
        
        if len(voices) > 0:
            voice_id = voices[0]["id"]
            print_pass(f"Using existing voice: {voice_id}")
            return voice_id
        else:
            print_warn("No voices available")
            return None
    except Exception as e:
        print_fail(f"Voices test failed: {e}")
        return None

async def test_videos(client: httpx.AsyncClient, avatar_id: str):
    """Test video endpoints."""
    print_test("Videos API")
    
    try:
        # List videos
        response = await client.get(f"{BASE_URL}/videos")
        response.raise_for_status()
        videos_data = response.json()
        # Backend returns a list directly
        videos = videos_data if isinstance(videos_data, list) else videos_data.get("videos", [])
        print_pass(f"Videos listed: {len(videos)} found")
        
        # Create video
        video_data = {
            "title": "Integration Test Video",
            "description": "Testing video creation",
            "type": "explainer",
            "script": "Hello! This is a test video for frontend-backend integration testing.",
            "avatar_id": avatar_id,
        }
        response = await client.post(f"{BASE_URL}/videos", json=video_data)
        response.raise_for_status()
        video = response.json()
        video_id = video["id"]
        print_pass(f"Video created: {video_id}")
        
        # Get video
        response = await client.get(f"{BASE_URL}/videos/{video_id}")
        response.raise_for_status()
        print_pass("Video retrieved")
        
        # Update video
        response = await client.patch(f"{BASE_URL}/videos/{video_id}", json={
            "title": "Updated Test Video",
        })
        response.raise_for_status()
        print_pass("Video updated")
        
        # Start generation (without video_id in body)
        generate_data = {
            "quality": "balanced",
            "resolution": "1080p",
        }
        response = await client.post(f"{BASE_URL}/videos/{video_id}/generate", json=generate_data)
        response.raise_for_status()
        generate_response = response.json()
        job_id = generate_response["job_id"]
        print_pass(f"Video generation started: Job {job_id}")
        
        # Check job status
        response = await client.get(f"{BASE_URL}/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        print_pass(f"Job status: {job.get('status')} ({job.get('progress', 0)*100:.1f}%)")
        
        return video_id, job_id
    except Exception as e:
        print_fail(f"Videos test failed: {e}")
        return None, None

async def test_jobs(client: httpx.AsyncClient):
    """Test jobs API."""
    print_test("Jobs API")
    
    try:
        # List jobs
        response = await client.get(f"{BASE_URL}/jobs")
        response.raise_for_status()
        jobs_data = response.json()
        jobs = jobs_data.get("jobs", [])
        print_pass(f"Jobs listed: {len(jobs)} found")
        
        if jobs:
            # Get a job
            job_id = jobs[0]["id"]
            response = await client.get(f"{BASE_URL}/jobs/{job_id}")
            response.raise_for_status()
            print_pass("Job retrieved")
    except Exception as e:
        print_fail(f"Jobs test failed: {e}")

async def test_live_session(client: httpx.AsyncClient, avatar_id: str):
    """Test live session API."""
    print_test("Live Session API")
    
    try:
        # Start session
        response = await client.post(f"{BASE_URL}/live/start", json={
            "avatar_id": avatar_id,
        })
        response.raise_for_status()
        session = response.json()
        session_id = session["session_id"]
        print_pass(f"Live session started: {session_id}")
        
        # Get status
        response = await client.get(f"{BASE_URL}/live/{session_id}/status")
        response.raise_for_status()
        print_pass("Session status retrieved")
        
        # Stop session
        response = await client.post(f"{BASE_URL}/live/{session_id}/stop")
        response.raise_for_status()
        print_pass("Live session stopped")
    except Exception as e:
        print_fail(f"Live session test failed: {e}")

async def test_llm(client: httpx.AsyncClient):
    """Test LLM API."""
    print_test("LLM API")
    
    try:
        # Generate script
        response = await client.post(f"{BASE_URL}/llm/script/generate", json={
            "topic": "Introduction to AI",
            "type": "explainer",
            "duration": 60,
        })
        response.raise_for_status()
        script_data = response.json()
        print_pass(f"Script generated: {len(script_data.get('script', ''))} characters")
    except Exception as e:
        print_warn(f"LLM test failed (may need LM Studio): {e}")

async def main():
    """Run all integration tests."""
    print(f"\n{Colors.BLUE}{'='*60}")
    print("Frontend-Backend Integration Tests")
    print(f"{'='*60}{Colors.RESET}\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 1. Authentication
            token, user_id = await test_auth(client)
            
            # 2. User Profile
            await test_user_profile(client)
            
            # 3. Avatars
            avatar_id = await test_avatars(client)
            if not avatar_id:
                print_warn("Skipping video tests - no avatar available")
                return
            
            # 4. Voices
            voice_id = await test_voices(client)
            
            # 5. Videos
            video_id, job_id = await test_videos(client, avatar_id)
            
            # 6. Jobs
            await test_jobs(client)
            
            # 7. Live Session
            await test_live_session(client, avatar_id)
            
            # 8. LLM
            await test_llm(client)
            
            print(f"\n{Colors.GREEN}{'='*60}")
            print("All Integration Tests Completed!")
            print(f"{'='*60}{Colors.RESET}\n")
            
        except Exception as e:
            print_fail(f"Test suite failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

