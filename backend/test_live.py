import asyncio
import json
import requests
import sys
import websockets

BASE_URL = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"

# Mock Auth Token (Assuming backend accepts unauth or we mock it)
# Real backend requires auth. Let's see if we can get a token or use a known user.
# For now, let's try to assume we might need to login first.
# But wait, I can just create a session with a user if I had credentials.
# I'll try to cheat: I'll manually insert a token if I know it, or just use a test user.
# Actually, the user "admin@neura.ai" usually exists from seed?
# Let's try to login.

async def run_test():
    print("1. Registering/Authenticating...")
    email = f"test_{int(asyncio.get_event_loop().time())}@neura.ai"
    try:
        # Register new user
        resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json={
            "email": email,
            "password": "password123",
            "name": "Test User"
        })
        if resp.status_code == 201:
            token = resp.json()["access_token"]
            print(f"Registered & Logged in. Token: {token[:10]}...")
        else:
            print(f"Registration failed: {resp.status_code} {resp.text}")
            return
            
    except Exception as e:
        print(f"Auth error: {e}")
        return

    if not token:
        print("No token, exiting.")
        return
    
    headers = {"Authorization": f"Bearer {token}"}

    print("\n2. Starting Live Session...")
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/live/start", json={"avatar_id": None}, headers=headers)
        if resp.status_code != 200:
            print(f"Start failed: {resp.status_code} {resp.text}")
            return
        
        data = resp.json()
        session_id = data["session_id"]
        print(f"Session Created: {session_id}")
        
    except Exception as e:
        print(f"Start error: {e}")
        return

    print("\n3. Connecting WebSocket...")
    ws_url = f"{WS_BASE_URL}/api/v1/live/ws/{session_id}"
    try:
        async with websockets.connect(ws_url) as ws:
            print("Connected.")
            
            # Send Offer
            print("\n4. Sending Mock Offer...")
            offer_msg = {
                "type": "offer",
                "content": "v=0\r\no=- 123 123 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=rtcp-mux\r\n", 
                "metadata": {"type": "offer"}
            }
            await ws.send(json.dumps(offer_msg))
            
            # Wait for Answer
            print("\n5. Waiting for Answer...")
            response = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = json.loads(response)
            
            print(f"Received: {msg['type']}")
            if msg['type'] == 'answer':
                print("SUCCESS: Received SDP Answer!")
                print(f"SDP: {msg['content'][:50]}...")
            elif msg['type'] == 'error':
                print(f"FAILURE: Received Error: {msg['content']}")
            else:
                print(f"Unexpected message: {msg}")

    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
