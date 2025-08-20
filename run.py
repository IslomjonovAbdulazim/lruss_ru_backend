#!/usr/bin/env python3
import asyncio
import uvicorn
from main import app

if __name__ == "__main__":
    print("🚀 Starting Educational Platform API...")
    print("📱 Telegram bot will start automatically")
    print("🌐 API will be available at: http://localhost:8000")
    print("📖 API docs will be available at: http://localhost:8000/docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )