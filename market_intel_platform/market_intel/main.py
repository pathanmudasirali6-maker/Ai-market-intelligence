"""
Market Intelligence Platform — FastAPI Application
Production-grade backend with:
  - NewsAPI data ingestion
  - MongoDB Atlas storage
  - NLP processing (sentiment, keywords, trend scoring)
  - Rate limiting (slowapi)
  - In-memory TTL caching
  - Structured logging (loguru)
  - Background tasks
  - OpenAPI/Swagger docs
"""
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.rate_limiter import limiter, rate_limit_exceeded_handler
from app.db.mongodb import mongodb
from app.api import api_router

# Create logs directory
os.makedirs("logs", exist_ok=True)

# Initialize logging
setup_logging()


# ── Lifespan (startup/shutdown) ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: connect DB on start, disconnect on stop."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await mongodb.connect()
    logger.success("Application startup complete")
    yield
    logger.info("Shutting down application...")
    await mongodb.disconnect()
    logger.info("Shutdown complete")


# ── App Factory ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
## 🚀 AI-Powered Market Intelligence & Trend Analytics Platform

A production-grade backend system that ingests real-world news data,
performs NLP analysis, and exposes actionable insights via a clean REST API.

### Features
- **Data Ingestion**: Fetches live articles from NewsAPI across multiple categories
- **NLP Processing**: Sentiment analysis, keyword extraction, trend scoring
- **Trend Detection**: Identifies viral keywords with velocity tracking
- **Time-Series**: Day-by-day article counts with growth rates
- **Full-Text Search**: MongoDB text-indexed search with relevance ranking
- **Caching**: In-memory TTL cache with hit-rate statistics
- **Rate Limiting**: 60 requests/minute per IP
- **Background Tasks**: Non-blocking ingestion via FastAPI BackgroundTasks
- **Structured Logging**: Loguru-powered daily rotating logs

### Pipeline
`NewsAPI → Data Ingestion → MongoDB (raw_data) → NLP Processing → MongoDB (processed_data) → FastAPI`
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        contact={
            "name": "Market Intel API",
            "url": "https://github.com/yourusername/market-intel",
        },
        license_info={
            "name": "MIT",
        },
    )

    # ── Middleware ───────────────────────────────────────────────────────────

    # Rate limiter state
    app.state.limiter = limiter

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip compression for large responses
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Exception Handlers ───────────────────────────────────────────────────

    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception | path={request.url.path} | {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
                "status_code": 500,
            },
        )

    # ── Request Logging Middleware ───────────────────────────────────────────

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = round((time.time() - start) * 1000, 2)
        logger.info(
            f"{request.method} {request.url.path} | "
            f"status={response.status_code} | {duration}ms | "
            f"ip={request.client.host if request.client else 'unknown'}"
        )
        response.headers["X-Process-Time"] = f"{duration}ms"
        response.headers["X-API-Version"] = settings.APP_VERSION
        return response

    # ── Routes ───────────────────────────────────────────────────────────────

    app.include_router(api_router)

    return app


app = create_app()


# ── Entry point for direct execution ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
        access_log=False,  # We handle this via middleware
    )
