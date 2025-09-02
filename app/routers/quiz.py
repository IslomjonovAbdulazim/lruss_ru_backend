from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any, Optional
import json
from app.database import get_db
from app.models import Pack, Word, Grammar, PackType, GrammarType, User
from app.schemas import (
    Word as WordSchema, WordCreate, WordUpdate,
    Grammar as GrammarSchema, GrammarCreate, GrammarUpdate,
    QuizResponse
)
from app.dependencies import get_current_user, get_admin_user
from app.redis_client import get_quiz_cache, set_quiz_cache, invalidate_quiz_cache

router = APIRouter()


async def get_quiz_data_from_db(db: AsyncSession) -> Dict[str, Any]:
    """Get all quiz data (words and grammars) from database"""
    # Get all word packs with their words
    word_packs_result = await db.execute(
        select(Pack)
        .options(selectinload(Pack.words))
        .where(Pack.type == PackType.WORD)
        .order_by(Pack.id)
    )
    word_packs = word_packs_result.scalars().all()

    # Get all grammar packs with their grammars
    grammar_packs_result = await db.execute(
        select(Pack)
        .options(selectinload(Pack.grammars))
        .where(Pack.type == PackType.GRAMMAR)
        .order_by(Pack.id)
    )
    grammar_packs = grammar_packs_result.scalars().all()

    # Convert to dict format for cache
    word_packs_data = []
    for pack in word_packs:
        pack_dict = {
            "id": pack.id,
            "title": pack.title,
            "lesson_id": pack.lesson_id,
            "type": pack.type.value,
            "word_count": pack.word_count,
            "created_at": pack.created_at,
            "updated_at": pack.updated_at,
            "words": [],
            "grammars": []
        }

        for word in pack.words:
            word_dict = {
                "id": word.id,
                "pack_id": word.pack_id,
                "audio_url": word.audio_url,
                "ru_text": word.ru_text,
                "uz_text": word.uz_text,
                "created_at": word.created_at,
                "updated_at": word.updated_at
            }
            pack_dict["words"].append(word_dict)

        word_packs_data.append(pack_dict)

    grammar_packs_data = []
    for pack in grammar_packs:
        pack_dict = {
            "id": pack.id,
            "title": pack.title,
            "lesson_id": pack.lesson_id,
            "type": pack.type.value,
            "word_count": pack.word_count,
            "created_at": pack.created_at,
            "updated_at": pack.updated_at,
            "words": [],
            "grammars": []
        }

        for grammar in pack.grammars:
            # Parse options from JSON string
            options = None
            if grammar.options:
                try:
                    options = json.loads(grammar.options)
                except:
                    options = None

            grammar_dict = {
                "id": grammar.id,
                "pack_id": grammar.pack_id,
                "type": grammar.type.value,
                "question_text": grammar.question_text,
                "options": options,
                "correct_option": grammar.correct_option,
                "sentence": grammar.sentence,
                "created_at": grammar.created_at,
                "updated_at": grammar.updated_at
            }
            pack_dict["grammars"].append(grammar_dict)

        grammar_packs_data.append(pack_dict)

    return {
        "word_packs": word_packs_data,
        "grammar_packs": grammar_packs_data
    }


async def update_quiz_cache(db: AsyncSession):
    """Update the quiz cache with fresh data from database"""
    quiz_data = await get_quiz_data_from_db(db)
    await set_quiz_cache(quiz_data)
    return quiz_data


# SINGLE GET ENDPOINT FOR ALL QUIZ DATA
@router.get("/all", response_model=QuizResponse)
async def get_all_quiz_data(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all quiz data: words and grammars with pack names from cache"""
    # Try to get from cache first
    cached_data = await get_quiz_cache()
    if cached_data:
        return cached_data

    # If not in cache, get from database and cache it
    quiz_data = await update_quiz_cache(db)
    return quiz_data


# WORD CRUD
@router.get("/words", response_model=List[WordSchema])
async def get_words(pack_id: Optional[int] = Query(None), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all words, optionally filtered by pack_id"""
    query = select(Word).order_by(Word.id)
    if pack_id:
        query = query.where(Word.pack_id == pack_id)
    
    result = await db.execute(query)
    words = result.scalars().all()
    return words


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
    await update_quiz_cache(db)
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
    await update_quiz_cache(db)
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
    await update_quiz_cache(db)
    return {"message": "Word deleted successfully"}


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
    await update_quiz_cache(db)

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
    await update_quiz_cache(db)

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
    await update_quiz_cache(db)
    return {"message": "Grammar deleted successfully"}