from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserBase(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    telegram_id: int
    phone_number: str


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class User(UserBase):
    id: int
    telegram_id: int
    phone_number: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuthRequest(BaseModel):
    phone_number: str
    code: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UsersResponse(BaseModel):
    users: List[User]


class PackTypeEnum(str, Enum):
    GRAMMAR = "grammar"
    WORD = "word"


class GrammarTypeEnum(str, Enum):
    FILL = "fill"
    BUILD = "build"


class PackBase(BaseModel):
    title: str
    type: PackTypeEnum
    word_count: Optional[int] = None


class PackCreate(PackBase):
    lesson_id: int


class PackUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[PackTypeEnum] = None
    word_count: Optional[int] = None


class Pack(PackBase):
    id: int
    lesson_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LessonBase(BaseModel):
    title: str
    description: Optional[str] = None


class LessonCreate(LessonBase):
    module_id: int


class LessonUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class Lesson(LessonBase):
    id: int
    module_id: int
    packs: List[Pack] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ModuleBase(BaseModel):
    title: str


class ModuleCreate(ModuleBase):
    pass


class ModuleUpdate(BaseModel):
    title: Optional[str] = None


class Module(ModuleBase):
    id: int
    lessons: List[Lesson] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LessonsResponse(BaseModel):
    modules: List[Module]


class WordBase(BaseModel):
    audio_url: Optional[str] = None
    ru_text: Optional[str] = None
    uz_text: Optional[str] = None


class WordCreate(WordBase):
    pack_id: int


class WordUpdate(BaseModel):
    audio_url: Optional[str] = None
    ru_text: Optional[str] = None
    uz_text: Optional[str] = None


class Word(WordBase):
    id: int
    pack_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GrammarBase(BaseModel):
    type: GrammarTypeEnum
    question_text: Optional[str] = None
    options: Optional[List[str]] = None  # List of 4 options
    correct_option: Optional[int] = None  # Index 0-3
    sentence: Optional[str] = None


class GrammarCreate(GrammarBase):
    pack_id: int


class GrammarUpdate(BaseModel):
    type: Optional[GrammarTypeEnum] = None
    question_text: Optional[str] = None
    options: Optional[List[str]] = None
    correct_option: Optional[int] = None
    sentence: Optional[str] = None


class Grammar(GrammarBase):
    id: int
    pack_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PackWithQuizData(PackBase):
    id: int
    lesson_id: int
    words: List[Word] = []
    grammars: List[Grammar] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QuizResponse(BaseModel):
    word_packs: List[PackWithQuizData]
    grammar_packs: List[PackWithQuizData]


class GrammarTopicBase(BaseModel):
    video_url: Optional[str] = None
    markdown_text: Optional[str] = None


class GrammarTopicCreate(GrammarTopicBase):
    pack_id: int


class GrammarTopicUpdate(BaseModel):
    video_url: Optional[str] = None
    markdown_text: Optional[str] = None


class GrammarTopic(GrammarTopicBase):
    id: int
    pack_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GrammarTopicSimple(BaseModel):
    id: int
    pack_id: int
    video_url: Optional[str] = None
    markdown_text: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GrammarTopicsResponse(BaseModel):
    topics: List[GrammarTopicSimple]


class ProgressSubmit(BaseModel):
    pack_id: int
    score: int  # Percentage 0-100


class ProgressResponse(BaseModel):
    points_earned: int
    total_points: int
    best_score: int


class PackProgress(BaseModel):
    pack_id: int
    lesson_id: int
    best_score: int
    total_points: int


class UserProgressResponse(BaseModel):
    progress: List[PackProgress]


class LeaderboardUser(BaseModel):
    user_id: int
    first_name: str
    last_name: Optional[str] = None
    total_points: int
    rank: int


class CurrentUserRank(BaseModel):
    rank: int
    total_points: int


class LeaderboardResponse(BaseModel):
    leaderboard: List[LeaderboardUser]
    current_user: CurrentUserRank
    last_updated: datetime
    next_update: datetime
    total_users: int


class TranslationRequest(BaseModel):
    text: str
    target_language: str  # 'uz' or 'ru'


class TranslationResponse(BaseModel):
    input_text: str
    target_language: str
    output_text: str
    from_cache: bool


# Subscription Schemas
class UserSubscriptionBase(BaseModel):
    start_date: datetime
    end_date: datetime
    amount: float
    currency: str = "USD"
    notes: Optional[str] = None


class UserSubscriptionCreate(UserSubscriptionBase):
    user_id: int


class UserSubscriptionUpdate(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class UserSubscription(UserSubscriptionBase):
    id: int
    user_id: int
    is_active: bool
    created_by_admin_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionStatus(BaseModel):
    has_premium: bool
    subscription: Optional[dict] = None
    message: str


class FinancialStats(BaseModel):
    total_revenue: float
    monthly_revenue: float
    yearly_revenue: float
    active_subscriptions: int
    total_paid_subscriptions: int
    average_subscription_value: float
    revenue_by_month: List[dict]


# Business Profile Schemas
class BusinessProfileBase(BaseModel):
    telegram_url: Optional[str] = None
    instagram_url: Optional[str] = None
    website_url: Optional[str] = None
    support_email: Optional[str] = None
    required_app_version: str = "1.0.0"
    company_name: Optional[str] = None


class BusinessProfileCreate(BusinessProfileBase):
    pass


class BusinessProfileUpdate(BaseModel):
    telegram_url: Optional[str] = None
    instagram_url: Optional[str] = None
    website_url: Optional[str] = None
    support_email: Optional[str] = None
    required_app_version: Optional[str] = None
    company_name: Optional[str] = None


class BusinessProfile(BusinessProfileBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True