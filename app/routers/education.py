from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List
from app.database import get_db
from app.models import Module, Lesson, Pack, PackType
from app.schemas import (
    Module as ModuleSchema, ModuleCreate, ModuleUpdate,
    Lesson as LessonSchema, LessonCreate, LessonUpdate,
    Pack as PackSchema, PackCreate, PackUpdate,
    LessonsResponse
)
from app.redis_client import get_lessons_cache, set_lessons_cache, invalidate_lessons_cache

router = APIRouter()


async def get_modules_from_db(db: AsyncSession) -> List[dict]:
    """Get all modules with lessons and packs from database"""
    result = await db.execute(
        select(Module)
        .options(
            selectinload(Module.lessons).selectinload(Lesson.packs)
        )
        .order_by(Module.id)
    )
    modules = result.scalars().all()
    
    modules_data = []
    for module in modules:
        module_dict = {
            "id": module.id,
            "title": module.title,
            "created_at": module.created_at,
            "updated_at": module.updated_at,
            "lessons": []
        }
        
        for lesson in module.lessons:
            lesson_dict = {
                "id": lesson.id,
                "title": lesson.title,
                "description": lesson.description,
                "module_id": lesson.module_id,
                "created_at": lesson.created_at,
                "updated_at": lesson.updated_at,
                "packs": []
            }
            
            for pack in lesson.packs:
                pack_dict = {
                    "id": pack.id,
                    "title": pack.title,
                    "lesson_id": pack.lesson_id,
                    "type": pack.type.value,
                    "word_count": pack.word_count,
                    "created_at": pack.created_at,
                    "updated_at": pack.updated_at
                }
                lesson_dict["packs"].append(pack_dict)
            
            module_dict["lessons"].append(lesson_dict)
        
        modules_data.append(module_dict)
    
    return modules_data


async def update_cache(db: AsyncSession):
    """Update the lessons cache with fresh data from database"""
    modules_data = await get_modules_from_db(db)
    await set_lessons_cache(modules_data)
    return modules_data


@router.get("/lessons", response_model=LessonsResponse)
async def get_lessons(db: AsyncSession = Depends(get_db)):
    """Get all lessons data from cache, fallback to database if not cached"""
    # Try to get from cache first
    cached_data = await get_lessons_cache()
    if cached_data:
        return {"modules": cached_data}
    
    # If not in cache, get from database and cache it
    modules_data = await update_cache(db)
    return {"modules": modules_data}


@router.post("/modules", response_model=ModuleSchema, status_code=status.HTTP_201_CREATED)
async def create_module(module: ModuleCreate, db: AsyncSession = Depends(get_db)):
    """Create a new module"""
    db_module = Module(**module.dict())
    db.add(db_module)
    await db.commit()
    await db.refresh(db_module)
    
    # Update cache
    await update_cache(db)
    
    return db_module


@router.get("/modules", response_model=List[ModuleSchema])
async def get_modules(db: AsyncSession = Depends(get_db)):
    """Get all modules"""
    result = await db.execute(
        select(Module)
        .options(selectinload(Module.lessons).selectinload(Lesson.packs))
        .order_by(Module.id)
    )
    modules = result.scalars().all()
    return modules


@router.get("/modules/{module_id}", response_model=ModuleSchema)
async def get_module(module_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific module by ID"""
    result = await db.execute(
        select(Module)
        .options(selectinload(Module.lessons).selectinload(Lesson.packs))
        .where(Module.id == module_id)
    )
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


@router.put("/modules/{module_id}", response_model=ModuleSchema)
async def update_module(module_id: int, module_update: ModuleUpdate, db: AsyncSession = Depends(get_db)):
    """Update a module"""
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    for field, value in module_update.dict(exclude_unset=True).items():
        setattr(module, field, value)
    
    await db.commit()
    await db.refresh(module)
    
    # Update cache
    await update_cache(db)
    
    return module


@router.delete("/modules/{module_id}")
async def delete_module(module_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a module"""
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    await db.delete(module)
    await db.commit()
    
    # Update cache
    await update_cache(db)
    
    return {"message": "Module deleted successfully"}


@router.post("/lessons", response_model=LessonSchema, status_code=status.HTTP_201_CREATED)
async def create_lesson(lesson: LessonCreate, db: AsyncSession = Depends(get_db)):
    """Create a new lesson"""
    # Check if module exists
    result = await db.execute(select(Module).where(Module.id == lesson.module_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Module not found")
    
    db_lesson = Lesson(**lesson.dict())
    db.add(db_lesson)
    await db.commit()
    await db.refresh(db_lesson)
    
    # Update cache
    await update_cache(db)
    
    return db_lesson


@router.get("/lessons/{lesson_id}", response_model=LessonSchema)
async def get_lesson(lesson_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific lesson by ID"""
    result = await db.execute(
        select(Lesson)
        .options(selectinload(Lesson.packs))
        .where(Lesson.id == lesson_id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


@router.put("/lessons/{lesson_id}", response_model=LessonSchema)
async def update_lesson(lesson_id: int, lesson_update: LessonUpdate, db: AsyncSession = Depends(get_db)):
    """Update a lesson"""
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    for field, value in lesson_update.dict(exclude_unset=True).items():
        setattr(lesson, field, value)
    
    await db.commit()
    await db.refresh(lesson)
    
    # Update cache
    await update_cache(db)
    
    return lesson


@router.delete("/lessons/{lesson_id}")
async def delete_lesson(lesson_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a lesson"""
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    await db.delete(lesson)
    await db.commit()
    
    # Update cache
    await update_cache(db)
    
    return {"message": "Lesson deleted successfully"}


@router.post("/packs", response_model=PackSchema, status_code=status.HTTP_201_CREATED)
async def create_pack(pack: PackCreate, db: AsyncSession = Depends(get_db)):
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
    
    # Update cache
    await update_cache(db)
    
    return db_pack


@router.get("/packs/{pack_id}", response_model=PackSchema)
async def get_pack(pack_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific pack by ID"""
    result = await db.execute(select(Pack).where(Pack.id == pack_id))
    pack = result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    return pack


@router.put("/packs/{pack_id}", response_model=PackSchema)
async def update_pack(pack_id: int, pack_update: PackUpdate, db: AsyncSession = Depends(get_db)):
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
    
    # Update cache
    await update_cache(db)
    
    return pack


@router.delete("/packs/{pack_id}")
async def delete_pack(pack_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a pack"""
    result = await db.execute(select(Pack).where(Pack.id == pack_id))
    pack = result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    
    await db.delete(pack)
    await db.commit()
    
    # Update cache
    await update_cache(db)
    
    return {"message": "Pack deleted successfully"}