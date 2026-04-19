from fastapi import FastAPI, Query
from app.database import raw_collection, processed_collection
from app.services import fetch_news
from app.utils import get_sentiment, extract_keywords, trend_score

app = FastAPI()

@app.post("/ingest")
def ingest_data():
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

    return {"message": "Data Ingested Successfully"}

@app.get("/trends")
def get_trends(days: int = Query(7)):
    pipeline = [
        {"$unwind": "$keywords"},
        {"$group": {"_id": "$keywords", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    result = list(processed_collection.aggregate(pipeline))
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
    results = list(processed_collection.find(
        {"keywords": q.lower()},
        {"_id": 0}
    ))
    return results

@app.get("/analytics/summary")
def summary():
    return {
        "total_records": processed_collection.count_documents({})
    }
