from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any
from app.database import get_db
from app.models import Pack, GrammarTopic, PackType, User
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
    """Get all grammar topics data from database"""
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
            "video_url": topic.video_url,
            "markdown_text": topic.markdown_text
        }
        topics_data.append(topic_dict)
    
    return {"topics": topics_data}


async def update_grammar_topics_cache(db: AsyncSession):
    """Update the grammar topics cache with fresh data from database"""
    grammar_topics_data = await get_grammar_topics_data_from_db(db)
    await set_grammar_topics_cache(grammar_topics_data)
    return grammar_topics_data


@router.get("/grammar-topics", response_model=GrammarTopicsResponse)
async def get_grammar_topics(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all grammar topics data from cache, fallback to database if not cached"""
    # Try to get from cache first
    cached_data = await get_grammar_topics_cache()
    if cached_data:
        return cached_data
    
    # If not in cache, get from database and cache it
    grammar_topics_data = await update_grammar_topics_cache(db)
    return grammar_topics_data


@router.post("/grammar-topics", response_model=GrammarTopicSchema, status_code=status.HTTP_201_CREATED)
async def create_grammar_topic(grammar_topic: GrammarTopicCreate, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Create a new grammar topic"""
    # Check if pack exists and is a grammar pack
    pack_result = await db.execute(select(Pack).where(Pack.id == grammar_topic.pack_id))
    pack = pack_result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    if pack.type != PackType.GRAMMAR:
        raise HTTPException(status_code=400, detail="Pack is not a grammar pack")
    
    db_grammar_topic = GrammarTopic(**grammar_topic.dict())
    db.add(db_grammar_topic)
    await db.commit()
    await db.refresh(db_grammar_topic)
    
    # Update cache
    await update_grammar_topics_cache(db)
    
    return db_grammar_topic


@router.get("/grammar-topics/{topic_id}", response_model=GrammarTopicSchema)
async def get_grammar_topic(topic_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get a specific grammar topic by ID"""
    result = await db.execute(select(GrammarTopic).where(GrammarTopic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Grammar topic not found")
    return topic


@router.put("/grammar-topics/{topic_id}", response_model=GrammarTopicSchema)
async def update_grammar_topic(topic_id: int, topic_update: GrammarTopicUpdate, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Update a grammar topic"""
    result = await db.execute(select(GrammarTopic).where(GrammarTopic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Grammar topic not found")
    
    for field, value in topic_update.dict(exclude_unset=True).items():
        setattr(topic, field, value)
    
    await db.commit()
    await db.refresh(topic)
    
    # Update cache
    await update_grammar_topics_cache(db)
    
    return topic


@router.delete("/grammar-topics/{topic_id}")
async def delete_grammar_topic(topic_id: int, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Delete a grammar topic"""
    result = await db.execute(select(GrammarTopic).where(GrammarTopic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Grammar topic not found")
    
    await db.delete(topic)
    await db.commit()
    
    # Update cache
    await update_grammar_topics_cache(db)
    
    return {"message": "Grammar topic deleted successfully"}


@router.get("/grammar-topics/by-pack/{pack_id}", response_model=List[GrammarTopicSchema])
async def get_grammar_topics_by_pack(pack_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all grammar topics for a specific pack"""
    # Check if pack exists and is a grammar pack
    pack_result = await db.execute(select(Pack).where(Pack.id == pack_id))
    pack = pack_result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    if pack.type != PackType.GRAMMAR:
        raise HTTPException(status_code=400, detail="Pack is not a grammar pack")
    
    result = await db.execute(
        select(GrammarTopic)
        .where(GrammarTopic.pack_id == pack_id)
        .order_by(GrammarTopic.id)
    )
    topics = result.scalars().all()
    return topics