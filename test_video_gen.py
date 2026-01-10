#!/usr/bin/env python3
"""Test video generation end-to-end."""
import requests
import json
import time
import sys

API_URL = "http://localhost:8000/api/v1"

def main():
    print("=== Testing Video Generation End-to-End ===\n")

    # Step 1: Register/Login
    print("1. Authenticating...")
    try:
        # Try to register
        register_data = {
            "email": "videotest@example.com",
            "password": "Test123!@#",
            "name": "Video Test User"
        }
        resp = requests.post(f"{API_URL}/auth/register", json=register_data, timeout=10)
        if resp.status_code == 201:
            token = resp.json()["access_token"]
            print("✓ User registered")
        else:
            # Try login
            login_data = {
                "email": "videotest@example.com",
                "password": "Test123!@#"
            }
            resp = requests.post(f"{API_URL}/auth/login", json=login_data, timeout=10)
            if resp.status_code == 200:
                token = resp.json()["access_token"]
                print("✓ User logged in")
            else:
                print(f"✗ Authentication failed: {resp.status_code} - {resp.text}")
                sys.exit(1)
    except Exception as e:
        print(f"✗ Authentication error: {e}")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # Step 1.5: Get or create an avatar
    print("\n1.5. Getting or creating avatar...")
    try:
        resp = requests.get(f"{API_URL}/avatars", headers=headers, timeout=30)
        if resp.status_code == 200:
            avatars_data = resp.json()
            avatars = avatars_data.get("avatars", [])
            if avatars:
                avatar_id = avatars[0]["id"]
                print(f"✓ Using existing avatar: {avatar_id}")
            else:
                # Create a test avatar
                avatar_data = {
                    "name": "Test Avatar",
                    "description": "Test avatar for video generation",
                    "avatar_type": "2d",
                    "config": {}
                }
                resp = requests.post(f"{API_URL}/avatars", json=avatar_data, headers=headers, timeout=30)
                if resp.status_code == 201:
                    avatar = resp.json()
                    avatar_id = avatar["id"]
                    print(f"✓ Created avatar: {avatar_id}")
                else:
                    print(f"✗ Failed to create avatar: {resp.status_code} - {resp.text}")
                    sys.exit(1)
        else:
            print(f"✗ Failed to list avatars: {resp.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ Error getting avatar: {e}")
        sys.exit(1)

    # Step 2: Create a video
    print("\n2. Creating video...")
    video_data = {
        "title": "Test Video Generation",
        "description": "End-to-end test video",
        "type": "explainer",
        "script": "Hello! This is a test video generation. Welcome to NEURA, where AI comes alive. We are testing the complete video generation pipeline.",
        "avatar_id": avatar_id
    }
    try:
        resp = requests.post(f"{API_URL}/videos", json=video_data, headers=headers, timeout=30)
        if resp.status_code == 201:
            video = resp.json()
            video_id = video["id"]
            print(f"✓ Video created: {video_id}")
            print(f"  Title: {video['title']}")
        else:
            print(f"✗ Failed to create video: {resp.status_code} - {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ Error creating video: {e}")
        sys.exit(1)

    # Step 3: Generate the video
    print("\n3. Starting video generation...")
    generate_data = {
        "quality": "balanced",
        "resolution": "1080p"
    }
    try:
        resp = requests.post(
            f"{API_URL}/videos/{video_id}/generate",
            json=generate_data,
            headers=headers,
            timeout=30
        )
        if resp.status_code in [200, 202]:
            job = resp.json()
            job_id = job["job_id"]
            print(f"✓ Video generation started: Job {job_id}")
            print(f"  Status: {job.get('status', 'N/A')}")
            print(f"  Estimated time: {job.get('estimated_time', 'N/A')}s")
            print(f"  Credits estimated: {job.get('credits_estimated', 'N/A')}")
        else:
            print(f"✗ Failed to start generation: {resp.status_code} - {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ Error starting generation: {e}")
        sys.exit(1)

    # Step 4: Monitor job status
    print("\n4. Monitoring job status...")
    max_iterations = 30
    for i in range(max_iterations):
        time.sleep(2)
        try:
            resp = requests.get(f"{API_URL}/jobs/{job_id}", headers=headers, timeout=30)
            if resp.status_code == 200:
                job = resp.json()
                status = job.get("status", "unknown")
                progress = job.get("progress", 0)
                step = job.get("current_step", "N/A")
                print(f"  [{i+1}/{max_iterations}] Status: {status} | Progress: {progress}% | Step: {step}")
                
                if status == "completed":
                    print("\n✓ Video generation completed!")
                    break
                elif status == "failed":
                    error = job.get("error_message", "Unknown error")
                    print(f"\n✗ Video generation failed: {error}")
                    sys.exit(1)
            else:
                print(f"  [{i+1}/{max_iterations}] Failed to get job status: {resp.status_code}")
        except Exception as e:
            print(f"  [{i+1}/{max_iterations}] Error checking status: {e}")

    # Step 5: Get final video details
    print("\n5. Fetching final video details...")
    try:
        resp = requests.get(f"{API_URL}/videos/{video_id}", headers=headers, timeout=30)
        if resp.status_code == 200:
            video = resp.json()
            print("\n✓ Video Details:")
            print(f"  ID: {video.get('id')}")
            print(f"  Title: {video.get('title')}")
            print(f"  Status: {video.get('status', 'N/A')}")
            print(f"  Video URL: {video.get('video_url', 'N/A')}")
            print(f"  Audio URL: {video.get('audio_url', 'N/A')}")
            print(f"  Duration: {video.get('duration', 'N/A')}s")
        else:
            print(f"✗ Failed to get video details: {resp.status_code}")
    except Exception as e:
        print(f"✗ Error fetching video details: {e}")

    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()

