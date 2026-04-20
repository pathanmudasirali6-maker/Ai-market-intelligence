import time
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger

from app.db.mongodb import get_database
from app.models.schemas import HealthResponse
from app.core.config import settings
from app.core.cache import cache

router = APIRouter(tags=["System"])

# Track startup time
_start_time = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service health status, database connectivity, and uptime.",
)
async def health_check(db: AsyncIOMotorDatabase = Depends(get_database)):
    try:
        await db.client.admin.command("ping")
        db_status = "connected"
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        db_status = "disconnected"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version=settings.APP_VERSION,
        database=db_status,
        uptime_seconds=round(time.time() - _start_time, 2),
    )


@router.get(
    "/",
    summary="API root",
    description="Welcome message and available endpoints.",
)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "ingest": "POST /ingest — Fetch & store data from NewsAPI",
            "trends": "GET /trends?days=7 — Trending keywords",
            "insights": "GET /insights?days=7 — Aggregated insights",
            "search": "GET /search?q=<keyword> — Full-text search",
            "summary": "GET /analytics/summary — System statistics",
            "health": "GET /health — Service health",
        },
        "cache_stats": cache.stats,
    }
