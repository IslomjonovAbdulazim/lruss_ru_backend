from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import asyncio

from app.database import get_db
from app.models import User, UserProgress
from app.schemas import LeaderboardResponse, LeaderboardUser, CurrentUserRank
from app.redis_client import get_leaderboard_cache, set_leaderboard_cache
from app.dependencies import get_current_user

router = APIRouter()

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


async def calculate_leaderboard(db: AsyncSession) -> Dict[str, Any]:
    """Calculate leaderboard from database and return structured data"""
    
    # Get user total points by summing their progress
    result = await db.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            User.avatar_url,
            func.sum(UserProgress.total_points).label('total_points')
        )
        .join(UserProgress, User.id == UserProgress.user_id)
        .group_by(User.id, User.first_name, User.last_name, User.avatar_url)
        .order_by(func.sum(UserProgress.total_points).desc())
    )
    
    users_data = result.all()
    
    # Build leaderboard with ranks
    leaderboard = []
    rank = 1
    for user_data in users_data:
        leaderboard_user = {
            "user_id": user_data.id,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "avatar_url": user_data.avatar_url,
            "total_points": user_data.total_points or 0,
            "rank": rank
        }
        leaderboard.append(leaderboard_user)
        rank += 1
    
    # Generate timestamps
    now = datetime.utcnow()
    # Calculate next 3-minute interval
    minutes_to_next = 3 - (now.minute % 3)
    next_update = now.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_next)
    
    return {
        "leaderboard": leaderboard,
        "last_updated": now,
        "next_update": next_update,
        "total_users": len(leaderboard)
    }


async def update_leaderboard_cache():
    """Background task to update leaderboard cache"""
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            leaderboard_data = await calculate_leaderboard(db)
            await set_leaderboard_cache(leaderboard_data)
            print(f"Leaderboard updated at {datetime.utcnow()}")
        except Exception as e:
            print(f"Error updating leaderboard: {e}")


def start_leaderboard_scheduler():
    """Start the background scheduler for leaderboard updates"""
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler()
        
        # Schedule to run every 3 minutes
        scheduler.add_job(
            update_leaderboard_cache,
            trigger=IntervalTrigger(minutes=3),
            id='leaderboard_update',
            name='Update Leaderboard Cache',
            replace_existing=True
        )
        
        # Also run immediately on startup
        scheduler.add_job(
            update_leaderboard_cache,
            trigger='date',
            run_date=datetime.now(),
            id='leaderboard_startup',
            name='Initial Leaderboard Update'
        )
        
        scheduler.start()
        print("Leaderboard scheduler started")


def stop_leaderboard_scheduler():
    """Stop the background scheduler"""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        print("Leaderboard scheduler stopped")


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get leaderboard from cache with current user's position"""
    
    # Try to get from cache first
    cached_data = await get_leaderboard_cache()
    
    if not cached_data:
        # Cache miss - calculate and cache
        cached_data = await calculate_leaderboard(db)
        await set_leaderboard_cache(cached_data)
    
    # Find current user's rank and points
    current_user_rank = None
    current_user_points = 0
    
    for user in cached_data["leaderboard"]:
        if user["user_id"] == current_user.id:
            current_user_rank = user["rank"]
            current_user_points = user["total_points"]
            break
    
    # If user not found in leaderboard (no progress yet), they're unranked
    if current_user_rank is None:
        current_user_rank = cached_data["total_users"] + 1
        current_user_points = 0
    
    return LeaderboardResponse(
        leaderboard=[
            LeaderboardUser(**user) for user in cached_data["leaderboard"]
        ],
        current_user=CurrentUserRank(
            rank=current_user_rank,
            total_points=current_user_points
        ),
        last_updated=cached_data["last_updated"],
        next_update=cached_data["next_update"],
        total_users=cached_data["total_users"]
    )