from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.schemas import AuthRequest, TokenResponse, RefreshTokenRequest
from app.utils import create_access_token, create_refresh_token, verify_token, generate_temp_code, sanitize_name
from app.telegram_bot import send_code_to_user
from app.redis_client import set_otp_code, get_otp_code, delete_otp_code, invalidate_users_cache
from pydantic import BaseModel
import os
from telegram import Bot
from dotenv import load_dotenv
import aiofiles
from pathlib import Path
import aiohttp

load_dotenv()

router = APIRouter()


class SendCodeRequest(BaseModel):
    phone_number: str


@router.post("/send-code")
async def send_code(request: SendCodeRequest, db: AsyncSession = Depends(get_db)):
    phone_number = request.phone_number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    # Check if this is admin phone - block with generic error
    admin_phone = os.getenv("ADMIN_PHONE")
    if admin_phone and phone_number == admin_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication service temporarily unavailable for this account"
        )
    
    user_result = await db.execute(
        select(User).where(User.phone_number == phone_number)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please register via Telegram bot first."
        )
    
    temp_code = generate_temp_code()
    
    await set_otp_code(phone_number, temp_code, 300)
    
    success = await send_code_to_user(phone_number, temp_code)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send code via Telegram"
        )
    
    return {"message": "Code sent successfully"}


@router.post("/login", response_model=TokenResponse)
async def login(auth_request: AuthRequest, db: AsyncSession = Depends(get_db)):
    phone_number = auth_request.phone_number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    # Check if this is admin phone - block with generic error
    admin_phone = os.getenv("ADMIN_PHONE")
    if admin_phone and phone_number == admin_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication service temporarily unavailable for this account"
        )
    
    cached_code = await get_otp_code(phone_number)
    
    if not cached_code or cached_code != auth_request.code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired code"
        )
    
    user_result = await db.execute(
        select(User).where(User.phone_number == phone_number)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await delete_otp_code(phone_number)
    
    # Refresh user profile from Telegram on each login
    try:
        bot = Bot(token=os.getenv("BOT_TOKEN"))
        user_profile = await bot.get_chat(user.telegram_id)
        photos = await bot.get_user_profile_photos(user.telegram_id, limit=1)
        
        # Update names
        first_name = sanitize_name(user_profile.first_name or "")
        last_name = sanitize_name(user_profile.last_name or "")
        
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        
        # Update avatar only if user doesn't have a local photo
        if not user.avatar_url or not user.avatar_url.startswith("/storage/"):
            if photos.photos:
                try:
                    # Download and save Telegram profile photo locally
                    file = await bot.get_file(photos.photos[0][-1].file_id)
                    file_url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"
                    
                    # Create filename using phone number
                    phone_clean = user.phone_number.replace("+", "").replace("-", "").replace(" ", "")
                    extension = Path(file.file_path).suffix.lower() or ".jpg"
                    filename = f"{phone_clean}{extension}"
                    
                    # Storage path
                    storage_path = os.getenv("STORAGE_PATH", "/tmp/persistent_storage")
                    user_photos_dir = Path(storage_path) / "user_photos"
                    user_photos_dir.mkdir(parents=True, exist_ok=True)
                    file_path = user_photos_dir / filename
                    
                    # Download and save file
                    async with aiohttp.ClientSession() as session:
                        async with session.get(file_url) as response:
                            if response.status == 200:
                                file_data = await response.read()
                                # Check size limit (1MB)
                                if len(file_data) <= 1048576:
                                    async with aiofiles.open(file_path, "wb") as f:
                                        await f.write(file_data)
                                    user.avatar_url = f"/storage/user_photos/{filename}"
                except Exception as e:
                    print(f"Error saving Telegram photo: {e}")
                    # Fallback to Telegram URL if local save fails
                    user.avatar_url = file.file_path
            else:
                user.avatar_url = None
        
        await db.commit()
        await db.refresh(user)
        
        # Invalidate users cache since user data was updated
        await invalidate_users_cache()
        
    except Exception as e:
        print(f"Error refreshing user profile on login: {e}")
        # Continue with login even if profile refresh fails
    
    access_token = create_access_token(data={"sub": str(user.id), "phone": user.phone_number})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "phone": user.phone_number})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    payload = verify_token(refresh_request.refresh_token, token_type="refresh")
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user_result = await db.execute(select(User).where(User.id == int(user_id)))
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    access_token = create_access_token(data={"sub": str(user.id), "phone": user.phone_number})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id), "phone": user.phone_number})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token
    )