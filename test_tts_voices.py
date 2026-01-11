#!/usr/bin/env python3
"""Test TTS voice generation end-to-end."""
import requests
import json
import os
import sys
import tempfile
import wave
import time
from datetime import datetime

# Configuration
TTS_SERVICE_URL = os.getenv("TTS_SERVICE_URL", "http://localhost:8001")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/v1")


def test_tts_service_health():
    """Test TTS service health."""
    print("1. Testing TTS service health...")
    try:
        resp = requests.get(f"{TTS_SERVICE_URL}/health", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✓ TTS Service Status: {data.get('status')}")
            print(f"   ✓ Model Loaded: {data.get('model_loaded')}")
            print(f"   ✓ Device: {data.get('device')}")
            return True
        else:
            print(f"   ✗ Health check failed: {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to TTS service. Is it running?")
        print(f"   ✗ Tried: {TTS_SERVICE_URL}")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def test_list_voices():
    """Test listing available voices."""
    print("\n2. Testing list voices...")
    try:
        resp = requests.get(f"{TTS_SERVICE_URL}/voices", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            voices = data.get("voices", [])
            print(f"   ✓ Found {len(voices)} voice(s):")
            for voice in voices:
                gender = voice.get("gender", "unknown")
                vtype = voice.get("type", "unknown")
                print(f"      - {voice['name']} ({voice['id']}) [{gender}, {vtype}]")
            return voices
        else:
            print(f"   ✗ Failed to list voices: {resp.status_code}")
            return []
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []


def test_synthesize_speech(text: str, voice_id: str = "default"):
    """Test speech synthesis."""
    print(f"\n3. Testing speech synthesis with voice '{voice_id}'...")
    print(f"   Text: \"{text}\"")
    
    try:
        start_time = time.time()
        resp = requests.post(
            f"{TTS_SERVICE_URL}/synthesize",
            json={
                "text": text,
                "voice_id": voice_id,
                "language": "en",
                "speed": 1.0,
                "pitch": 1.0,
            },
            timeout=60,  # TTS can take time
        )
        elapsed = time.time() - start_time

        
        if resp.status_code == 200:
            # Get audio data
            audio_data = resp.content
            duration = resp.headers.get("X-Duration", "unknown")
            sample_rate = resp.headers.get("X-Sample-Rate", "unknown")
            
            print(f"   ✓ Audio generated successfully!")
            print(f"   ✓ Time taken: {elapsed:.2f}s")
            print(f"   ✓ Audio size: {len(audio_data)} bytes")
            print(f"   ✓ Duration: {duration} seconds")
            
            # Calculate RTF (Real-Time Factor) - lower is better
            try:
                 dur_val = float(duration)
                 if dur_val > 0:
                     rtf = elapsed / dur_val
                     print(f"   ✓ Real-Time Factor: {rtf:.2f}x (Lower is better)")
            except:
                pass

            print(f"   ✓ Sample rate: {sample_rate} Hz")
            
            # Save to file for verification
            output_file = f"/tmp/neura_tts_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"   ✓ Saved to: {output_file}")
            
            # Verify it's a valid WAV file
            try:
                with wave.open(output_file, 'rb') as wav:
                    channels = wav.getnchannels()
                    framerate = wav.getframerate()
                    frames = wav.getnframes()
                    actual_duration = frames / framerate
                    print(f"   ✓ WAV validation: {channels} channel(s), {framerate}Hz, {actual_duration:.2f}s")
            except Exception as wav_error:
                print(f"   ⚠ WAV validation warning: {wav_error}")
            
            return True, output_file
        elif resp.status_code == 503:
            print("   ⚠ TTS engine not fully initialized (fallback mode may be active)")
            print(f"   Response: {resp.text}")
            return False, None
        else:
            print(f"   ✗ Synthesis failed: {resp.status_code}")
            print(f"   Response: {resp.text}")
            return False, None
            
    except requests.exceptions.Timeout:
        print("   ⚠ Synthesis timed out (this is normal for first run - model loading)")
        return False, None
    except Exception as e:
        print(f"   ✗ Error: {e}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False, None


def test_preview_endpoint(voice_id: str, token: str):
    """Test the preview endpoint used by frontend."""
    print(f"\n5. Testing Frontend Preview Endpoint for voice '{voice_id}'...")
    try:
        start_time = time.time()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Note: frontend uses /tts/voices/{id}/preview, but standard router might be just /voices/{id}/preview
        # if router prefix is /tts. Let's try correct full URL based on backend config.
        # Backend router tts.py usually mounted. If internal URL is used, let's assume /tts prefix.
        
        # URL construction: BACKEND is http://localhost:8000/api/v1
        # Frontend calls: /tts/voices/... 
        # So we test: BACKEND_API_URL + "/tts/voices/{voice_id}/preview"
        
        url = f"{BACKEND_API_URL}/tts/voices/{voice_id}/preview"
        print(f"   GET {url}")
        
        with requests.get(url, headers=headers, stream=True, timeout=10) as r:
            if r.status_code == 200:
                print("   ✓ Status 200 OK")
                size = 0
                for chunk in r.iter_content(chunk_size=8192):
                    size += len(chunk)
                
                elapsed = time.time() - start_time
                print(f"   ✓ Received {size} bytes")
                print(f"   ✓ Time taken: {elapsed:.2f}s")
                if size > 1000:
                    print("   ✓ Audio data received successfully")
                    return True
                else:
                    print("   ⚠ Response seems too small for audio")
                    return False
            else:
                print(f"   ✗ Failed: {r.status_code} {r.text}")
                return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def test_backend_tts_integration():
    """Test backend TTS endpoint integration."""
    print("\n4. Testing Backend TTS integration...")
    
    # First, authenticate
    try:
        login_data = {
            "email": "test@example.com",
            "password": "Test123!@#"
        }
        resp = requests.post(f"{BACKEND_API_URL}/auth/login", json=login_data, timeout=10)
        
        # If login fails, try to register
        if resp.status_code != 200:
            print("   ⚠ Login failed, trying to register...")
            register_data = {
                "email": "test@example.com",
                "password": "Test123!@#",
                "name": "Test User"
            }
            reg_resp = requests.post(f"{BACKEND_API_URL}/auth/register", json=register_data, timeout=10)
            if reg_resp.status_code in [200, 201]:
                print("   ✓ Registration successful, retrying login...")
                resp = requests.post(f"{BACKEND_API_URL}/auth/login", json=login_data, timeout=10)
            else:
                print(f"   ✗ Registration failed: {reg_resp.status_code} {reg_resp.text}")
                return None
        
        if resp.status_code != 200:
            print("   ⚠ Could not authenticate. Skipping backend integration test.")
            return None
            
        token = resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test voices endpoint
        resp = requests.get(f"{BACKEND_API_URL}/tts/voices", headers=headers, timeout=10)
        if resp.status_code == 200:
            voices = resp.json()
            print(f"   ✓ Backend voices endpoint working")
            
            # Now test preview
            if voices and 'voices' in voices and len(voices['voices']) > 0:
                 first_voice = voices['voices'][0]
                 test_preview_endpoint(first_voice['id'], token)
            elif isinstance(voices, list) and len(voices) > 0:
                 test_preview_endpoint(voices[0]['id'], token)
                 
            return True
        else:
            print(f"   ⚠ Backend voices endpoint: {resp.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("   ⚠ Cannot connect to backend API.")
        return None
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return None


def main():
    print("=" * 60)
    print("NEURA TTS Voice Generation Test")
    print("=" * 60)
    print(f"TTS Service URL: {TTS_SERVICE_URL}")
    print(f"Backend API URL: {BACKEND_API_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Test 1: Health check
    health_ok = test_tts_service_health()
    
    if not health_ok:
        print("\n" + "=" * 60)
        print("TTS Service is not available.")
        print("Please ensure the TTS service is running:")
        print("  docker compose up -d tts-service")
        print("  # Or: ./run.sh start")
        print("=" * 60)
        sys.exit(1)
    
    # Test 2: List voices
    voices = test_list_voices()
    
    # Test 3: Synthesize speech
    test_script = "Hello! Welcome to NEURA, where AI comes alive. This is a test of our text-to-speech system."
    success, audio_file = test_synthesize_speech(test_script)
    
    # Test 4: Backend integration
    backend_ok = test_backend_tts_integration()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"TTS Service Health: {'✓ PASS' if health_ok else '✗ FAIL'}")
    print(f"Available Voices: {'✓ PASS (' + str(len(voices)) + ' voices)' if voices else '✗ FAIL'}")
    print(f"Speech Synthesis: {'✓ PASS' if success else '✗ FAIL'}")
    print(f"Backend Integration: {'✓ PASS' if backend_ok else '⚠ SKIP' if backend_ok is None else '✗ FAIL'}")
    
    if audio_file:
        print(f"\nGenerated audio file: {audio_file}")
        print("You can play this file to verify audio quality.")
    
    print("\n" + "=" * 60)
    
    # Exit code
    if health_ok and voices and success:
        print("All TTS tests PASSED!")
        sys.exit(0)
    else:
        print("Some tests failed. Check output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
