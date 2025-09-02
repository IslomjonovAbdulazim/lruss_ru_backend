from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any, Optional
import json
import os
import aiofiles
from pathlib import Path
from app.database import get_db
from app.models import Pack, Word, Grammar, PackType, GrammarType, User
from app.schemas import (
    Word as WordSchema, WordCreate, WordUpdate,
    Grammar as GrammarSchema, GrammarCreate, GrammarUpdate,
    QuizResponse
)
from app.dependencies import get_current_user, get_admin_user
from app.redis_client import (
    get_quiz_cache, set_quiz_cache, invalidate_quiz_cache,
    get_words_cache_by_pack, set_words_cache_by_pack, invalidate_words_cache_by_pack,
    get_grammars_cache_by_pack, set_grammars_cache_by_pack, invalidate_grammars_cache_by_pack
)

router = APIRouter()








# WORD CRUD
@router.get("/words", response_model=List[WordSchema])
async def get_words(pack_id: Optional[int] = Query(None), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all words, optionally filtered by pack_id"""
    # If pack_id specified, try cache first
    if pack_id:
        cached_data = await get_words_cache_by_pack(pack_id)
        if cached_data:
            return cached_data
    
    query = select(Word).order_by(Word.id)
    if pack_id:
        query = query.where(Word.pack_id == pack_id)
    
    result = await db.execute(query)
    words = result.scalars().all()
    
    # Convert to dict for caching
    words_data = [
        {
            "id": word.id,
            "pack_id": word.pack_id,
            "audio_url": word.audio_url,
            "ru_text": word.ru_text,
            "uz_text": word.uz_text,
            "created_at": word.created_at,
            "updated_at": word.updated_at
        }
        for word in words
    ]
    
    # Cache if filtered by pack_id
    if pack_id:
        await set_words_cache_by_pack(pack_id, words_data)
    
    return words_data


@router.get("/words/{word_id}", response_model=WordSchema)
async def get_word(word_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get a specific word"""
    result = await db.execute(select(Word).where(Word.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return word


@router.post("/words", response_model=WordSchema, status_code=status.HTTP_201_CREATED)
async def create_word(word: WordCreate, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Create a new word"""
    # Check if pack exists and is a word pack
    pack_result = await db.execute(select(Pack).where(Pack.id == word.pack_id))
    pack = pack_result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    if pack.type != PackType.WORD:
        raise HTTPException(status_code=400, detail="Pack is not a word pack")

    db_word = Word(**word.dict())
    db.add(db_word)
    await db.commit()
    await db.refresh(db_word)
    await invalidate_words_cache_by_pack(word.pack_id)
    return db_word


@router.put("/words/{word_id}", response_model=WordSchema)
async def update_word(word_id: int, word_update: WordUpdate, admin_user: User = Depends(get_admin_user),
                      db: AsyncSession = Depends(get_db)):
    """Update a word"""
    result = await db.execute(select(Word).where(Word.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    for field, value in word_update.dict(exclude_unset=True).items():
        setattr(word, field, value)

    await db.commit()
    await db.refresh(word)
    await invalidate_words_cache_by_pack(word.pack_id)
    return word


@router.delete("/words/{word_id}")
async def delete_word(word_id: int, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Delete a word"""
    result = await db.execute(select(Word).where(Word.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    await db.delete(word)
    await db.commit()
    await invalidate_words_cache_by_pack(word.pack_id)
    return {"message": "Word deleted successfully"}


@router.post("/words/{word_id}/audio", response_model=WordSchema)
async def upload_word_audio(
    word_id: int,
    audio: UploadFile = File(...),
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload audio for a word (max 1MB)"""
    # Get the word
    result = await db.execute(select(Word).where(Word.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    
    # Validate file size (1MB = 1048576 bytes)
    MAX_SIZE = 1048576
    
    # Read file to check size
    contents = await audio.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio size must be less than 1MB"
        )
    
    # Validate file type
    allowed_types = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/ogg", "audio/m4a"}
    if audio.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only MP3, WAV, OGG, M4A audio files are allowed"
        )
    
    # Get file extension
    extension = Path(audio.filename).suffix.lower()
    if not extension:
        extension = ".mp3"  # Default extension
    
    # Create filename using word ID (unique per word)
    filename = f"{word_id}{extension}"
    
    # Storage path
    storage_path = os.getenv("STORAGE_PATH", "/tmp/persistent_storage")
    word_audio_dir = Path(storage_path) / "word_audio"
    word_audio_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = word_audio_dir / filename
    
    # Save file (overwrites if exists)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)
    
    # Update word audio_url to relative path
    relative_path = f"/storage/word_audio/{filename}"
    word.audio_url = relative_path
    
    await db.commit()
    await db.refresh(word)
    
    # Invalidate words cache
    await invalidate_words_cache_by_pack(word.pack_id)
    
    return word


# GRAMMAR CRUD
@router.get("/grammars", response_model=List[GrammarSchema])
async def get_grammars(pack_id: Optional[int] = Query(None), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all grammars, optionally filtered by pack_id"""
    query = select(Grammar).order_by(Grammar.id)
    if pack_id:
        query = query.where(Grammar.pack_id == pack_id)
    
    result = await db.execute(query)
    grammars = result.scalars().all()
    
    # Convert to response format
    response_grammars = []
    for grammar in grammars:
        options = None
        if grammar.options:
            try:
                options = json.loads(grammar.options)
            except:
                options = None
        
        response_grammars.append(GrammarSchema(
            id=grammar.id,
            pack_id=grammar.pack_id,
            type=grammar.type.value,
            question_text=grammar.question_text,
            options=options,
            correct_option=grammar.correct_option,
            sentence=grammar.sentence,
            created_at=grammar.created_at,
            updated_at=grammar.updated_at
        ))
    
    return response_grammars


@router.get("/grammars/{grammar_id}", response_model=GrammarSchema)
async def get_grammar(grammar_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get a specific grammar"""
    result = await db.execute(select(Grammar).where(Grammar.id == grammar_id))
    grammar = result.scalar_one_or_none()
    if not grammar:
        raise HTTPException(status_code=404, detail="Grammar not found")
    
    # Convert to response format
    options = None
    if grammar.options:
        try:
            options = json.loads(grammar.options)
        except:
            options = None
    
    return GrammarSchema(
        id=grammar.id,
        pack_id=grammar.pack_id,
        type=grammar.type.value,
        question_text=grammar.question_text,
        options=options,
        correct_option=grammar.correct_option,
        sentence=grammar.sentence,
        created_at=grammar.created_at,
        updated_at=grammar.updated_at
    )


@router.post("/grammars", response_model=GrammarSchema, status_code=status.HTTP_201_CREATED)
async def create_grammar(grammar: GrammarCreate, admin_user: User = Depends(get_admin_user),
                         db: AsyncSession = Depends(get_db)):
    """Create a new grammar question"""
    # Check if pack exists and is a grammar pack
    pack_result = await db.execute(select(Pack).where(Pack.id == grammar.pack_id))
    pack = pack_result.scalar_one_or_none()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    if pack.type != PackType.GRAMMAR:
        raise HTTPException(status_code=400, detail="Pack is not a grammar pack")

    # Validate based on grammar type
    if grammar.type == "fill":
        if not grammar.question_text or not grammar.options or grammar.correct_option is None:
            raise HTTPException(
                status_code=400,
                detail="Fill type requires question_text, options, and correct_option"
            )
        if len(grammar.options) != 4:
            raise HTTPException(status_code=400, detail="Options must contain exactly 4 items")
        if grammar.correct_option < 0 or grammar.correct_option > 3:
            raise HTTPException(status_code=400, detail="correct_option must be between 0 and 3")
    elif grammar.type == "build":
        if not grammar.sentence:
            raise HTTPException(status_code=400, detail="Build type requires sentence")

    # Convert enum and options to database format
    grammar_type = GrammarType.FILL if grammar.type == "fill" else GrammarType.BUILD
    options_json = json.dumps(grammar.options) if grammar.options else None

    db_grammar = Grammar(
        pack_id=grammar.pack_id,
        type=grammar_type,
        question_text=grammar.question_text,
        options=options_json,
        correct_option=grammar.correct_option,
        sentence=grammar.sentence
    )

    db.add(db_grammar)
    await db.commit()
    await db.refresh(db_grammar)
    await invalidate_grammars_cache_by_pack(grammar.pack_id)

    # Convert back to response format
    response_grammar = GrammarSchema(
        id=db_grammar.id,
        pack_id=db_grammar.pack_id,
        type=db_grammar.type.value,
        question_text=db_grammar.question_text,
        options=json.loads(db_grammar.options) if db_grammar.options else None,
        correct_option=db_grammar.correct_option,
        sentence=db_grammar.sentence,
        created_at=db_grammar.created_at,
        updated_at=db_grammar.updated_at
    )

    return response_grammar


@router.put("/grammars/{grammar_id}", response_model=GrammarSchema)
async def update_grammar(grammar_id: int, grammar_update: GrammarUpdate, admin_user: User = Depends(get_admin_user),
                         db: AsyncSession = Depends(get_db)):
    """Update a grammar question"""
    result = await db.execute(select(Grammar).where(Grammar.id == grammar_id))
    grammar = result.scalar_one_or_none()
    if not grammar:
        raise HTTPException(status_code=404, detail="Grammar not found")

    update_data = grammar_update.dict(exclude_unset=True)

    # Validate and convert data
    if "type" in update_data:
        grammar_type = update_data["type"]
        if grammar_type == "fill":
            # Check if required fields for fill type will be present after update
            question_text = update_data.get("question_text", grammar.question_text)
            options = update_data.get("options")
            correct_option = update_data.get("correct_option", grammar.correct_option)

            if not question_text or not options or correct_option is None:
                raise HTTPException(
                    status_code=400,
                    detail="Fill type requires question_text, options, and correct_option"
                )
            if len(options) != 4:
                raise HTTPException(status_code=400, detail="Options must contain exactly 4 items")
            if correct_option < 0 or correct_option > 3:
                raise HTTPException(status_code=400, detail="correct_option must be between 0 and 3")

        elif grammar_type == "build":
            sentence = update_data.get("sentence", grammar.sentence)
            if not sentence:
                raise HTTPException(status_code=400, detail="Build type requires sentence")

        # Convert string type to enum
        update_data["type"] = GrammarType.FILL if grammar_type == "fill" else GrammarType.BUILD

    # Convert options to JSON string if provided
    if "options" in update_data and update_data["options"] is not None:
        update_data["options"] = json.dumps(update_data["options"])

    # Apply updates
    for field, value in update_data.items():
        setattr(grammar, field, value)

    await db.commit()
    await db.refresh(grammar)
    await invalidate_grammars_cache_by_pack(grammar.pack_id)

    # Convert back to response format
    options = None
    if grammar.options:
        try:
            options = json.loads(grammar.options)
        except:
            options = None

    return GrammarSchema(
        id=grammar.id,
        pack_id=grammar.pack_id,
        type=grammar.type.value,
        question_text=grammar.question_text,
        options=options,
        correct_option=grammar.correct_option,
        sentence=grammar.sentence,
        created_at=grammar.created_at,
        updated_at=grammar.updated_at
    )


@router.delete("/grammars/{grammar_id}")
async def delete_grammar(grammar_id: int, admin_user: User = Depends(get_admin_user),
                         db: AsyncSession = Depends(get_db)):
    """Delete a grammar question"""
    result = await db.execute(select(Grammar).where(Grammar.id == grammar_id))
    grammar = result.scalar_one_or_none()
    if not grammar:
        raise HTTPException(status_code=404, detail="Grammar not found")

    await db.delete(grammar)
    await db.commit()
    await invalidate_grammars_cache_by_pack(grammar.pack_id)
    return {"message": "Grammar deleted successfully"}