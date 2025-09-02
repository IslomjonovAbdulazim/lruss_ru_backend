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
            await redis_client.setex("users", 900, json.dumps(users_data, default=str))  # 15 min
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
            await redis_client.setex("leaderboard", 3600, json.dumps(leaderboard_data, default=str))  # 1 hour
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


async def invalidate_leaderboard_cache():
    """Remove leaderboard data from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete("leaderboard")
            return True
        except Exception as e:
            print(f"Redis leaderboard cache delete error: {e}")
    return False


# Individual entity caching
async def set_modules_cache(modules_data: List[Dict[str, Any]]):
    """Store modules data in Redis cache"""
    if redis_client:
        try:
            await redis_client.setex("modules", 3600, json.dumps(modules_data, default=str))  # 1 hour
            return True
        except Exception as e:
            print(f"Redis modules cache set error: {e}")
    return False


async def get_modules_cache() -> List[Dict[str, Any]]:
    """Get modules data from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get("modules")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis modules cache get error: {e}")
    return None


async def invalidate_modules_cache():
    """Remove modules data from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete("modules")
            return True
        except Exception as e:
            print(f"Redis modules cache delete error: {e}")
    return False


async def set_lessons_cache_by_module(module_id: int, lessons_data: List[Dict[str, Any]]):
    """Store lessons data for specific module in Redis cache"""
    if redis_client:
        try:
            await redis_client.setex(f"lessons:module:{module_id}", 1800, json.dumps(lessons_data, default=str))  # 30 min
            return True
        except Exception as e:
            print(f"Redis lessons cache set error: {e}")
    return False


async def get_lessons_cache_by_module(module_id: int) -> List[Dict[str, Any]]:
    """Get lessons data for specific module from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get(f"lessons:module:{module_id}")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis lessons cache get error: {e}")
    return None


async def invalidate_lessons_cache_by_module(module_id: int):
    """Remove lessons data for specific module from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete(f"lessons:module:{module_id}")
            return True
        except Exception as e:
            print(f"Redis lessons cache delete error: {e}")
    return False


async def set_packs_cache_by_lesson(lesson_id: int, packs_data: List[Dict[str, Any]]):
    """Store packs data for specific lesson in Redis cache"""
    if redis_client:
        try:
            await redis_client.setex(f"packs:lesson:{lesson_id}", 1800, json.dumps(packs_data, default=str))  # 30 min
            return True
        except Exception as e:
            print(f"Redis packs cache set error: {e}")
    return False


async def get_packs_cache_by_lesson(lesson_id: int) -> List[Dict[str, Any]]:
    """Get packs data for specific lesson from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get(f"packs:lesson:{lesson_id}")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis packs cache get error: {e}")
    return None


async def invalidate_packs_cache_by_lesson(lesson_id: int):
    """Remove packs data for specific lesson from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete(f"packs:lesson:{lesson_id}")
            return True
        except Exception as e:
            print(f"Redis packs cache delete error: {e}")
    return False


async def set_words_cache_by_pack(pack_id: int, words_data: List[Dict[str, Any]]):
    """Store words data for specific pack in Redis cache"""
    if redis_client:
        try:
            await redis_client.setex(f"words:pack:{pack_id}", 1800, json.dumps(words_data, default=str))  # 30 min
            return True
        except Exception as e:
            print(f"Redis words cache set error: {e}")
    return False


async def get_words_cache_by_pack(pack_id: int) -> List[Dict[str, Any]]:
    """Get words data for specific pack from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get(f"words:pack:{pack_id}")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis words cache get error: {e}")
    return None


async def invalidate_words_cache_by_pack(pack_id: int):
    """Remove words data for specific pack from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete(f"words:pack:{pack_id}")
            return True
        except Exception as e:
            print(f"Redis words cache delete error: {e}")
    return False


async def set_grammars_cache_by_pack(pack_id: int, grammars_data: List[Dict[str, Any]]):
    """Store grammars data for specific pack in Redis cache"""
    if redis_client:
        try:
            await redis_client.setex(f"grammars:pack:{pack_id}", 1800, json.dumps(grammars_data, default=str))  # 30 min
            return True
        except Exception as e:
            print(f"Redis grammars cache set error: {e}")
    return False


async def get_grammars_cache_by_pack(pack_id: int) -> List[Dict[str, Any]]:
    """Get grammars data for specific pack from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get(f"grammars:pack:{pack_id}")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis grammars cache get error: {e}")
    return None


async def invalidate_grammars_cache_by_pack(pack_id: int):
    """Remove grammars data for specific pack from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete(f"grammars:pack:{pack_id}")
            return True
        except Exception as e:
            print(f"Redis grammars cache delete error: {e}")
    return False


# Subscription caching
async def set_user_subscription_cache(user_id: int, subscription_data: Dict[str, Any]):
    """Store user subscription data in Redis cache"""
    if redis_client:
        try:
            await redis_client.setex(f"subscription:user:{user_id}", 300, json.dumps(subscription_data, default=str))  # 5 min
            return True
        except Exception as e:
            print(f"Redis subscription cache set error: {e}")
    return False


async def get_user_subscription_cache(user_id: int) -> Dict[str, Any]:
    """Get user subscription data from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get(f"subscription:user:{user_id}")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis subscription cache get error: {e}")
    return None


async def invalidate_user_subscription_cache(user_id: int):
    """Remove user subscription data from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete(f"subscription:user:{user_id}")
            return True
        except Exception as e:
            print(f"Redis subscription cache delete error: {e}")
    return False


async def set_subscriptions_list_cache(subscriptions_data: List[Dict[str, Any]]):
    """Store admin subscriptions list in Redis cache"""
    if redis_client:
        try:
            await redis_client.setex("subscriptions:admin:list", 600, json.dumps(subscriptions_data, default=str))  # 10 min
            return True
        except Exception as e:
            print(f"Redis subscriptions list cache set error: {e}")
    return False


async def get_subscriptions_list_cache() -> List[Dict[str, Any]]:
    """Get admin subscriptions list from Redis cache"""
    if redis_client:
        try:
            data = await redis_client.get("subscriptions:admin:list")
            if data:
                return json.loads(data.decode())
        except Exception as e:
            print(f"Redis subscriptions list cache get error: {e}")
    return None


async def invalidate_subscriptions_list_cache():
    """Remove admin subscriptions list from Redis cache"""
    if redis_client:
        try:
            await redis_client.delete("subscriptions:admin:list")
            return True
        except Exception as e:
            print(f"Redis subscriptions list cache delete error: {e}")
    return False


async def close_redis():
    """Close Redis connection"""
    if redis_client:
        await redis_client.close()