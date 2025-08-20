import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models import User
from app.utils import generate_temp_code, sanitize_name
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("📱 Telefon raqamni ulashish", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Ta'lim platformasiga xush kelibsiz! 📚\n\n"
        "Telefon raqamingizni ulashing.",
        reply_markup=reply_markup
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    
    if contact.user_id != update.effective_user.id:
        await update.message.reply_text("Iltimos, o'zingizning telefon raqamingizni ulashing.")
        return
    
    phone_number = contact.phone_number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    telegram_id = update.effective_user.id
    first_name = sanitize_name(update.effective_user.first_name or "")
    last_name = sanitize_name(update.effective_user.last_name or "")
    
    temp_code = generate_temp_code()
    
    async with AsyncSessionLocal() as session:
        existing_user = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = existing_user.scalar_one_or_none()
        
        if not user:
            avatar_url = None
            try:
                photos = await update.effective_user.get_profile_photos()
                if photos.photos:
                    file = await context.bot.get_file(photos.photos[0][-1].file_id)
                    avatar_url = file.file_path
            except Exception:
                avatar_url = None
            
            user = User(
                telegram_id=telegram_id,
                phone_number=phone_number,
                first_name=first_name or "Foydalanuvchi",
                last_name=last_name,
                avatar_url=avatar_url
            )
            session.add(user)
            await session.commit()
    
    from app.redis_client import set_otp_code
    await set_otp_code(phone_number, temp_code, 300)
    
    await update.message.reply_text(
        f"✅ Ro'yxatdan o'tdingiz!\n\n"
        f"📱 Telefon raqam: {phone_number}\n"
        f"🔐 Tasdiqlash kodi: {temp_code}\n\n"
        f"Ilovada shu ma'lumotlarni kiriting. Kod 5 daqiqa amal qiladi."
    )


async def send_code_to_user(phone_number: str, code: str):
    """Send verification code to user via Telegram"""
    try:
        async with AsyncSessionLocal() as session:
            user_result = await session.execute(
                select(User).where(User.phone_number == phone_number)
            )
            user = user_result.scalar_one_or_none()
            
            if user:
                from telegram import Bot
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"🔐 Tasdiqlash kodi: {code}\n\n"
                         f"Ushbu kod 5 daqiqa davomida amal qiladi. "
                         f"Kodni ilovada kiriting."
                )
                return True
    except Exception as e:
        print(f"Error sending code to user: {e}")
    return False




async def start_bot():
    if not BOT_TOKEN:
        print("BOT_TOKEN not found in environment variables")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("Telegram bot started successfully!")