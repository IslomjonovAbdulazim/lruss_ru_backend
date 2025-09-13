from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.database import get_db
from app.models import Module, Lesson, Pack, PackType, User, Word, Grammar, GrammarTopic, UserProgress
from app.schemas import (
    Module as ModuleSchema, ModuleCreate, ModuleUpdate,
    Lesson as LessonSchema, LessonCreate, LessonUpdate,
    Pack as PackSchema, PackCreate, PackUpdate,
    LessonsResponse,
    StudentContentResponse, ModuleWithProgress, LessonWithProgress,
    LessonPacksResponse, PackWithProgress, PackUserProgress,
    PackWordsResponse, WordSimple, PackWordsUserProgress,
    PackGrammarResponse, GrammarQuestion, GrammarTopicSimple, PackGrammarUserProgress
)
from app.dependencies import get_current_user, get_admin_user
from app.redis_client import (
    get_lessons_cache, set_lessons_cache, invalidate_lessons_cache,
    get_modules_cache, set_modules_cache, invalidate_modules_cache,
    get_lessons_cache_by_module, set_lessons_cache_by_module, invalidate_lessons_cache_by_module,
    get_packs_cache_by_lesson, set_packs_cache_by_lesson, invalidate_packs_cache_by_lesson
)

router = APIRouter()


