from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import User, Pack, UserProgress
from app.schemas import (
    ProgressSubmit, 
    ProgressResponse, 
    UserProgressResponse,
    PackProgress
)
from app.dependencies import get_current_user
from app.redis_client import invalidate_leaderboard_cache

router = APIRouter()


@router.post("/submit", response_model=ProgressResponse)
async def submit_progress(
    progress: ProgressSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit quiz results and get points earned"""
    
    # Validate pack exists
    pack_result = await db.execute(select(Pack).where(Pack.id == progress.pack_id))
    pack = pack_result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    
    # Validate score range
    if progress.score < 0 or progress.score > 100:
        raise HTTPException(status_code=400, detail="Score must be between 0 and 100")
    
    # Get existing progress
    existing_result = await db.execute(
        select(UserProgress).where(
            UserProgress.user_id == current_user.id,
            UserProgress.pack_id == progress.pack_id
        )
    )
    existing_progress = existing_result.scalar_one_or_none()
    
    if existing_progress:
        # User has previous progress
        old_score = existing_progress.best_score
        
        if progress.score > old_score:
            # New score is better - calculate additional points
            points_earned = progress.score - old_score
            existing_progress.best_score = progress.score
            existing_progress.total_points += points_earned
            
            await db.commit()
            await db.refresh(existing_progress)
            
            # Invalidate leaderboard cache since user points changed
            await invalidate_leaderboard_cache()
            
            return ProgressResponse(
                points_earned=points_earned,
                total_points=existing_progress.total_points,
                best_score=existing_progress.best_score
            )
        else:
            # Score not improved
            return ProgressResponse(
                points_earned=0,
                total_points=existing_progress.total_points,
                best_score=existing_progress.best_score
            )
    else:
        # First time playing this pack
        # Award full points if score >= 90%, otherwise award score points
        points_earned = 100 if progress.score >= 90 else progress.score
        
        new_progress = UserProgress(
            user_id=current_user.id,
            pack_id=progress.pack_id,
            best_score=progress.score,
            total_points=points_earned
        )
        
        db.add(new_progress)
        await db.commit()
        await db.refresh(new_progress)
        
        # Invalidate leaderboard cache since new user points added
        await invalidate_leaderboard_cache()
        
        return ProgressResponse(
            points_earned=points_earned,
            total_points=new_progress.total_points,
            best_score=new_progress.best_score
        )


@router.get("/my-progress", response_model=UserProgressResponse)
async def get_user_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all user progress for all packs"""
    
    # Get user progress with pack and lesson info
    result = await db.execute(
        select(UserProgress, Pack.lesson_id)
        .join(Pack, UserProgress.pack_id == Pack.id)
        .where(UserProgress.user_id == current_user.id)
        .order_by(Pack.lesson_id, Pack.id)
    )
    
    progress_data = []
    for progress, lesson_id in result:
        pack_progress = PackProgress(
            pack_id=progress.pack_id,
            lesson_id=lesson_id,
            best_score=progress.best_score,
            total_points=progress.total_points
        )
        progress_data.append(pack_progress)
    
    return UserProgressResponse(progress=progress_data)