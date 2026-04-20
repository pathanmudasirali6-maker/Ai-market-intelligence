# 🚀 AI-Powered Market Intelligence & Trend Analytics Platform

A **production-grade backend system** that ingests real-world news data from NewsAPI, performs NLP analysis (sentiment, keyword extraction, trend detection), stores everything in MongoDB Atlas, and exposes clean insights via a FastAPI REST API.

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CLIENT (Postman / Browser)                       │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       FastAPI Application                            │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Rate Limiter│  │  GZip Middle │  │   Request Logger         │  │
│  │  (slowapi)   │  │  ware        │  │   (loguru)               │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                        API Router                             │   │
│  │  POST /ingest  GET /trends  GET /insights                    │   │
│  │  GET /search   GET /analytics/summary  GET /health           │   │
│  └───────────────────────┬──────────────────────────────────────┘   │
│                          │                                           │
│  ┌───────────────────────▼──────────────────────────────────────┐   │
│  │                    Service Layer                               │   │
│  │                                                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐   │   │
│  │  │ Ingestion   │  │  Analytics  │  │   NLP Processor    │   │   │
│  │  │ Service     │  │  Service    │  │   (TextBlob)       │   │   │
│  │  └──────┬──────┘  └──────┬──────┘  └────────────────────┘   │   │
│  │         │                │                                    │   │
│  │  ┌──────▼──────┐  ┌──────▼──────┐                           │   │
│  │  │ NewsAPI     │  │  TTL Cache  │                           │   │
│  │  │ Client      │  │  (cachetools│                           │   │
│  │  │ (httpx)     │  │  )          │                           │   │
│  │  └─────────────┘  └─────────────┘                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ Motor (async)
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        MongoDB Atlas                                 │
│                                                                      │
│   ┌─────────────────────────┐    ┌─────────────────────────────┐   │
│   │      raw_data           │    │      processed_data          │   │
│   │  ─────────────────────  │    │  ───────────────────────── │   │
│   │  title, source, url     │    │  raw_id, sentiment          │   │
│   │  published_at, content  │    │  sentiment_score, keywords   │   │
│   │  category, author       │    │  score, trend_score         │   │
│   │  ingested_at            │    │  word_count, reading_time   │   │
│   │                         │    │  processed_at               │   │
│   │  Indexes:               │    │                             │   │
│   │  - url (unique)         │    │  Indexes:                   │   │
│   │  - published_at         │    │  - raw_id (unique)          │   │
│   │  - category             │    │  - sentiment, keywords      │   │
│   │  - TEXT (title+content) │    │  - trend_score              │   │
│   └─────────────────────────┘    │  - TEXT (title)             │   │
│                                  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Project Structure

```
market_intel/
├── main.py                     # FastAPI app factory, middleware, lifespan
├── requirements.txt            # All dependencies
├── Procfile                    # Gunicorn start command
├── render.yaml                 # Render deployment config
├── railway.toml                # Railway deployment config
├── pytest.ini                  # Test configuration
├── postman_collection.json     # Import into Postman for testing
├── .env.example                # Environment variable template
├── .gitignore
│
├── app/
│   ├── core/
│   │   ├── config.py           # Pydantic Settings (all env vars)
│   │   ├── logging.py          # Loguru structured logging setup
│   │   ├── cache.py            # In-memory TTL cache with stats
│   │   └── rate_limiter.py     # slowapi rate limiting
│   │
│   ├── db/
│   │   └── mongodb.py          # Motor async client + index creation
│   │
│   ├── models/
│   │   └── schemas.py          # All Pydantic v2 models (request/response)
│   │
│   ├── services/
│   │   ├── news_client.py      # NewsAPI async client with retry logic
│   │   ├── processor.py        # NLP: sentiment, keywords, scoring
│   │   ├── ingestion.py        # Pipeline orchestration
│   │   └── analytics.py        # Trends, insights, search, summary
│   │
│   └── api/
│       ├── __init__.py         # Router aggregator
│       └── endpoints/
│           ├── ingest.py       # POST /ingest
│           ├── analytics.py    # GET /trends /insights /search /analytics/summary
│           └── health.py       # GET /health GET /
│
└── tests/
    └── test_app.py             # Unit + integration tests
```

---

## ⚡ Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/market-intel.git
cd market-intel
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and fill in:
# - MONGODB_URL (MongoDB Atlas connection string)
# - NEWS_API_KEY  (get free key at https://newsapi.org)
```

### 3. Run Locally

```bash
python main.py
# Or with uvicorn directly:
uvicorn main:app --reload --port 8000
```

API docs available at: **http://localhost:8000/docs**

### 4. Run Tests

```bash
# Unit tests only (no DB needed):
pytest tests/ -v -k "not integration"