@router.get("/student-content", response_model=StudentContentResponse)
async def get_student_content_with_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get modules with lessons and user progress - simple and efficient"""
    
    # Get all modules with lessons ordered properly
    modules_result = await db.execute(
        select(Module)
        .options(
            selectinload(Module.lessons)
            .selectinload(Lesson.packs)
        )
        .order_by(Module.order)
    )
    modules = modules_result.scalars().all()
    
    # Get user progress for all packs
    user_progress_result = await db.execute(
        select(UserProgress)
        .where(UserProgress.user_id == current_user.id)
    )
    user_progress_list = user_progress_result.scalars().all()
    
    # Create progress lookup: pack_id -> best_score
    progress_lookup = {progress.pack_id: progress.best_score for progress in user_progress_list}
    
    # Build response
    modules_with_progress = []
    total_lessons = 0
    
    for module in modules:
        lessons_with_progress = []
        module_total_score = 0
        module_total_packs = 0
        
        # Sort lessons by order
        sorted_lessons = sorted(module.lessons, key=lambda l: l.order)
        
        for lesson in sorted_lessons:
            total_lessons += 1
            lesson_total_score = 0
            lesson_completed_packs = 0
            lesson_total_packs = len(lesson.packs)
            
            # Calculate lesson progress
            for pack in lesson.packs:
                if pack.id in progress_lookup:
                    lesson_total_score += progress_lookup[pack.id]
                    lesson_completed_packs += 1
            
            # Lesson percentage
            lesson_percentage = (lesson_total_score / (lesson_total_packs * 100)) * 100 if lesson_total_packs > 0 else 0.0
            
            lessons_with_progress.append(LessonWithProgress(
                id=lesson.id,
                title=lesson.title,
                description=lesson.description,
                module_id=lesson.module_id,
                order=lesson.order,
                progress_percentage=round(lesson_percentage, 1),
                total_packs=lesson_total_packs,
                completed_packs=lesson_completed_packs,
                created_at=lesson.created_at,
                updated_at=lesson.updated_at
            ))
            
            # Add to module totals
            module_total_score += lesson_total_score
            module_total_packs += lesson_total_packs
        
        # Module percentage
        module_percentage = (module_total_score / (module_total_packs * 100)) * 100 if module_total_packs > 0 else 0.0
        completed_lessons = len([l for l in lessons_with_progress if l.completed_packs == l.total_packs and l.total_packs > 0])
        
        modules_with_progress.append(ModuleWithProgress(
            id=module.id,
            title=module.title,
            order=module.order,
            progress_percentage=round(module_percentage, 1),
            total_lessons=len(lessons_with_progress),
            completed_lessons=completed_lessons,
            lessons=lessons_with_progress,
            created_at=module.created_at,
            updated_at=module.updated_at
        ))
    
    return StudentContentResponse(
        modules=modules_with_progress,
        total_modules=len(modules),
        total_lessons=total_lessons,
        overall_progress_percentage=0.0  # Simplified - can calculate if needed
    )


@router.get("/lesson/{lesson_id}/packs", response_model=LessonPacksResponse)
async def get_lesson_packs_with_progress(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all packs for a lesson with user progress"""
    
    # Get lesson with packs
    lesson_result = await db.execute(
        select(Lesson)
        .options(selectinload(Lesson.packs))
        .where(Lesson.id == lesson_id)
    )
    lesson = lesson_result.scalar_one_or_none()
    
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    # Get user progress for all packs in this lesson
    user_progress_result = await db.execute(
        select(UserProgress)
        .join(Pack, UserProgress.pack_id == Pack.id)
        .where(Pack.lesson_id == lesson_id, UserProgress.user_id == current_user.id)
    )
    user_progress_list = user_progress_result.scalars().all()
    
    # Create progress lookup: pack_id -> progress
    progress_lookup = {progress.pack_id: progress for progress in user_progress_list}
    
    # Build packs with progress
    packs_with_progress = []
    total_score = 0
    completed_packs = 0
    
    # Sort packs by order (assuming they have an order field, if not use id)
    sorted_packs = sorted(lesson.packs, key=lambda p: getattr(p, 'order', p.id))
    
    for pack in sorted_packs:
        # Get word count for word packs
        if pack.type == PackType.WORD:
            word_count = await db.scalar(
                select(func.count(Word.id)).where(Word.pack_id == pack.id)
            )
        else:
            word_count = 0
        
        # Get user progress for this pack
        if pack.id in progress_lookup:
            progress = progress_lookup[pack.id]
            user_progress = PackUserProgress(
                best_score=progress.best_score,
                total_points=progress.total_points,
                completed=True
            )
            total_score += progress.best_score
            completed_packs += 1
        else:
            user_progress = PackUserProgress(
                best_score=0,
                total_points=0,
                completed=False
            )
        
        pack_with_progress = PackWithProgress(
            id=pack.id,
            title=pack.title,
            type=pack.type,
            order=getattr(pack, 'order', 0),
            word_count=word_count,
            user_progress=user_progress,
            created_at=pack.created_at,
            updated_at=pack.updated_at
        )
        packs_with_progress.append(pack_with_progress)
    
    # Calculate lesson progress percentage
    total_packs = len(packs_with_progress)
    lesson_progress_percentage = (total_score / (total_packs * 100)) * 100 if total_packs > 0 else 0.0
    
    return LessonPacksResponse(
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        packs=packs_with_progress,
        total_packs=total_packs,
        completed_packs=completed_packs,
        lesson_progress_percentage=round(lesson_progress_percentage, 1)
    )


