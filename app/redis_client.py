import os
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

redis_client = redis.from_url(REDIS_URL) if REDIS_URL else None


async def set_otp_code(phone_number: str, code: str, expire_seconds: int = 300):
    """Store OTP code in Redis with expiration (default 5 minutes)"""
    if redis_client:
        try:
            await redis_client.setex(f"otp:{phone_number}", expire_seconds, code)
            return True
        except Exception as e:
            print(f"Redis set error: {e}")
    return False


async def get_otp_code(phone_number: str) -> str:
    """Get OTP code from Redis"""
    if redis_client:
        try:
            code = await redis_client.get(f"otp:{phone_number}")
            return code.decode() if code else None
        except Exception as e:
            print(f"Redis get error: {e}")
    return None


async def delete_otp_code(phone_number: str):
    """Delete OTP code from Redis"""
    if redis_client:
        try:
            await redis_client.delete(f"otp:{phone_number}")
            return True
        except Exception as e:
            print(f"Redis delete error: {e}")
    return False


async def close_redis():
    """Close Redis connection"""
    if redis_client:
        await redis_client.close()