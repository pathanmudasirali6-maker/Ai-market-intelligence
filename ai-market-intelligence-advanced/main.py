from fastapi import FastAPI, Query, BackgroundTasks
from database import get_db
from app.services import fetch_news
from app.utils import get_sentiment, extract_keywords, trend_score
from app.cache import cache
import logging
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['ai_market_intelligence']
raw_collection = db['raw_articles']
processed_collection = db['processed_articles']

app = FastAPI()

def ingest_job():
    articles = fetch_news()

    for art in articles:
        raw_collection.insert_one(art)

        content = art.get("title", "") + " " + str(art.get("description", ""))

        processed = {
            "title": art.get("title"),
            "sentiment": get_sentiment(content),
            "keywords": extract_keywords(content),
            "trend_score": trend_score(content)
        }
        processed_collection.insert_one(processed)

    logging.info("Background ingest completed")

@app.post("/ingest")
def ingest_data(background_tasks: BackgroundTasks):
    background_tasks.add_task(ingest_job)
    return {"message": "Ingestion started in background"}

@app.get("/trends")
def get_trends(days: int = Query(7)):
    if "trends" in cache:
        return cache["trends"]

    pipeline = [
        {"$unwind": "$keywords"},
        {"$group": {"_id": "$keywords", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    result = list(processed_collection.aggregate(pipeline))
    cache["trends"] = result
    return result

@app.get("/insights")
def insights():
    total = processed_collection.count_documents({})
    positive = processed_collection.count_documents({"sentiment": "positive"})
    negative = processed_collection.count_documents({"sentiment": "negative"})

    return {
        "total": total,
        "positive": positive,
        "negative": negative
    }

@app.get("/search")
def search(q: str):
    return list(processed_collection.find(
        {"keywords": {"$in": [q.lower()]}},
        {"_id": 0}
    ))

@app.get("/analytics/summary")
def summary():
    return {
        "total_records": processed_collection.count_documents({})
    }
