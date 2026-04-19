from fastapi import FastAPI, Query, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import get_db, raw_collection, processed_collection
from services import fetch_news, fetch_news_by_topic
from utils import get_sentiment, extract_keywords, trend_score, summarize_text
from cache import cache, get_cached, set_cached
import logging
from datetime import datetime, timedelta
from typing import Optional
from pymongo import DESCENDING

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Market Intelligence API",
    description="Advanced market intelligence with sentiment analysis, trend detection, and keyword extraction.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Background Jobs ────────────────────────────────────────────────

def ingest_job(topic: str = "technology"):
    try:
        articles = fetch_news_by_topic(topic)
        inserted = 0

        for art in articles:
            # Avoid duplicates by URL
            if raw_collection.find_one({"url": art.get("url")}):
                continue

            art["ingested_at"] = datetime.utcnow()
            raw_collection.insert_one(art)

            content = art.get("title", "") + " " + str(art.get("description", ""))

            processed = {
                "url": art.get("url"),
                "title": art.get("title"),
                "source": art.get("source", {}).get("name", "unknown"),
                "published_at": art.get("publishedAt"),
                "sentiment": get_sentiment(content),
                "keywords": extract_keywords(content),
                "trend_score": trend_score(content),
                "summary": summarize_text(content),
                "ingested_at": datetime.utcnow(),
                "topic": topic
            }
            processed_collection.insert_one(processed)
            inserted += 1

        logger.info(f"Ingest completed: {inserted} new articles for topic='{topic}'")
    except Exception as e:
        logger.error(f"Ingest job failed: {e}")


# ─── Endpoints ──────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "AI Market Intelligence API v2.0"}


@app.get("/health", tags=["Health"])
def health():
    try:
        raw_collection.database.client.admin.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    return {"status": "ok", "database": db_status, "timestamp": datetime.utcnow()}


@app.post("/ingest", tags=["Ingestion"])
def ingest_data(background_tasks: BackgroundTasks, topic: str = Query("technology")):
    background_tasks.add_task(ingest_job, topic)
    return {"message": f"Ingestion started for topic='{topic}'"}


@app.get("/trends", tags=["Analytics"])
def get_trends(days: int = Query(7, ge=1, le=90)):
    cache_key = f"trends_{days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    since = datetime.utcnow() - timedelta(days=days)
    pipeline = [
        {"$match": {"ingested_at": {"$gte": since}}},
        {"$unwind": "$keywords"},
        {"$group": {"_id": "$keywords", "count": {"$sum": 1}, "avg_trend_score": {"$avg": "$trend_score"}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
        {"$project": {"keyword": "$_id", "count": 1, "avg_trend_score": {"$round": ["$avg_trend_score", 2]}, "_id": 0}}
    ]
    result = list(processed_collection.aggregate(pipeline))
    set_cached(cache_key, result, ttl=180)
    return result


@app.get("/insights", tags=["Analytics"])
def insights(topic: Optional[str] = Query(None)):
    cache_key = f"insights_{topic or 'all'}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    match = {"topic": topic} if topic else {}
    total = processed_collection.count_documents(match)
    positive = processed_collection.count_documents({**match, "sentiment": "positive"})
    negative = processed_collection.count_documents({**match, "sentiment": "negative"})
    neutral = processed_collection.count_documents({**match, "sentiment": "neutral"})

    result = {
        "topic": topic or "all",
        "total": total,
        "sentiment_breakdown": {
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "positive_pct": round((positive / total * 100), 1) if total else 0,
            "negative_pct": round((negative / total * 100), 1) if total else 0,
        },
        "generated_at": datetime.utcnow().isoformat()
    }
    set_cached(cache_key, result, ttl=120)
    return result


@app.get("/search", tags=["Search"])
def search(
    q: str = Query(..., min_length=1),
    sentiment: Optional[str] = Query(None, pattern="^(positive|negative|neutral)$"),
    topic: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0)
):
    query = {"keywords": {"$in": [q.strip("'").lower()]}}
    if sentiment:
        query["sentiment"] = sentiment
    if topic:
        query["topic"] = topic

    projection = {"_id": 0}
    results = list(
        processed_collection.find(query, projection)
        .sort("ingested_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )

    if not results:
        return {"results": [], "count": 0, "query": q}

    return {"results": results, "count": len(results), "query": q}


@app.get("/articles/recent", tags=["Articles"])
def recent_articles(limit: int = Query(10, ge=1, le=50), topic: Optional[str] = Query(None)):
    match = {"topic": topic} if topic else {}
    articles = list(
        processed_collection.find(match, {"_id": 0})
        .sort("ingested_at", DESCENDING)
        .limit(limit)
    )
    return {"articles": articles, "count": len(articles)}


@app.get("/analytics/summary", tags=["Analytics"])
def summary():
    cache_key = "analytics_summary"
    cached = get_cached(cache_key)
    if cached:
        return cached

    total = processed_collection.count_documents({})
    topics = processed_collection.distinct("topics") if total else []
    last_article = processed_collection.find_one({}, {"_id": 0, "ingested_at": 1}, sort=[("ingested_at", DESCENDING)])

    result = {
        "total_records": total,
        "raw_records": raw_collection.count_documents({}),
        "last_ingested": last_article["ingested_at"].isoformat() if last_article else None,
        "available_topics": list(processed_collection.distinct("topic")),
    }
    set_cached(cache_key, result, ttl=60)
    return result


@app.delete("/data/clear", tags=["Admin"])
def clear_data(confirm: bool = Query(False)):
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass ?confirm=true to delete all data.")
    raw_collection.delete_many({})
    processed_collection.delete_many({})
    cache.clear()
    return {"message": "All data cleared."}
