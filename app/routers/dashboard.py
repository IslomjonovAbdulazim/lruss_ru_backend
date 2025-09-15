from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional

from app.database import get_db
from app.models import User, UserProgress, Module, Lesson, Pack
from app.schemas import (
    DashboardHomeResponse,
    UserInfoDashboard,
    CurrentLessonDashboard,
    LeaderboardPositionDashboard
)
from app.dependencies import get_current_user
from app.redis_client import get_leaderboard_cache

router = APIRouter()


def generate_avatar_initials(first_name: str, last_name: Optional[str] = None) -> str:
    """Generate avatar initials from user's name"""
    initials = first_name[0].upper() if first_name else "U"
    if last_name:
        initials += last_name[0].upper()
    return initials


async def get_user_total_points(user_id: int, db: AsyncSession) -> int:
    """Get user's total points across all packs"""
    result = await db.execute(
        select(func.sum(UserProgress.total_points))
        .where(UserProgress.user_id == user_id)
    )
    total_points = result.scalar()
    return total_points or 0


async def find_current_lesson(user_id: int, db: AsyncSession) -> Optional[dict]:
    """Find the next incomplete lesson for the user"""
    
    # Get all lessons ordered by module and lesson order
    lessons_result = await db.execute(
        select(Lesson, Module.order.label('module_order'))
        .join(Module, Lesson.module_id == Module.id)
        .order_by(Module.order, Lesson.order)
    )
    lessons = lessons_result.all()
    
    # Check each lesson for completion
    for lesson_data in lessons:
        lesson = lesson_data[0]
        
        # Get all packs for this lesson
        packs_result = await db.execute(
            select(Pack).where(Pack.lesson_id == lesson.id)
        )
        packs = packs_result.scalars().all()
        
        if not packs:
            # Lesson has no packs, skip it
            continue
        
        # Check user progress for each pack
        total_packs = len(packs)
        completed_packs = 0
        total_progress = 0
        
        for pack in packs:
            progress_result = await db.execute(
                select(UserProgress).where(
                    UserProgress.user_id == user_id,
                    UserProgress.pack_id == pack.id
                )
            )
            progress = progress_result.scalar_one_or_none()
            
            if progress and progress.best_score > 0:
                completed_packs += 1
                total_progress += progress.best_score
        
        # Calculate lesson progress percentage
        if total_packs > 0:
            progress_percentage = (total_progress / total_packs) if completed_packs > 0 else 0
        else:
            progress_percentage = 0
        
        # If lesson is not 100% complete, this is the current lesson
        if progress_percentage < 100:
            return {
                "id": lesson.id,
                "title": lesson.title,
                "progress_percentage": round(progress_percentage, 1)
            }
    
    # All lessons completed, return the last lesson
    if lessons:
        last_lesson = lessons[-1][0]
        return {
            "id": last_lesson.id,
            "title": last_lesson.title,
            "progress_percentage": 100.0
        }
    
    return None


async def get_user_leaderboard_position(user_id: int, db: AsyncSession) -> dict:
    """Get user's current leaderboard position"""
    
    # Try to get from cache first
    cached_data = await get_leaderboard_cache()
    
    if cached_data:
        # Find user in cached leaderboard
        user_rank = None
        total_users = cached_data.get("total_users", 0)
        
        for user in cached_data.get("leaderboard", []):
            if user["user_id"] == user_id:
                user_rank = user["rank"]
                break
        
        # If user not found in leaderboard (no progress yet)
        if user_rank is None:
            user_rank = total_users + 1
        
        return {
            "current_user_rank": user_rank,
            "total_users": total_users
        }
    
    # Cache miss - calculate from database
    # Get total number of users with points
    total_users_result = await db.execute(
        select(func.count(func.distinct(UserProgress.user_id)))
    )
    total_users = total_users_result.scalar() or 0
    
    # Get users ranked above current user
    user_points = await get_user_total_points(user_id, db)
    
    if user_points > 0:
        # Count users with more points
        higher_ranked_result = await db.execute(
            select(func.count(func.distinct(UserProgress.user_id)))
            .group_by(UserProgress.user_id)
            .having(func.sum(UserProgress.total_points) > user_points)
        )
        higher_ranked_users = len(higher_ranked_result.scalars().all())
        user_rank = higher_ranked_users + 1
    else:
        # User has no points, ranked last
        user_rank = total_users + 1
    
    return {
        "current_user_rank": user_rank,
        "total_users": total_users
    }


@router.get("/home", response_model=DashboardHomeResponse)
async def get_dashboard_home(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get home page dashboard data including user info, current lesson, and leaderboard position"""
    
    # Get user's total points
    total_points = await get_user_total_points(current_user.id, db)
    
    # Generate avatar initials
    avatar = generate_avatar_initials(current_user.first_name, current_user.last_name)
    
    # Build user info
    user_info = UserInfoDashboard(
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        avatar=avatar,
        total_points=total_points
    )
    
    # Find current lesson
    current_lesson_data = await find_current_lesson(current_user.id, db)
    current_lesson = None
    if current_lesson_data:
        current_lesson = CurrentLessonDashboard(**current_lesson_data)
    
    # Get leaderboard position
    leaderboard_data = await get_user_leaderboard_position(current_user.id, db)
    leaderboard_position = LeaderboardPositionDashboard(**leaderboard_data)
    
    return DashboardHomeResponse(
        user_info=user_info,
        current_lesson=current_lesson,
        leaderboard_position=leaderboard_position
    )