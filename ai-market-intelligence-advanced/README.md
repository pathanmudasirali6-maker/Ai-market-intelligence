# AI Market Intelligence API v2.0

Advanced market intelligence API with sentiment analysis, trend detection, keyword extraction, and caching.

## Features

- **Background ingestion** — fetch news by topic without blocking the API
- **Sentiment analysis** — positive / negative / neutral classification via TextBlob
- **Keyword extraction** — stopword-filtered, deduped keyword lists
- **Trend detection** — aggregated keyword frequency over time windows
- **TTL Caching** — fast repeated reads with automatic expiry
- **MongoDB** — Atlas-ready with indexes for fast queries
- **CORS enabled** — ready for frontend integration
- **Duplicate prevention** — URL-based deduplication on ingest
- **Full-text search** — search articles by keyword, sentiment, topic

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/health` | DB ping + status |
| POST | `/ingest?topic=ai` | Trigger background ingestion |
| GET | `/trends?days=7` | Top trending keywords |
| GET | `/insights?topic=ai` | Sentiment breakdown |
| GET | `/search?q=bitcoin` | Search by keyword |
| GET | `/articles/recent` | Latest ingested articles |
| GET | `/analytics/summary` | Overall stats |
| DELETE | `/data/clear?confirm=true` | Clear all data |

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your MONGO_URI and NEWS_API_KEY
```

### 3. Run locally
```bash
uvicorn main:app --reload
```

### 4. API Docs
Visit: `http://localhost:8000/docs`

## Deployment on Railway

1. Push to GitHub
2. Connect repo to Railway
3. Add environment variables:
   - `MONGO_URI` — MongoDB Atlas connection string
   - `NEWS_API_KEY` — from https://newsapi.org
4. Railway uses `Procfile` automatically

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGO_URI` | ✅ | MongoDB connection string |
| `DB_NAME` | ❌ | Database name (default: `market_db`) |
| `NEWS_API_KEY` | ✅ | NewsAPI.org API key |
