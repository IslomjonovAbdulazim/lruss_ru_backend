from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import os

from app.database import init_db
from app.routers import auth, profile, education, quiz, grammar_topics, admin, progress, leaderboard, translation, subscription
from app.routers import dashboard
from app.telegram_bot import start_bot
from app.redis_client import close_redis
from app.routers.leaderboard import start_leaderboard_scheduler, stop_leaderboard_scheduler
from dotenv import load_dotenv

load_dotenv()

# Global hardcoded passkey for testing purposes - loaded from .env
TEST_PASSKEY = os.getenv("TEST_PASSKEY")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create storage directories
    storage_path = os.getenv("STORAGE_PATH", "/tmp/persistent_storage")
    os.makedirs(f"{storage_path}/user_photos", exist_ok=True)
    os.makedirs(f"{storage_path}/word_audio", exist_ok=True)
    print(f"✅ Storage directories created: {storage_path}")
    
    try:
        await init_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print("⚠️  Server will start without database connection")
    
    try:
        await start_bot()
        print("✅ Telegram bot started successfully")
    except Exception as e:
        print(f"❌ Telegram bot failed to start: {e}")
    
    try:
        start_leaderboard_scheduler()
        print("✅ Leaderboard scheduler started")
    except Exception as e:
        print(f"❌ Leaderboard scheduler failed: {e}")
    
    yield
    
    try:
        stop_leaderboard_scheduler()
    except Exception as e:
        print(f"❌ Error stopping leaderboard scheduler: {e}")
    
    try:
        await close_redis()
    except Exception as e:
        print(f"❌ Error closing Redis: {e}")


app = FastAPI(
    title="Educational Platform API",
    description="Simplified Backend API for educational platform with Telegram authentication",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://admin.lruss.uz",
        "https://lruss.uz"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simplified API Routes
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(education.router, prefix="/api/education", tags=["education"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["quiz"])
app.include_router(grammar_topics.router, prefix="/api/grammar", tags=["grammar"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(progress.router, prefix="/api/progress", tags=["progress"])
app.include_router(leaderboard.router, prefix="/api/leaderboard", tags=["leaderboard"])
app.include_router(translation.router, prefix="/api/translation", tags=["translation"])
app.include_router(subscription.router, prefix="/api/subscription", tags=["subscription"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])

# Mount static files for photo serving
storage_path = os.getenv("STORAGE_PATH", "/tmp/persistent_storage")
app.mount("/storage", StaticFiles(directory=storage_path), name="storage")


@app.get("/")
async def root():
    return {"message": "Educational Platform API v2.0 - Simplified & Optimized!"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)