# Integration tests (requires MongoDB + .env):
pytest tests/ -v -m integration
```

---

## 📡 API Endpoints

### `POST /ingest`
Fetch articles from NewsAPI and run the full processing pipeline.

```json
// Request body
{
  "query": "artificial intelligence",   // optional: search query
  "category": "technology",             // optional: business|tech|science|health|sports
  "page_size": 20,                      // 1-100
  "language": "en"
}
// Query params: ?background=true  →  returns task_id for async execution
```

```json
// Response
{
  "status": "success",
  "fetched": 20,
  "stored": 18,
  "processed": 18,
  "duplicates_skipped": 2,
  "message": "Successfully ingested and processed 18 articles"
}
```

---

### `GET /trends?days=7&top_n=20`
Returns trending keywords with velocity and sentiment distribution.

```json
{
  "days": 7,
  "total_articles": 342,
  "keywords": [
    {
      "keyword": "artificial intelligence",
      "count": 47,
      "trend_velocity": 83.5,
      "categories": ["technology", "science"],
      "sentiment_distribution": {"positive": 62.5, "neutral": 25.0, "negative": 12.5}
    }
  ],
  "generated_at": "2024-01-15T12:00:00"
}
```

---

### `GET /insights?days=7`
Aggregated insights with time-series and growth rates.

```json
{
  "total_articles": 342,
  "period_days": 7,
  "sentiment": {
    "positive": 145, "negative": 72, "neutral": 125,
    "positive_pct": 42.4, "negative_pct": 21.1, "neutral_pct": 36.5
  },
  "top_sources": [{"source": "TechCrunch", "count": 28, "avg_score": 0.73}],
  "top_categories": [{"category": "technology", "count": 98, "avg_sentiment": 0.12}],
  "time_series": [
    {"date": "2024-01-09", "count": 45, "avg_sentiment_score": 0.08, "growth_rate": null},
    {"date": "2024-01-10", "count": 52, "avg_sentiment_score": 0.12, "growth_rate": 15.56}
  ],
  "avg_trend_score": 23.4,
  "avg_reading_time_minutes": 2.1
}
```

---

### `GET /search?q=<query>`
Full-text search with filters and pagination.

| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Search query (required, min 2 chars) |
| `page` | int | Page number (default: 1) |
| `page_size` | int | Results per page (1-50, default: 10) |
| `sentiment` | string | Filter: positive/negative/neutral |
| `category` | string | Filter by category |
| `days` | int | Filter to last N days |

---

### `GET /analytics/summary`
System-wide statistics.

```json
{
  "total_raw": 1250,
  "total_processed": 1238,
  "processing_rate_pct": 99.04,
  "categories": [{"category": "technology", "count": 412}],
  "sources_count": 87,
  "date_range": {"oldest": "2024-01-01T...", "newest": "2024-01-15T..."},
  "sentiment_breakdown": {"positive": 524, "negative": 231, "neutral": 483, ...},
  "cache_stats": {"hits": 142, "misses": 23, "hit_rate_pct": 86.06, ...},
  "avg_keywords_per_article": 7.3
}
```

---

### `GET /health`
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "uptime_seconds": 3621.5
}
```

---

## 🔥 Advanced Features Implemented

| Feature | Implementation |
|---------|----------------|
| **Background Tasks** | FastAPI `BackgroundTasks` on `POST /ingest?background=true` with task status tracking |
| **Caching** | `cachetools.TTLCache` — 3 separate cache instances (trends: 2min, insights: 5min, general: 5min) with hit-rate statistics |
| **Logging** | `loguru` — structured console + daily rotating file logs + error-only log, all async-safe |
| **Rate Limiting** | `slowapi` — 60 req/min default, 10 req/min on ingest |
| **Data Validation** | Pydantic v2 full validation pipeline on all inputs and outputs |

---

## 🚀 Deployment

### Render (Recommended)
1. Push repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service → Connect GitHub
3. Set environment variables in Render dashboard:
   - `MONGODB_URL` → Your MongoDB Atlas URI
   - `NEWS_API_KEY` → Your NewsAPI key
4. Deploy — `render.yaml` handles the rest

### Railway
1. Push repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variables in Railway dashboard
4. Deploy — `railway.toml` handles the rest

---

## 🔑 Getting API Keys

**NewsAPI** (Free: 100 req/day, 1000 articles/request)
1. Go to [https://newsapi.org/register](https://newsapi.org/register)
2. Sign up for a free account
3. Copy your API key to `.env`

**MongoDB Atlas** (Free tier: 512MB)
1. Go to [https://cloud.mongodb.com](https://cloud.mongodb.com)
2. Create a free M0 cluster
3. Create a database user
4. Whitelist your IP (or 0.0.0.0/0 for cloud deployment)
5. Copy the connection string to `.env`

---

## 📊 Sample Output

```bash
# Ingest latest tech news
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"category": "technology", "page_size": 20}'

# Get trending keywords (last 7 days)
curl "http://localhost:8000/trends?days=7&top_n=10"

# Search for AI articles
curl "http://localhost:8000/search?q=artificial+intelligence&sentiment=positive&page_size=5"

# Get analytics summary
curl "http://localhost:8000/analytics/summary"
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.111 |
| Database | MongoDB Atlas + Motor (async) |
| NLP | TextBlob + NLTK |
| HTTP Client | httpx (async with retry) |
| Rate Limiting | slowapi |
| Caching | cachetools TTLCache |
| Logging | loguru |
| Validation | Pydantic v2 |
| Production Server | Gunicorn + Uvicorn workers |
| Testing | pytest + httpx AsyncClient |

---

## 📝 License

MIT
