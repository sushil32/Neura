
import asyncio
import httpx

async def test_services():
    tts_url = "http://localhost:8001"
    avatar_url = "http://localhost:8002"

    print(f"Testing connectivity with:")
    print(f"TTS_SERVICE_URL: {tts_url}")
    print(f"AVATAR_SERVICE_URL: {avatar_url}")
    print("-" * 50)

    async with httpx.AsyncClient(timeout=5.0) as client:
        # 1. Test TTS
        try:
            resp = await client.get(f"{tts_url}/health")
            print(f"TTS Service (8001): {'✅ UP' if resp.status_code == 200 else f'❌ DOWN ({resp.status_code})'}")
        except Exception as e:
            print(f"TTS Service (8001): ❌ ERROR - {e}")

        # 2. Test Avatar
        try:
            resp = await client.get(f"{avatar_url}/health")
            print(f"Avatar Service (8002): {'✅ UP' if resp.status_code == 200 else f'❌ DOWN ({resp.status_code})'}")
        except Exception as e:
            print(f"Avatar Service (8002): ❌ ERROR - {e}")

if __name__ == "__main__":
    asyncio.run(test_services())
