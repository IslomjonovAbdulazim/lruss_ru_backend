from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.database import get_db
from app.models import User
from app.schemas import UsersResponse
from app.redis_client import get_users_cache, set_users_cache

router = APIRouter()


async def get_users_data_from_db(db: AsyncSession) -> List[Dict[str, Any]]:
    """Get all users data from database"""
    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    
    # Convert to dict format for cache
    users_data = []
    for user in users:
        user_dict = {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "phone_number": user.phone_number,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "avatar_url": user.avatar_url,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
        users_data.append(user_dict)
    
    return users_data


async def update_users_cache(db: AsyncSession):
    """Update the users cache with fresh data from database"""
    users_data = await get_users_data_from_db(db)
    await set_users_cache(users_data)
    return users_data


@router.get("/users", response_model=UsersResponse)
async def get_all_users(db: AsyncSession = Depends(get_db)):
    """Get all users for admin panel from cache, fallback to database if not cached"""
    # Try to get from cache first
    cached_data = await get_users_cache()
    if cached_data:
        return {"users": cached_data}
    
    # If not in cache, get from database and cache it
    users_data = await update_users_cache(db)
    return {"users": users_data}