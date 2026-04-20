from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List, Literal
from datetime import datetime
from bson import ObjectId
import re


# ─── Helpers ────────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.utcnow()


class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if ObjectId.is_valid(str(v)):
            return str(v)
        raise ValueError(f"Invalid ObjectId: {v}")


# ─── Raw Data Models ────────────────────────────────────────────────────────

class RawArticleBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=512)
    source: str = Field(..., min_length=1, max_length=128)
    url: str = Field(..., min_length=10)
    published_at: datetime
    content: Optional[str] = Field(None, max_length=10000)
    description: Optional[str] = Field(None, max_length=1000)
    author: Optional[str] = Field(None, max_length=128)
    category: str = Field(default="general", max_length=64)
    image_url: Optional[str] = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        return re.sub(r'\s+', ' ', v).strip()

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        return v.lower().strip()


class RawArticleCreate(RawArticleBase):
    pass


class RawArticleDB(RawArticleBase):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    ingested_at: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class RawArticleResponse(RawArticleBase):
    id: str
    ingested_at: datetime

    model_config = {"populate_by_name": True}


# ─── Processed Data Models ──────────────────────────────────────────────────

SentimentType = Literal["positive", "negative", "neutral"]


class ProcessedArticleBase(BaseModel):
    raw_id: str
    title: str
    source: str
    published_at: datetime
    category: str
    sentiment: SentimentType
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    subjectivity: float = Field(..., ge=0.0, le=1.0)
    keywords: List[str] = Field(default_factory=list)
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance/quality score")
    trend_score: int = Field(default=0, ge=0)
    word_count: int = Field(default=0, ge=0)
    reading_time_minutes: float = Field(default=0.0, ge=0)


class ProcessedArticleDB(ProcessedArticleBase):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    processed_at: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class ProcessedArticleResponse(ProcessedArticleBase):
    id: str
    processed_at: datetime

    model_config = {"populate_by_name": True}


# ─── API Request/Response Models ────────────────────────────────────────────

class IngestRequest(BaseModel):
    query: Optional[str] = Field(None, description="Search query for news", max_length=256)
    category: Optional[str] = Field(None, description="News category", max_length=64)
    page_size: int = Field(default=20, ge=1, le=100)
    language: str = Field(default="en", max_length=5)


class IngestResponse(BaseModel):
    status: str
    fetched: int
    stored: int
    processed: int
    duplicates_skipped: int
    message: str
    task_id: Optional[str] = None


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    data: List


class TrendKeyword(BaseModel):
    keyword: str
    count: int
    trend_velocity: float = Field(description="Growth rate compared to previous period")
    categories: List[str] = Field(default_factory=list)
    sentiment_distribution: dict = Field(default_factory=dict)


class TrendsResponse(BaseModel):
    days: int
    total_articles: int
    keywords: List[TrendKeyword]
    generated_at: datetime = Field(default_factory=utcnow)


class SentimentStats(BaseModel):
    positive: int
    negative: int
    neutral: int
    positive_pct: float
    negative_pct: float
    neutral_pct: float


class TimeSeriesPoint(BaseModel):
    date: str
    count: int
    avg_sentiment_score: float
    growth_rate: Optional[float] = None


class InsightsResponse(BaseModel):
    total_articles: int
    period_days: int
    sentiment: SentimentStats
    top_sources: List[dict]
    top_categories: List[dict]
    time_series: List[TimeSeriesPoint]
    avg_trend_score: float
    avg_reading_time_minutes: float
    generated_at: datetime = Field(default_factory=utcnow)


class AnalyticsSummary(BaseModel):
    total_raw: int
    total_processed: int
    processing_rate_pct: float
    categories: List[dict]
    sources_count: int
    date_range: dict
    sentiment_breakdown: SentimentStats
    cache_stats: dict
    avg_keywords_per_article: float
    generated_at: datetime = Field(default_factory=utcnow)


class SearchResponse(PaginatedResponse):
    query: str
    search_time_ms: float


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int
    timestamp: datetime = Field(default_factory=utcnow)


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    uptime_seconds: float
    timestamp: datetime = Field(default_factory=utcnow)
