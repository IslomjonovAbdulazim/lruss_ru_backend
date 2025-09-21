#!/usr/bin/env python3
"""
Script to reset database with fresh content from JSON files
"""
import json
import sys
import os
import asyncio
from pathlib import Path

# Add the parent directory to sys.path to import app modules
sys.path.append(str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.models import Module, Lesson, Pack, Word, Grammar, GrammarTopic, PackType, GrammarType
from sqlalchemy import text


async def clean_database():
    """Clean ONLY content-related tables (modules, lessons, packs, words, grammars, grammar_topics, user_progress)"""
    print("🧹 Cleaning content tables only (keeping users, premiums, etc.)...")

    async with AsyncSessionLocal() as db:
        # Define tables to clean in reverse order of dependencies
        tables_to_clean = [
            "user_progress",
            "grammar_topics", 
            "grammars",
            "words", 
            "packs",
            "lessons",
            "modules"
        ]
        
        for table in tables_to_clean:
            try:
                print(f"   - Deleting {table}...")
                await db.execute(text(f"DELETE FROM {table}"))
            except Exception as e:
                if "does not exist" in str(e):
                    print(f"   - Skipping {table} (table doesn't exist yet)")
                else:
                    raise e

        await db.commit()

    print("✅ Content tables cleaned successfully (users and premiums preserved)")


async def load_modules():
    """Load modules from modules.json"""
    print("📚 Loading modules...")

    modules_file = Path(__file__).parent.parent / "content" / "modules.json"

    with open(modules_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    async with AsyncSessionLocal() as db:
        for module_data in data['modules']:
            module = Module(
                id=module_data['id'],
                title=module_data['title'],
                order=module_data['order']
            )
            db.add(module)

        await db.commit()

    print(f"✅ Loaded {len(data['modules'])} modules")


async def load_lessons():
    """Load lessons from lessons.json"""
    print("📖 Loading lessons...")

    lessons_file = Path(__file__).parent.parent / "content" / "lessons.json"

    with open(lessons_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    async with AsyncSessionLocal() as db:
        for lesson_data in data['lessons']:
            lesson = Lesson(
                id=lesson_data['id'],
                title=lesson_data['title'],
                description=lesson_data['description'],
                module_id=lesson_data['module_id'],
                order=lesson_data['order']
            )
            db.add(lesson)

        await db.commit()

    print(f"✅ Loaded {len(data['lessons'])} lessons")


async def load_detailed_content():
    """Load detailed content from module JSON files"""
    print("📝 Loading detailed content...")

    content_dir = Path(__file__).parent.parent / "content"

    # Load Module 1 detailed content
    module1_file = content_dir / "1.json"

    if not module1_file.exists():
        print("⚠️  Module 1 detailed content not found, skipping...")
        return

    with open(module1_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    async with AsyncSessionLocal() as db:
        for lesson_data in data['lessons']:
            for pack_data in lesson_data.get('packs', []):
                # Create pack
                pack = Pack(
                    id=pack_data['id'],
                    title=pack_data['title'],
                    lesson_id=pack_data['lesson_id'],
                    type=PackType(pack_data['type']),
                    word_count=pack_data.get('word_count')
                )
                db.add(pack)
                await db.flush()  # Get the ID

                # Add words if this is a word pack
                if 'words' in pack_data:
                    for word_data in pack_data['words']:
                        word = Word(
                            id=word_data['id'],
                            pack_id=word_data['pack_id'],
                            ru_text=word_data['ru_text'],
                            uz_text=word_data['uz_text']
                        )
                        db.add(word)

                # Add grammars if this is a grammar pack
                if 'grammars' in pack_data:
                    for grammar_data in pack_data['grammars']:
                        grammar = Grammar(
                            id=grammar_data['id'],
                            pack_id=grammar_data['pack_id'],
                            type=GrammarType(grammar_data['type']),
                            question_text=grammar_data.get('question_text'),
                            options=grammar_data.get('options'),
                            correct_option=grammar_data.get('correct_option'),
                            sentence=grammar_data.get('sentence')
                        )
                        db.add(grammar)

                # Add grammar topics
                if 'grammar_topics' in pack_data:
                    for topic_data in pack_data['grammar_topics']:
                        topic = GrammarTopic(
                            id=topic_data['id'],
                            pack_id=topic_data['pack_id'],
                            video_url=topic_data.get('video_url'),
                            markdown_text=topic_data.get('markdown_text')
                        )
                        db.add(topic)

        await db.commit()

    print("✅ Loaded detailed content for Module 1")


async def get_stats():
    """Get database statistics"""
    async with AsyncSessionLocal() as db:
        module_count = (await db.execute(text("SELECT COUNT(*) FROM modules"))).scalar()
        lesson_count = (await db.execute(text("SELECT COUNT(*) FROM lessons"))).scalar()
        pack_count = (await db.execute(text("SELECT COUNT(*) FROM packs"))).scalar()
        word_count = (await db.execute(text("SELECT COUNT(*) FROM words"))).scalar()
        grammar_count = (await db.execute(text("SELECT COUNT(*) FROM grammars"))).scalar()

        return {
            'modules': module_count,
            'lessons': lesson_count,
            'packs': pack_count,
            'words': word_count,
            'grammars': grammar_count
        }


async def main():
    """Main function to reset CONTENT ONLY (preserves users, premiums, etc.)"""
    print("🚀 Starting content reset (preserving users and premiums)...")

    try:
        # Step 1: Clean ONLY content tables
        await clean_database()

        # Step 2: Load modules
        await load_modules()

        # Step 3: Load lessons
        await load_lessons()

        # Step 4: Load detailed content
        await load_detailed_content()

        print("\n🎉 Content reset completed successfully!")
        print("📊 Content Summary:")

        stats = await get_stats()
        print(f"   - Modules: {stats['modules']}")
        print(f"   - Lessons: {stats['lessons']}")
        print(f"   - Packs: {stats['packs']}")
        print(f"   - Words: {stats['words']}")
        print(f"   - Grammar exercises: {stats['grammars']}")
        print("\n✅ User data and premiums were preserved")

    except Exception as e:
        print(f"❌ Error during content reset: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())