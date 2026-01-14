#!/usr/bin/env python3
"""
Diagnostic script for preview video generation using ONLY built-in libraries.
"""
import json
import time
import urllib.request
import urllib.error
import sys

BACKEND_URL = "http://localhost:8000/api/v1"

# Update these with your test credentials
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test123"

def make_request(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    
    if data:
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8")), response.getcode()
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8")), e.code
    except Exception as e:
        return {"error": str(e)}, 500

def test_preview():
    print("🔹 Preview Generation Test (No dependencies)")
    print("=" * 60)
    
    # 1. Login
    print("\n1️⃣ Logging in...")
    login_data, code = make_request(f"{BACKEND_URL}/auth/login", method="POST", 
                                  data={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    
    if code != 200:
        print(f"❌ Login failed ({code}): {login_data}")
        print("\n💡 Update TEST_EMAIL and TEST_PASSWORD in the script")
        return
    
    token = login_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Logged in")
    
    # 2. Create video
    print("\n2️⃣ Creating video...")
    video_data, code = make_request(f"{BACKEND_URL}/videos", method="POST", headers=headers,
                                   data={
                                       "title": "Preview Test Script",
                                       "script": "Hello! This is a diagnostic test for preview generation. We are verifying if audio and avatar movement work correctly.",
                                       "type": "custom"
                                   })
    
    if code != 201:
        print(f"❌ Video creation failed ({code}): {video_data}")
        return
    
    video_id = video_data["id"]
    print(f"✅ Video created: {video_id}")
    
    # 3. Generate preview
    print("\n3️⃣ Generating preview...")
    gen_data, code = make_request(f"{BACKEND_URL}/videos/{video_id}/generate", method="POST", headers=headers,
                                 data={"quality": "fast", "resolution": "720p", "preview": True})
    
    if code != 200:
        print(f"❌ Preview generation failed ({code}): {gen_data}")
        return
    
    job_id = gen_data["job_id"]
    print(f"✅ Job started: {job_id}")
    
    # 4. Poll
    print("\n4️⃣ Waiting for completion...")
    for i in range(120): # 4 minutes max
        time.sleep(2)
        job_data, code = make_request(f"{BACKEND_URL}/jobs/{job_id}", headers=headers)
        
        if code != 200:
            print(f"   [{i+1}] Error checking job: {job_data}")
            continue
            
        status = job_data["status"]
        progress = job_data.get("progress", 0) * 100
        step = job_data.get("current_step", "")
        
        print(f"   [{i+1}] {status} | {progress:.0f}% | {step}")
        
        if status == "completed":
            print("\n✅ COMPLETED!")
            print(f"   Job Result: {json.dumps(job_data.get('result', {}), indent=2)}")
            
            # Final Video check
            v_data, _ = make_request(f"{BACKEND_URL}/videos/{video_id}", headers=headers)
            print(f"   Video Status: {v_data.get('status')}")
            print(f"   Preview URL: {v_data.get('preview_url')}")
            print(f"   Video URL: {v_data.get('video_url')}")
            print(f"   Audio URL: {v_data.get('audio_url')}")
            return
            
        if status == "failed":
            print(f"\n❌ FAILED: {job_data.get('error')}")
            return
            
    print("\n⏱️ Timeout")

if __name__ == "__main__":
    test_preview()
