from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from datetime import datetime
from app.database import get_db
from app.models import Pack, GrammarTopic, PackType, User, UserSubscription
from app.schemas import (
    GrammarTopic as GrammarTopicSchema,
    GrammarTopicCreate,
    GrammarTopicUpdate,
    GrammarTopicsResponse
)
from app.dependencies import get_current_user, get_admin_user
from app.redis_client import (
    get_grammar_topics_cache,
    set_grammar_topics_cache,
    invalidate_grammar_topics_cache
)

router = APIRouter()


async def get_grammar_topics_data_from_db(db: AsyncSession) -> Dict[str, Any]:
    """Get all grammar topics data from database - ONE TOPIC PER GRAMMAR PACK"""
    # Get all grammar topics directly
    result = await db.execute(
        select(GrammarTopic)
        .order_by(GrammarTopic.id)
    )
    topics = result.scalars().all()

    # Convert to simple format
    topics_data = []
    for topic in topics:
        topic_dict = {
            "id": topic.id,
            "pack_id": topic.pack_id,
            "video_url": topic.video_url,
            "markdown_text": topic.markdown_text,
            "created_at": topic.created_at,
            "updated_at": topic.updated_at
        }
        topics_data.append(topic_dict)

    return {"topics": topics_data}


async def update_grammar_topics_cache(db: AsyncSession):
    """Update the grammar topics cache with fresh data from database"""
    grammar_topics_data = await get_grammar_topics_data_from_db(db)
    await set_grammar_topics_cache(grammar_topics_data)
    return grammar_topics_data


# GET TOPIC BY PACK ID
@router.get("/topics", response_model=GrammarTopicSchema)
async def get_grammar_topic_by_pack(pack_id: int = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get grammar topic for specific pack"""
    result = await db.execute(
        select(GrammarTopic).where(GrammarTopic.pack_id == pack_id)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Grammar topic not found for this pack")
    return topic


# GET VIDEO URL BY TOPIC ID (PREMIUM REQUIRED)
@router.get("/topics/{topic_id}/video")
async def get_video_url_by_topic_id(topic_id: int, telegram_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    """Get video URL for specific grammar topic by ID (premium subscription required)"""
    # First, find user by telegram_id
    user_result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check for active premium subscription
    now = datetime.utcnow()
    subscription_result = await db.execute(
        select(UserSubscription)
        .where(
            and_(
                UserSubscription.user_id == user.id,
                UserSubscription.is_active == True,
                UserSubscription.end_date > now
            )
        )
        .order_by(UserSubscription.end_date.desc())
    )
    active_subscription = subscription_result.scalars().first()
    
    if not active_subscription:
        raise HTTPException(
            status_code=403, 
            detail="Premium subscription required to access video content"
        )
    
    # User has premium, get the video URL
    video_result = await db.execute(
        select(GrammarTopic.video_url).where(GrammarTopic.id == topic_id)
    )
    video_url = video_result.scalar_one_or_none()
    if not video_url:
        raise HTTPException(status_code=404, detail="Grammar topic not found or no video URL available")
    
    return {"video_url": video_url}


# GRAMMAR TOPIC CRUD
@router.post("/topics", response_model=GrammarTopicSchema, status_code=status.HTTP_201_CREATED)
async def create_grammar_topic(grammar_topic: GrammarTopicCreate, admin_user: User = Depends(get_admin_user),
                               db: AsyncSession = Depends(get_db)):
    """Create a new grammar topic (one per grammar pack)"""
    # Check if pack exists and is a grammar pack
    pack_result = await db.execute(select(Pack).where(Pack.id == grammar_topic.pack_id))
    pack = pack_result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    if pack.type != PackType.GRAMMAR:
        raise HTTPException(status_code=400, detail="Pack is not a grammar pack")

    # Check if topic already exists for this pack
    existing_result = await db.execute(
        select(GrammarTopic).where(GrammarTopic.pack_id == grammar_topic.pack_id)
    )
    existing_topic = existing_result.scalar_one_or_none()
    if existing_topic:
        raise HTTPException(status_code=400, detail="Grammar topic already exists for this pack")

    db_grammar_topic = GrammarTopic(**grammar_topic.dict())
    db.add(db_grammar_topic)
    await db.commit()
    await db.refresh(db_grammar_topic)
    await update_grammar_topics_cache(db)
    return db_grammar_topic


@router.put("/topics/{topic_id}", response_model=GrammarTopicSchema)
async def update_grammar_topic(topic_id: int, topic_update: GrammarTopicUpdate,
                               admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Update a grammar topic"""
    result = await db.execute(select(GrammarTopic).where(GrammarTopic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Grammar topic not found")

    for field, value in topic_update.dict(exclude_unset=True).items():
        setattr(topic, field, value)

    await db.commit()
    await db.refresh(topic)
    await update_grammar_topics_cache(db)
    return topic


@router.delete("/topics/{topic_id}")
async def delete_grammar_topic(topic_id: int, admin_user: User = Depends(get_admin_user),
                               db: AsyncSession = Depends(get_db)):
    """Delete a grammar topic"""
    result = await db.execute(select(GrammarTopic).where(GrammarTopic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Grammar topic not found")

    await db.delete(topic)
    await db.commit()
    await update_grammar_topics_cache(db)
    return {"message": "Grammar topic deleted successfully"}