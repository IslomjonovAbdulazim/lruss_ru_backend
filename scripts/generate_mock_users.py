import asyncio
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal, init_db
from app.models import User, UserProgress, Pack
from sqlalchemy import select

load_dotenv()

async def create_mock_users():
    """Create mock users for leaderboard testing"""
    
    # Mock user data
    mock_users = [
        {
            "telegram_id": 998990000001,
            "phone_number": "+998990000001",
            "first_name": "Mock",
            "last_name": "User1",
            "points": 100
        },
        {
            "telegram_id": 998990000002,
            "phone_number": "+998990000002",
            "first_name": "Mock",
            "last_name": "User2",
            "points": 200
        },
        {
            "telegram_id": 998990000003,
            "phone_number": "+998990000003",
            "first_name": "Mock",
            "last_name": "User3",
            "points": 300
        },
        {
            "telegram_id": 998990000004,
            "phone_number": "+998990000004",
            "first_name": "Mock",
            "last_name": "User4",
            "points": 400
        }
    ]
    
    async with AsyncSessionLocal() as session:
        try:
            # Get first pack to assign progress to
            pack_result = await session.execute(select(Pack).limit(1))
            pack = pack_result.scalar_one_or_none()
            
            if not pack:
                print("No packs found in database. Creating a dummy pack...")
                # Create a dummy pack if none exists
                from app.models import Module, Lesson, PackType
                
                # Create dummy module
                module = Module(title="Mock Module", order=1)
                session.add(module)
                await session.flush()
                
                # Create dummy lesson
                lesson = Lesson(title="Mock Lesson", module_id=module.id, order=1)
                session.add(lesson)
                await session.flush()
                
                # Create dummy pack
                pack = Pack(title="Mock Pack", lesson_id=lesson.id, type=PackType.WORD)
                session.add(pack)
                await session.flush()
            
            for user_data in mock_users:
                # Check if user already exists
                existing_user = await session.execute(
                    select(User).where(User.phone_number == user_data["phone_number"])
                )
                if existing_user.scalar_one_or_none():
                    print(f"User with phone {user_data['phone_number']} already exists, skipping...")
                    continue
                
                # Create user
                user = User(
                    telegram_id=user_data["telegram_id"],
                    phone_number=user_data["phone_number"],
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"]
                )
                session.add(user)
                await session.flush()
                
                # Create user progress with points
                progress = UserProgress(
                    user_id=user.id,
                    pack_id=pack.id,
                    best_score=85,  # Mock score
                    total_points=user_data["points"]
                )
                session.add(progress)
                
                print(f"Created user: {user_data['first_name']} {user_data['last_name']} with {user_data['points']} points")
            
            await session.commit()
            print("\nMock users created successfully!")
            print("Users will appear on the leaderboard with their assigned points.")
            
        except Exception as e:
            await session.rollback()
            print(f"Error creating mock users: {e}")
            raise

async def main():
    """Main function to run the script"""
    print("Creating mock users for leaderboard...")
    
    # Initialize database tables if they don't exist
    await init_db()
    
    # Create mock users
    await create_mock_users()

if __name__ == "__main__":
    asyncio.run(main())