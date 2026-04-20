from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Literal
from loguru import logger

from app.db.mongodb import get_database
from app.services.analytics import AnalyticsService
from app.models.schemas import (
    TrendsResponse, InsightsResponse, AnalyticsSummary, SearchResponse
)
from app.core.rate_limiter import limiter

router = APIRouter(tags=["Analytics"])


def get_analytics(db: AsyncIOMotorDatabase = Depends(get_database)) -> AnalyticsService:
    return AnalyticsService(db)


# ── Trends ───────────────────────────────────────────────────────────────────

@router.get(
    "/trends",
    response_model=TrendsResponse,
    summary="Get trending keywords",
    description=(
        "Returns the top trending keywords over the specified time window. "
        "Includes trend velocity (% change vs previous period) and sentiment distribution."
    ),
)
@limiter.limit("30/minute")
async def get_trends(
    request: Request,
    days: int = Query(7, ge=1, le=30, description="Time window in days"),
    top_n: int = Query(20, ge=5, le=50, description="Number of keywords to return"),
    analytics: AnalyticsService = Depends(get_analytics),
):
    try:
        return await analytics.get_trends(days=days, top_n=top_n)
    except Exception as e:
        logger.error(f"Trends error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Insights ─────────────────────────────────────────────────────────────────

@router.get(
    "/insights",
    response_model=InsightsResponse,
    summary="Aggregated market insights",
    description=(
        "Returns aggregated insights including sentiment breakdown, "
        "top sources, top categories, and time-series data with growth rates."
    ),
)
@limiter.limit("30/minute")
async def get_insights(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Analysis period in days"),
    analytics: AnalyticsService = Depends(get_analytics),
):
    try:
        return await analytics.get_insights(days=days)
    except Exception as e:
        logger.error(f"Insights error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Search ────────────────────────────────────────────────────────────────────

@router.get(
    "/search",
    summary="Full-text search across processed articles",
    description=(
        "Full-text search using MongoDB text indexes. "
        "Supports filtering by sentiment, category, and time window. "
        "Results ranked by relevance score."
    ),
)
@limiter.limit("30/minute")
async def search_articles(
    request: Request,
    q: str = Query(..., min_length=2, max_length=256, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Results per page"),
    sentiment: Optional[Literal["positive", "negative", "neutral"]] = Query(
        None, description="Filter by sentiment"
    ),
    category: Optional[str] = Query(None, description="Filter by category"),
    days: Optional[int] = Query(None, ge=1, le=90, description="Filter to last N days"),
    analytics: AnalyticsService = Depends(get_analytics),
):
    try:
        result = await analytics.search(
            query=q,
            page=page,
            page_size=page_size,
            sentiment=sentiment,
            category=category,
            days=days,
        )
        return result
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Analytics Summary ─────────────────────────────────────────────────────────

@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummary,
    summary="System-wide analytics summary",
    description=(
        "Returns comprehensive system statistics: "
        "total documents, processing rate, category breakdown, "
        "sentiment distribution, date range, and cache performance."
    ),
)
@limiter.limit("20/minute")
async def get_analytics_summary(
    request: Request,
    analytics: AnalyticsService = Depends(get_analytics),
):
    try:
        return await analytics.get_analytics_summary()
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
