import os
import json
import redis.asyncio as redis
from dotenv import load_dotenv
from typing import List, Dict, Any

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


async def set_lessons_cache(modules_data: List[Dict[str, Any]]):
    """Store lessons data in Redis cache"""
    if redis_client:
        try:
            await redis_client.set("lessons", json.dumps(modules_data, default=str))
            return True
        except Exception as e:
            print(f"Redis lessons cache set error: {e}")
    return False


async def get_lessons_cache() -> List[Dict[str, Any]]:
    """Get lessons data from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get("lessons")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis lessons cache get error: {e}")
    return None


async def invalidate_lessons_cache():
    """Remove lessons data from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete("lessons")
            return True
        except Exception as e:
            print(f"Redis lessons cache delete error: {e}")
    return False


async def set_quiz_cache(quiz_data: Dict[str, Any]):
    """Store quiz data in Redis cache"""
    if redis_client:
        try:
            await redis_client.set("quiz", json.dumps(quiz_data, default=str))
            return True
        except Exception as e:
            print(f"Redis quiz cache set error: {e}")
    return False


async def get_quiz_cache() -> Dict[str, Any]:
    """Get quiz data from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get("quiz")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis quiz cache get error: {e}")
    return None


async def invalidate_quiz_cache():
    """Remove quiz data from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete("quiz")
            return True
        except Exception as e:
            print(f"Redis quiz cache delete error: {e}")
    return False


async def set_grammar_topics_cache(grammar_topics_data: Dict[str, Any]):
    """Store grammar topics data in Redis cache"""
    if redis_client:
        try:
            await redis_client.set("grammar_topics", json.dumps(grammar_topics_data, default=str))
            return True
        except Exception as e:
            print(f"Redis grammar topics cache set error: {e}")
    return False


async def get_grammar_topics_cache() -> Dict[str, Any]:
    """Get grammar topics data from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get("grammar_topics")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis grammar topics cache get error: {e}")
    return None


async def invalidate_grammar_topics_cache():
    """Remove grammar topics data from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete("grammar_topics")
            return True
        except Exception as e:
            print(f"Redis grammar topics cache delete error: {e}")
    return False


async def set_users_cache(users_data: List[Dict[str, Any]]):
    """Store users data in Redis cache"""
    if redis_client:
        try:
            await redis_client.set("users", json.dumps(users_data, default=str))
            return True
        except Exception as e:
            print(f"Redis users cache set error: {e}")
    return False


async def get_users_cache() -> List[Dict[str, Any]]:
    """Get users data from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get("users")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis users cache get error: {e}")
    return None


async def invalidate_users_cache():
    """Remove users data from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete("users")
            return True
        except Exception as e:
            print(f"Redis users cache delete error: {e}")
    return False


async def set_leaderboard_cache(leaderboard_data: Dict[str, Any]):
    """Store leaderboard data in Redis cache"""
    if redis_client:
        try:
            await redis_client.set("leaderboard", json.dumps(leaderboard_data, default=str))
            return True
        except Exception as e:
            print(f"Redis leaderboard cache set error: {e}")
    return False


async def get_leaderboard_cache() -> Dict[str, Any]:
    """Get leaderboard data from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get("leaderboard")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis leaderboard cache get error: {e}")
    return None


async def close_redis():
    """Close Redis connection"""
    if redis_client:
        await redis_client.close()