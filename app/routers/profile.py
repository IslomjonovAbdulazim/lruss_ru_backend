import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot
import aiofiles
from pathlib import Path
from app.database import get_db
from app.models import User
from app.schemas import User as UserSchema, UserUpdate
from app.dependencies import get_current_user
from app.utils import sanitize_name
from app.redis_client import invalidate_users_cache
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
bot = Bot(token=os.getenv("BOT_TOKEN"))


@router.get("/me", response_model=UserSchema)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    update_data = user_update.dict(exclude_unset=True)
    
    if "first_name" in update_data:
        update_data["first_name"] = sanitize_name(update_data["first_name"])
        if not update_data["first_name"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="First name cannot be empty"
            )
    
    if "last_name" in update_data and update_data["last_name"]:
        update_data["last_name"] = sanitize_name(update_data["last_name"])
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    # Invalidate users cache since user data was updated
    await invalidate_users_cache()
    
    return current_user


@router.post("/refresh-avatar", response_model=UserSchema)
async def refresh_avatar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        user_profile = await bot.get_chat(current_user.telegram_id)
        photos = await bot.get_user_profile_photos(current_user.telegram_id, limit=1)
        
        if photos.photos:
            file = await bot.get_file(photos.photos[0][-1].file_id)
            avatar_url = file.file_path
            current_user.avatar_url = avatar_url
        else:
            current_user.avatar_url = None
        
        first_name = sanitize_name(user_profile.first_name or "")
        last_name = sanitize_name(user_profile.last_name or "")
        
        if first_name:
            current_user.first_name = first_name
        if last_name:
            current_user.last_name = last_name
        
        await db.commit()
        await db.refresh(current_user)
        
        # Invalidate users cache since user data was updated
        await invalidate_users_cache()
        
        return current_user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh avatar: {str(e)}"
        )


@router.post("/upload-photo", response_model=UserSchema)
async def upload_photo(
    photo: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload user profile photo (max 1MB)"""
    # Validate file size (1MB = 1048576 bytes)
    MAX_SIZE = 1048576
    
    # Read file to check size
    contents = await photo.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Photo size must be less than 1MB"
        )
    
    # Validate file type - check both content type and file extension
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
    
    file_extension = Path(photo.filename).suffix.lower()
    
    if photo.content_type not in allowed_types and file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, WebP, HEIC and HEIF images are allowed"
        )
    
    # Get file extension
    extension = Path(photo.filename).suffix.lower()
    if not extension:
        extension = ".jpg"  # Default extension
    
    # Create filename using phone number (unique per user)
    phone_clean = current_user.phone_number.replace("+", "").replace("-", "").replace(" ", "")
    filename = f"{phone_clean}{extension}"
    
    # Storage path
    storage_path = os.getenv("STORAGE_PATH", "/tmp/persistent_storage")
    user_photos_dir = Path(storage_path) / "user_photos"
    user_photos_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = user_photos_dir / filename
    
    # Save file (overwrites if exists)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)
    
    # Update user avatar_url to relative path
    relative_path = f"/storage/user_photos/{filename}"
    current_user.avatar_url = relative_path
    
    await db.commit()
    await db.refresh(current_user)
    
    # Invalidate users cache
    await invalidate_users_cache()
    
    return current_user