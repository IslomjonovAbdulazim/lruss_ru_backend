from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from pydantic import BaseModel

from app.database import get_db
from app.models import User, UserProgress, Pack, Lesson, Module, Word, Grammar, Translation
from app.schemas import UsersResponse, TokenResponse
from app.redis_client import get_users_cache, set_users_cache, invalidate_users_cache
from app.dependencies import get_admin_user
from app.utils import create_access_token, create_refresh_token

load_dotenv()

router = APIRouter()


class AdminLoginRequest(BaseModel):
    phone_number: str
    password: str


class AdminStatsResponse(BaseModel):
    total_users: int
    total_modules: int
    total_lessons: int
    total_packs: int
    total_words: int
    total_grammar_questions: int
    total_translations: int
    active_users_last_7_days: int


@router.post("/login", response_model=TokenResponse)
async def admin_login(request: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    """Admin login with phone number and password"""
    phone_number = request.phone_number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number

    # Check admin credentials
    admin_phone = os.getenv("ADMIN_PHONE")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_phone or not admin_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin credentials not configured"
        )

    if phone_number != admin_phone or request.password != admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )

    # Check if admin user exists in database
    result = await db.execute(select(User).where(User.phone_number == phone_number))
    admin_user = result.scalar_one_or_none()

    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found in database. Please register via Telegram first."
        )

    # Create tokens
    access_token = create_access_token(
        data={"sub": str(admin_user.id), "phone": admin_user.phone_number, "admin": True})
    refresh_token = create_refresh_token(
        data={"sub": str(admin_user.id), "phone": admin_user.phone_number, "admin": True})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Get comprehensive admin statistics"""
    from datetime import datetime, timedelta

    # Get counts for all entities
    users_count = await db.scalar(select(func.count(User.id)))
    modules_count = await db.scalar(select(func.count(Module.id)))
    lessons_count = await db.scalar(select(func.count(Lesson.id)))
    packs_count = await db.scalar(select(func.count(Pack.id)))
    words_count = await db.scalar(select(func.count(Word.id)))
    grammar_count = await db.scalar(select(func.count(Grammar.id)))
    translations_count = await db.scalar(select(func.count(Translation.id)))

    # Active users in last 7 days (users with progress entries)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    active_users = await db.scalar(
        select(func.count(func.distinct(UserProgress.user_id)))
        .where(UserProgress.updated_at >= seven_days_ago)
    )

    return AdminStatsResponse(
        total_users=users_count or 0,
        total_modules=modules_count or 0,
        total_lessons=lessons_count or 0,
        total_packs=packs_count or 0,
        total_words=words_count or 0,
        total_grammar_questions=grammar_count or 0,
        total_translations=translations_count or 0,
        active_users_last_7_days=active_users or 0
    )


@router.get("/users", response_model=UsersResponse)
async def get_users(admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Get all users from cache, fallback to database if not cached"""
    # Try to get from cache first
    cached_data = await get_users_cache()
    if cached_data:
        return {"users": cached_data}

    # If not in cache, get from database and cache it
    users_data = await update_users_cache(db)
    return {"users": users_data}


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