import asyncio
import json
import requests
import sys
import os
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription

# Use environment variable for Backend URL, default to localhost for local testing
# But inside container, we might need http://neura-backend:8000
BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
WS_BASE_URL = BASE_URL.replace("http", "ws")

async def run_test():
    print(f"Target Backend: {BASE_URL}")
    print("1. Registering/Authenticating...")
    email = f"test_{int(asyncio.get_event_loop().time())}@neura.ai"
    try:
        # Register new user
        resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json={
            "email": email,
            "password": "password123", # Fixed comma
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
            
            # Generate REAL Offer
            pc = RTCPeerConnection()
            # Must add a transceiver or track to generate media section in SDP
            pc.addTransceiver("audio", direction="sendrecv")
            
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            print("\n4. Sending Real SDP Offer...")
            offer_msg = {
                "type": "offer",
                "content": pc.localDescription.sdp, 
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
                
                # Verify we can set it
                answer = RTCSessionDescription(sdp=msg['content'], type='answer')
                await pc.setRemoteDescription(answer)
                print("Remote Description Set. WebRTC Negotiated!")
                
            elif msg['type'] == 'error':
                print(f"FAILURE: Received Error: {msg['content']}")
            else:
                print(f"Unexpected message: {msg}")
                
            await pc.close()

    except Exception as e:
        print(f"WebSocket/WebRTC error: {e}")


if __name__ == "__main__":
    asyncio.run(run_test())