@router.get("/pack/{pack_id}/words", response_model=PackWordsResponse)
async def get_pack_words(
    pack_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all words for a word pack"""
    
    # Get pack with lesson info
    pack_result = await db.execute(
        select(Pack, Lesson.title.label('lesson_title'))
        .join(Lesson, Pack.lesson_id == Lesson.id)
        .where(Pack.id == pack_id)
    )
    pack_data = pack_result.first()
    
    if not pack_data:
        raise HTTPException(status_code=404, detail="Pack not found")
    
    pack, lesson_title = pack_data
    
    # Check if it's a word pack
    if pack.type != PackType.WORD:
        raise HTTPException(
            status_code=400, 
            detail="This endpoint only works for word packs"
        )
    
    # Get all words in this pack
    words_result = await db.execute(
        select(Word)
        .where(Word.pack_id == pack_id)
        .order_by(Word.id)
    )
    words = words_result.scalars().all()
    
    # Get user progress for this pack
    user_progress_result = await db.execute(
        select(UserProgress)
        .where(
            UserProgress.pack_id == pack_id,
            UserProgress.user_id == current_user.id
        )
    )
    user_progress = user_progress_result.scalar_one_or_none()
    
    # Build user progress object
    if user_progress:
        progress_data = PackWordsUserProgress(
            best_score=user_progress.best_score,
            total_points=user_progress.total_points,
            completed=True,
            last_attempt=user_progress.updated_at
        )
    else:
        progress_data = PackWordsUserProgress(
            best_score=0,
            total_points=0,
            completed=False,
            last_attempt=None
        )
    
    # Convert words to simple format
    word_list = [
        WordSimple(
            id=word.id,
            ru_text=word.ru_text,
            uz_text=word.uz_text,
            audio_url=word.audio_url
        )
        for word in words
    ]
    
    return PackWordsResponse(
        pack_id=pack.id,
        pack_title=pack.title,
        pack_type=pack.type.value,
        lesson_title=lesson_title,
        words=word_list,
        total_words=len(word_list),
        user_progress=progress_data
    )


@router.get("/pack/{pack_id}/grammar", response_model=PackGrammarResponse)
async def get_pack_grammar(
    pack_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all grammar questions and topics for a grammar pack"""
    
    # Get pack with lesson info
    pack_result = await db.execute(
        select(Pack, Lesson.title.label('lesson_title'))
        .join(Lesson, Pack.lesson_id == Lesson.id)
        .where(Pack.id == pack_id)
    )
    pack_data = pack_result.first()
    
    if not pack_data:
        raise HTTPException(status_code=404, detail="Pack not found")
    
    pack, lesson_title = pack_data
    
    # Check if it's a grammar pack
    if pack.type != PackType.GRAMMAR:
        raise HTTPException(
            status_code=400, 
            detail="This endpoint only works for grammar packs"
        )
    
    # Get all grammar questions in this pack
    grammar_result = await db.execute(
        select(Grammar)
        .where(Grammar.pack_id == pack_id)
        .order_by(Grammar.id)
    )
    grammar_questions = grammar_result.scalars().all()
    
    # Get all grammar topics in this pack
    topics_result = await db.execute(
        select(GrammarTopic)
        .where(GrammarTopic.pack_id == pack_id)
        .order_by(GrammarTopic.id)
    )
    grammar_topics = topics_result.scalars().all()
    
    # Get user progress for this pack
    user_progress_result = await db.execute(
        select(UserProgress)
        .where(
            UserProgress.pack_id == pack_id,
            UserProgress.user_id == current_user.id
        )
    )
    user_progress = user_progress_result.scalar_one_or_none()
    
    # Build user progress object
    if user_progress:
        progress_data = PackGrammarUserProgress(
            best_score=user_progress.best_score,
            total_points=user_progress.total_points,
            completed=True,
            last_attempt=user_progress.updated_at
        )
    else:
        progress_data = PackGrammarUserProgress(
            best_score=0,
            total_points=0,
            completed=False,
            last_attempt=None
        )
    
    # Convert grammar questions to simple format
    import json
    question_list = []
    for grammar in grammar_questions:
        # Parse options JSON if it exists
        options = None
        if grammar.options:
            try:
                options = json.loads(grammar.options)
            except json.JSONDecodeError:
                options = None
        
        question_list.append(GrammarQuestion(
            id=grammar.id,
            type=grammar.type,
            question_text=grammar.question_text,
            options=options,
            correct_option=grammar.correct_option,
            sentence=grammar.sentence
        ))
    
    # Convert grammar topics to simple format
    topic_list = [
        GrammarTopicSimple(
            id=topic.id,
            video_url=topic.video_url,
            markdown_text=topic.markdown_text
        )
        for topic in grammar_topics
    ]
    
    return PackGrammarResponse(
        pack_id=pack.id,
        pack_title=pack.title,
        pack_type=pack.type.value,
        lesson_title=lesson_title,
        grammar_questions=question_list,
        grammar_topics=topic_list,
        total_questions=len(question_list),
        total_topics=len(topic_list),
        user_progress=progress_data
    )





# MODULE CRUD
@router.get("/modules", response_model=List[ModuleSchema])
async def get_modules(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all modules from cache"""
    # Try cache first
    cached_data = await get_modules_cache()
    if cached_data:
        return cached_data
    
    # Get from database and cache
    result = await db.execute(select(Module).order_by(Module.order))
    modules = result.scalars().all()
    
    # Convert to dict for caching
    modules_data = [
        {
            "id": module.id,
            "title": module.title,
            "order": module.order,
            "created_at": module.created_at,
            "updated_at": module.updated_at
        }
        for module in modules
    ]
    
    await set_modules_cache(modules_data)
    return modules_data


@router.get("/modules/{module_id}", response_model=ModuleSchema)
async def get_module(module_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get a specific module"""
    result = await db.execute(
        select(Module)
        .options(selectinload(Module.lessons).selectinload(Lesson.packs))
        .where(Module.id == module_id)
    )
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


@router.post("/modules", response_model=ModuleSchema, status_code=status.HTTP_201_CREATED)
async def create_module(module: ModuleCreate, admin_user: User = Depends(get_admin_user),
                        db: AsyncSession = Depends(get_db)):
    """Create a new module"""
    db_module = Module(**module.dict())
    db.add(db_module)
    await db.commit()
    await db.refresh(db_module)
    await invalidate_modules_cache()
    
    # Reload with lessons for response
    result = await db.execute(
        select(Module)
        .options(selectinload(Module.lessons).selectinload(Lesson.packs))
        .where(Module.id == db_module.id)
    )
    return result.scalar_one()


@router.put("/modules/{module_id}", response_model=ModuleSchema)
async def update_module(module_id: int, module_update: ModuleUpdate, admin_user: User = Depends(get_admin_user),
                        db: AsyncSession = Depends(get_db)):
    """Update a module"""
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    for field, value in module_update.dict(exclude_unset=True).items():
        setattr(module, field, value)

    await db.commit()
    await db.refresh(module)
    await invalidate_modules_cache()
    
    # Reload with lessons for response
    result = await db.execute(
        select(Module)
        .options(selectinload(Module.lessons).selectinload(Lesson.packs))
        .where(Module.id == module_id)
    )
    return result.scalar_one()


@router.delete("/modules/{module_id}")
async def delete_module(module_id: int, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Delete a module (only if it has no lessons)"""
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    # Check if module has lessons
    lesson_count = await db.scalar(
        select(func.count(Lesson.id)).where(Lesson.module_id == module_id)
    )
    if lesson_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete module: it contains {lesson_count} lesson(s). Delete all lessons first."
        )

    await db.delete(module)
    await db.commit()
    await invalidate_modules_cache()
    return {"message": "Module deleted successfully"}


# LESSON CRUD
@router.get("/lessons", response_model=List[LessonSchema])
async def get_lessons_by_module(module_id: Optional[int] = Query(None), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all lessons, optionally filtered by module_id"""
    # If module_id specified, try cache first
    if module_id:
        cached_data = await get_lessons_cache_by_module(module_id)
        if cached_data:
            return cached_data
    
    query = select(Lesson).order_by(Lesson.order)
    if module_id:
        query = query.where(Lesson.module_id == module_id)
    
    result = await db.execute(query)
    lessons = result.scalars().all()
    
    # Convert to dict for caching
    lessons_data = [
        {
            "id": lesson.id,
            "title": lesson.title,
            "description": lesson.description,
            "module_id": lesson.module_id,
            "order": lesson.order,
            "created_at": lesson.created_at,
            "updated_at": lesson.updated_at
        }
        for lesson in lessons
    ]
    
    # Cache if filtered by module_id
    if module_id:
        await set_lessons_cache_by_module(module_id, lessons_data)
    
    return lessons_data


@router.get("/lessons/{lesson_id}", response_model=LessonSchema)
async def get_lesson(lesson_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get a specific lesson"""
    result = await db.execute(
        select(Lesson)
        .options(selectinload(Lesson.packs))
        .where(Lesson.id == lesson_id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


@router.post("/lessons", response_model=LessonSchema, status_code=status.HTTP_201_CREATED)
async def create_lesson(lesson: LessonCreate, admin_user: User = Depends(get_admin_user),
                        db: AsyncSession = Depends(get_db)):
    """Create a new lesson"""
    # Check if module exists
    result = await db.execute(select(Module).where(Module.id == lesson.module_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Module not found")

    db_lesson = Lesson(**lesson.dict())
    db.add(db_lesson)
    await db.commit()
    await db.refresh(db_lesson)
    await invalidate_lessons_cache_by_module(lesson.module_id)
    await invalidate_modules_cache()
    
    # Reload with packs for response
    result = await db.execute(
        select(Lesson)
        .options(selectinload(Lesson.packs))
        .where(Lesson.id == db_lesson.id)
    )
    return result.scalar_one()


@router.put("/lessons/{lesson_id}", response_model=LessonSchema)
async def update_lesson(lesson_id: int, lesson_update: LessonUpdate, admin_user: User = Depends(get_admin_user),
                        db: AsyncSession = Depends(get_db)):
    """Update a lesson"""
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    for field, value in lesson_update.dict(exclude_unset=True).items():
        setattr(lesson, field, value)

    await db.commit()
    await db.refresh(lesson)
    await invalidate_lessons_cache_by_module(lesson.module_id)
    await invalidate_modules_cache()
    
    # Reload with packs for response
    result = await db.execute(
        select(Lesson)
        .options(selectinload(Lesson.packs))
        .where(Lesson.id == lesson_id)
    )
    return result.scalar_one()


@router.delete("/lessons/{lesson_id}")
async def delete_lesson(lesson_id: int, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Delete a lesson (only if it has no packs)"""
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    # Check if lesson has packs
    pack_count = await db.scalar(
        select(func.count(Pack.id)).where(Pack.lesson_id == lesson_id)
    )
    if pack_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete lesson: it contains {pack_count} pack(s). Delete all packs first."
        )

    await db.delete(lesson)
    await db.commit()
    await invalidate_lessons_cache_by_module(lesson.module_id)
    await invalidate_modules_cache()
    return {"message": "Lesson deleted successfully"}


# PACK CRUD
@router.get("/packs", response_model=List[PackSchema])
async def get_packs(lesson_id: Optional[int] = Query(None), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all packs, optionally filtered by lesson_id"""
    # If lesson_id specified, try cache first
    if lesson_id:
        cached_data = await get_packs_cache_by_lesson(lesson_id)
        if cached_data:
            return cached_data
    
    query = select(Pack).order_by(Pack.id)
    if lesson_id:
        query = query.where(Pack.lesson_id == lesson_id)
    
    result = await db.execute(query)
    packs = result.scalars().all()
    
    # Convert to dict for caching with dynamic word count
    packs_data = []
    for pack in packs:
        # Count words dynamically for word packs, return 0 for grammar packs
        if pack.type == PackType.WORD:
            word_count = await db.scalar(
                select(func.count(Word.id)).where(Word.pack_id == pack.id)
            )
        else:
            word_count = 0
            
        packs_data.append({
            "id": pack.id,
            "title": pack.title,
            "lesson_id": pack.lesson_id,
            "type": pack.type.value,
            "word_count": word_count,
            "created_at": pack.created_at,
            "updated_at": pack.updated_at
        })
    
    # Cache if filtered by lesson_id
    if lesson_id:
        await set_packs_cache_by_lesson(lesson_id, packs_data)
    
    return packs_data


@router.get("/packs/{pack_id}", response_model=PackSchema)
async def get_pack(pack_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get a specific pack with dynamic word count"""
    result = await db.execute(select(Pack).where(Pack.id == pack_id))
    pack = result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    
    # Count words dynamically for word packs, return 0 for grammar packs
    if pack.type == PackType.WORD:
        word_count = await db.scalar(
            select(func.count(Word.id)).where(Word.pack_id == pack_id)
        )
    else:
        word_count = 0
    
    # Return pack with updated word count
    return {
        "id": pack.id,
        "title": pack.title,
        "lesson_id": pack.lesson_id,
        "type": pack.type.value,
        "word_count": word_count,
        "created_at": pack.created_at,
        "updated_at": pack.updated_at
    }


@router.post("/packs", response_model=PackSchema, status_code=status.HTTP_201_CREATED)
async def create_pack(pack: PackCreate, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Create a new pack"""
    # Check if lesson exists
    result = await db.execute(select(Lesson).where(Lesson.id == pack.lesson_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Lesson not found")

    # Convert string type to enum
    pack_type = PackType.GRAMMAR if pack.type == "grammar" else PackType.WORD

    db_pack = Pack(
        title=pack.title,
        lesson_id=pack.lesson_id,
        type=pack_type,
        word_count=pack.word_count
    )
    db.add(db_pack)
    await db.commit()
    await db.refresh(db_pack)
    
    # Get lesson to invalidate its module cache
    lesson_result = await db.execute(select(Lesson).where(Lesson.id == pack.lesson_id))
    lesson = lesson_result.scalar_one()
    
    await invalidate_packs_cache_by_lesson(pack.lesson_id)
    await invalidate_lessons_cache_by_module(lesson.module_id)
    return db_pack


@router.put("/packs/{pack_id}", response_model=PackSchema)
async def update_pack(pack_id: int, pack_update: PackUpdate, admin_user: User = Depends(get_admin_user),
                      db: AsyncSession = Depends(get_db)):
    """Update a pack"""
    result = await db.execute(select(Pack).where(Pack.id == pack_id))
    pack = result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")

    update_data = pack_update.dict(exclude_unset=True)

    # Convert string type to enum if provided
    if "type" in update_data:
        update_data["type"] = PackType.GRAMMAR if update_data["type"] == "grammar" else PackType.WORD

    for field, value in update_data.items():
        setattr(pack, field, value)

    await db.commit()
    await db.refresh(pack)
    
    # Get lesson to invalidate its module cache
    lesson_result = await db.execute(select(Lesson).where(Lesson.id == pack.lesson_id))
    lesson = lesson_result.scalar_one()
    
    await invalidate_packs_cache_by_lesson(pack.lesson_id)
    await invalidate_lessons_cache_by_module(lesson.module_id)
    return pack


@router.delete("/packs/{pack_id}")
async def delete_pack(pack_id: int, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Delete a pack (only if it has no content)"""
    result = await db.execute(select(Pack).where(Pack.id == pack_id))
    pack = result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")

    # Check if pack has content based on its type
    if pack.type == PackType.WORD:
        word_count = await db.scalar(
            select(func.count(Word.id)).where(Word.pack_id == pack_id)
        )
        if word_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete word pack: it contains {word_count} word(s). Delete all words first."
            )
    elif pack.type == PackType.GRAMMAR:
        grammar_count = await db.scalar(
            select(func.count(Grammar.id)).where(Grammar.pack_id == pack_id)
        )
        grammar_topic_count = await db.scalar(
            select(func.count(GrammarTopic.id)).where(GrammarTopic.pack_id == pack_id)
        )
        total_content = grammar_count + grammar_topic_count
        if total_content > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete grammar pack: it contains {grammar_count} grammar question(s) and {grammar_topic_count} grammar topic(s). Delete all content first."
            )

    # Get lesson info before deleting pack
    lesson_result = await db.execute(select(Lesson).where(Lesson.id == pack.lesson_id))
    lesson = lesson_result.scalar_one()
    
    await db.delete(pack)
    await db.commit()
    
    try:
        await invalidate_packs_cache_by_lesson(pack.lesson_id)
        await invalidate_lessons_cache_by_module(lesson.module_id)
    except Exception as e:
        print(f"Cache invalidation warning: {e}")
        
    return {"message": "Pack deleted successfully"}