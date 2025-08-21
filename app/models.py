from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Boolean, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PackType(enum.Enum):
    GRAMMAR = "grammar"
    WORD = "word"


class GrammarType(enum.Enum):
    FILL = "fill"
    BUILD = "build"


class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    lessons = relationship("Lesson", back_populates="module", cascade="all, delete-orphan")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    module = relationship("Module", back_populates="lessons")
    packs = relationship("Pack", back_populates="lesson", cascade="all, delete-orphan")


class Pack(Base):
    __tablename__ = "packs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    type = Column(Enum(PackType), nullable=False)
    word_count = Column(Integer, nullable=True)  # Only for word packs
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    lesson = relationship("Lesson", back_populates="packs")
    words = relationship("Word", back_populates="pack", cascade="all, delete-orphan")
    grammars = relationship("Grammar", back_populates="pack", cascade="all, delete-orphan")
    grammar_topics = relationship("GrammarTopic", back_populates="pack", cascade="all, delete-orphan")


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, index=True)
    pack_id = Column(Integer, ForeignKey("packs.id"), nullable=False)
    audio_url = Column(String, nullable=True)
    ru_text = Column(String, nullable=True)
    uz_text = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    pack = relationship("Pack", back_populates="words")


class Grammar(Base):
    __tablename__ = "grammars"

    id = Column(Integer, primary_key=True, index=True)
    pack_id = Column(Integer, ForeignKey("packs.id"), nullable=False)
    type = Column(Enum(GrammarType), nullable=False)
    question_text = Column(String, nullable=True)  # Required for fill type
    options = Column(String, nullable=True)  # JSON string of 4 options, required for fill type
    correct_option = Column(Integer, nullable=True)  # Index of correct option (0-3), required for fill type
    sentence = Column(String, nullable=True)  # Required for build type
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    pack = relationship("Pack", back_populates="grammars")


class GrammarTopic(Base):
    __tablename__ = "grammar_topics"

    id = Column(Integer, primary_key=True, index=True)
    pack_id = Column(Integer, ForeignKey("packs.id"), nullable=False)
    video_url = Column(String, nullable=True)  # Telegram video URL
    markdown_text = Column(String, nullable=True)  # Long explanation in markdown
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    pack = relationship("Pack", back_populates="grammar_topics")


class UserProgress(Base):
    __tablename__ = "user_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pack_id = Column(Integer, ForeignKey("packs.id"), nullable=False)
    best_score = Column(Integer, nullable=False)  # Best percentage (0-100)
    total_points = Column(Integer, default=0)     # Total points earned from this pack
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")
    pack = relationship("Pack")

    # Unique constraint: one progress record per user-pack combination
    __table_args__ = (UniqueConstraint('user_id', 'pack_id', name='unique_user_pack_progress'),)


class Translation(Base):
    __tablename__ = "translations"

    id = Column(Integer, primary_key=True, index=True)
    input_text = Column(String, nullable=False)
    target_language = Column(String, nullable=False)  # 'uz' or 'ru'
    output_text = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Unique constraint: same input + target language should return cached result
    __table_args__ = (UniqueConstraint('input_text', 'target_language', name='unique_translation'),)