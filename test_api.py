import asyncio
import aiohttp
import json

BASE_URL = "http://localhost:8000"

async def test_api():
    async with aiohttp.ClientSession() as session:
        print("Testing API endpoints...")
        
        print("\n1. Testing root endpoint")
        async with session.get(f"{BASE_URL}/") as response:
            result = await response.json()
            print(f"Status: {response.status}")
            print(f"Response: {result}")
        
        print("\n2. Testing auth login (this will fail without valid code)")
        login_data = {
            "phone_number": "+1234567890",
            "code": "1234"
        }
        async with session.post(f"{BASE_URL}/api/auth/login", json=login_data) as response:
            result = await response.json()
            print(f"Status: {response.status}")
            print(f"Response: {result}")
        
        print("\n✅ Basic API test completed!")

if __name__ == "__main__":
    asyncio.run(test_api())