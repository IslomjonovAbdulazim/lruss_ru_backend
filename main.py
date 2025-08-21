from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.database import init_db
from app.routers import auth, profile, education, quiz, grammar_topics, admin, progress, leaderboard, translation, subscription
from app.telegram_bot import start_bot
from app.redis_client import close_redis
from app.routers.leaderboard import start_leaderboard_scheduler, stop_leaderboard_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await start_bot()
    start_leaderboard_scheduler()
    yield
    stop_leaderboard_scheduler()
    await close_redis()


app = FastAPI(
    title="Educational Platform API",
    description="Backend API for educational platform with Telegram authentication",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/")
async def root():
    return {"message": "Educational Platform API is running!"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)