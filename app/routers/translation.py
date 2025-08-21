from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

from app.database import get_db
from app.models import Translation, User
from app.schemas import TranslationRequest, TranslationResponse
from app.dependencies import get_current_user, get_admin_user

load_dotenv()

router = APIRouter()

# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = AsyncOpenAI(
    api_key=openai_api_key
)

ALLOWED_LANGUAGES = {"uz", "ru"}
LANGUAGE_NAMES = {
    "uz": "Uzbek",
    "ru": "Russian"
}


async def translate_with_openai(text: str, target_language: str) -> str:
    """Translate text using OpenAI API"""
    
    target_name = LANGUAGE_NAMES[target_language]
    
    system_prompt = f"""You are a professional translator. Translate the given text to {target_name}. 
    
Rules:
- Only translate to {target_name}
- Preserve the meaning and context
- Keep the same tone and style
- For technical terms, use appropriate {target_name} equivalents
- Return only the translation, no explanations"""

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation failed: {str(e)}"
        )


@router.post("/translate", response_model=TranslationResponse)
async def translate_text(
    request: TranslationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Translate text with database caching"""
    
    # Validate target language
    if request.target_language not in ALLOWED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target language. Only {', '.join(ALLOWED_LANGUAGES)} are supported."
        )
    
    # Validate input text
    if not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input text cannot be empty"
        )
    
    # Check if translation exists in database (cache)
    existing_result = await db.execute(
        select(Translation).where(
            Translation.input_text == request.text.strip(),
            Translation.target_language == request.target_language
        )
    )
    existing_translation = existing_result.scalar_one_or_none()
    
    if existing_translation:
        # Return cached translation
        return TranslationResponse(
            input_text=existing_translation.input_text,
            target_language=existing_translation.target_language,
            output_text=existing_translation.output_text,
            from_cache=True
        )
    
    # Translation not cached - call OpenAI
    try:
        output_text = await translate_with_openai(request.text.strip(), request.target_language)
        
        # Save to database for future caching
        new_translation = Translation(
            input_text=request.text.strip(),
            target_language=request.target_language,
            output_text=output_text
        )
        
        db.add(new_translation)
        await db.commit()
        
        return TranslationResponse(
            input_text=request.text.strip(),
            target_language=request.target_language,
            output_text=output_text,
            from_cache=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation service error: {str(e)}"
        )


@router.get("/admin/translations")
async def get_all_translations(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Get all translations (admin only)"""
    result = await db.execute(
        select(Translation).offset(skip).limit(limit)
    )
    translations = result.scalars().all()
    return translations


@router.delete("/admin/translations/{translation_id}")
async def delete_translation(
    translation_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a translation by ID (admin only)"""
    result = await db.execute(
        select(Translation).where(Translation.id == translation_id)
    )
    translation = result.scalar_one_or_none()
    
    if not translation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation not found"
        )
    
    await db.delete(translation)
    await db.commit()
    return {"message": "Translation deleted successfully"}


@router.delete("/admin/translations")
async def clear_all_translations(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Clear all translations from cache (admin only)"""
    from sqlalchemy import text
    await db.execute(text("DELETE FROM translations"))
    await db.commit()
    return {"message": "All translations cleared successfully"}