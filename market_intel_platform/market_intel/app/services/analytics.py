"""
Analytics Service
- Trend detection (keyword frequency + velocity)
- Sentiment aggregation
- Time-series analysis with growth rates
- Comprehensive insights aggregation
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from collections import defaultdict, Counter
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger

from app.models.schemas import (
    TrendKeyword, TrendsResponse, InsightsResponse,
    SentimentStats, TimeSeriesPoint, AnalyticsSummary,
)
from app.core.cache import trends_cache, insights_cache


class AnalyticsService:

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    # ── Trend Detection ──────────────────────────────────────────────────────

    async def get_trends(self, days: int = 7, top_n: int = 20) -> TrendsResponse:
        cache_key = f"trends:{days}:{top_n}"
        cached = trends_cache.get(cache_key)
        if cached:
            return cached

        since = datetime.utcnow() - timedelta(days=days)
        prev_since = since - timedelta(days=days)

        pipeline = [
            {"$match": {"published_at": {"$gte": since}}},
            {"$unwind": "$keywords"},
            {"$match": {"keywords": {"$ne": ""}}},
            {
                "$group": {
                    "_id": "$keywords",
                    "count": {"$sum": 1},
                    "categories": {"$addToSet": "$category"},
                    "sentiments": {"$push": "$sentiment"},
                    "avg_trend_score": {"$avg": "$trend_score"},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": top_n},
        ]

        current_kw_docs = await self.db.processed_data.aggregate(pipeline).to_list(length=None)

        # Previous period for velocity calculation
        prev_pipeline = [
            {"$match": {"published_at": {"$gte": prev_since, "$lt": since}}},
            {"$unwind": "$keywords"},
            {"$group": {"_id": "$keywords", "count": {"$sum": 1}}},
        ]
        prev_docs = await self.db.processed_data.aggregate(prev_pipeline).to_list(length=None)
        prev_freq: Dict[str, int] = {d["_id"]: d["count"] for d in prev_docs}

        total_articles = await self.db.processed_data.count_documents(
            {"published_at": {"$gte": since}}
        )

        keywords = []
        for doc in current_kw_docs:
            kw = doc["_id"]
            current_count = doc["count"]
            prev_count = prev_freq.get(kw, 0)
            velocity = (
                round((current_count - prev_count) / max(prev_count, 1) * 100, 2)
                if prev_count > 0 else 100.0
            )

            # Sentiment distribution
            sentiments = doc.get("sentiments", [])
            sentiment_dist = {}
            if sentiments:
                total = len(sentiments)
                sent_counter = Counter(sentiments)
                sentiment_dist = {
                    k: round(v / total * 100, 1)
                    for k, v in sent_counter.items()
                }

            keywords.append(TrendKeyword(
                keyword=kw,
                count=current_count,
                trend_velocity=velocity,
                categories=doc.get("categories", [])[:5],
                sentiment_distribution=sentiment_dist,
            ))

        result = TrendsResponse(
            days=days,
            total_articles=total_articles,
            keywords=keywords,
        )
        trends_cache.set(cache_key, result)
        return result

    # ── Insights ─────────────────────────────────────────────────────────────

    async def get_insights(self, days: int = 7) -> InsightsResponse:
        cache_key = f"insights:{days}"
        cached = insights_cache.get(cache_key)
        if cached:
            return cached

        since = datetime.utcnow() - timedelta(days=days)

        # Sentiment breakdown
        sent_pipeline = [
            {"$match": {"published_at": {"$gte": since}}},
            {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}},
        ]
        sent_docs = await self.db.processed_data.aggregate(sent_pipeline).to_list(length=None)
        sent_map = {d["_id"]: d["count"] for d in sent_docs}
        pos = sent_map.get("positive", 0)
        neg = sent_map.get("negative", 0)
        neu = sent_map.get("neutral", 0)
        total = pos + neg + neu or 1

        sentiment = SentimentStats(
            positive=pos, negative=neg, neutral=neu,
            positive_pct=round(pos / total * 100, 2),
            negative_pct=round(neg / total * 100, 2),
            neutral_pct=round(neu / total * 100, 2),
        )

        # Top sources
        sources_pipeline = [
            {"$match": {"published_at": {"$gte": since}}},
            {"$group": {
                "_id": "$source",
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$score"},
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        top_sources = await self.db.processed_data.aggregate(sources_pipeline).to_list(length=None)

        # Top categories
        cat_pipeline = [
            {"$match": {"published_at": {"$gte": since}}},
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1},
                "avg_sentiment": {"$avg": "$sentiment_score"},
            }},
            {"$sort": {"count": -1}},
        ]
        top_categories = await self.db.processed_data.aggregate(cat_pipeline).to_list(length=None)

        # Time series (per day)
        time_series_pipeline = [
            {"$match": {"published_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$published_at",
                        }
                    },
                    "count": {"$sum": 1},
                    "avg_sentiment_score": {"$avg": "$sentiment_score"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        ts_docs = await self.db.processed_data.aggregate(time_series_pipeline).to_list(length=None)

        # Compute growth rates
        time_series = []
        for i, ts in enumerate(ts_docs):
            growth = None
            if i > 0 and ts_docs[i - 1]["count"] > 0:
                growth = round(
                    (ts["count"] - ts_docs[i - 1]["count"]) / ts_docs[i - 1]["count"] * 100,
                    2
                )
            time_series.append(TimeSeriesPoint(
                date=ts["_id"],
                count=ts["count"],
                avg_sentiment_score=round(ts["avg_sentiment_score"], 4),
                growth_rate=growth,
            ))

        # Aggregated metrics
        agg_pipeline = [
            {"$match": {"published_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": None,
                    "avg_trend": {"$avg": "$trend_score"},
                    "avg_reading": {"$avg": "$reading_time_minutes"},
                    "total": {"$sum": 1},
                }
            }
        ]
        agg_docs = await self.db.processed_data.aggregate(agg_pipeline).to_list(length=1)
        agg = agg_docs[0] if agg_docs else {}

        result = InsightsResponse(
            total_articles=total,
            period_days=days,
            sentiment=sentiment,
            top_sources=[
                {"source": d["_id"], "count": d["count"], "avg_score": round(d["avg_score"], 4)}
                for d in top_sources
            ],
            top_categories=[
                {"category": d["_id"], "count": d["count"],
                 "avg_sentiment": round(d["avg_sentiment"], 4)}
                for d in top_categories
            ],
            time_series=time_series,
            avg_trend_score=round(agg.get("avg_trend", 0), 2),
            avg_reading_time_minutes=round(agg.get("avg_reading", 0), 2),
        )
        insights_cache.set(cache_key, result)
        return result

    # ── Summary Statistics ────────────────────────────────────────────────────

    async def get_analytics_summary(self) -> Dict[str, Any]:
        from app.core.cache import cache

        total_raw = await self.db.raw_data.count_documents({})
        total_processed = await self.db.processed_data.count_documents({})
        processing_rate = round(total_processed / max(total_raw, 1) * 100, 2)

        # Category breakdown
        cat_pipeline = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        categories = await self.db.processed_data.aggregate(cat_pipeline).to_list(length=None)

        # Unique sources count
        sources_count = len(await self.db.processed_data.distinct("source"))

        # Date range
        oldest = await self.db.raw_data.find_one({}, sort=[("published_at", 1)])
        newest = await self.db.raw_data.find_one({}, sort=[("published_at", -1)])

        # Sentiment breakdown (all time)
        sent_pipeline = [
            {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}}
        ]
        sent_docs = await self.db.processed_data.aggregate(sent_pipeline).to_list(length=None)
        sent_map = {d["_id"]: d["count"] for d in sent_docs}
        total_s = sum(sent_map.values()) or 1

        sentiment_breakdown = SentimentStats(
            positive=sent_map.get("positive", 0),
            negative=sent_map.get("negative", 0),
            neutral=sent_map.get("neutral", 0),
            positive_pct=round(sent_map.get("positive", 0) / total_s * 100, 2),
            negative_pct=round(sent_map.get("negative", 0) / total_s * 100, 2),
            neutral_pct=round(sent_map.get("neutral", 0) / total_s * 100, 2),
        )

        # Avg keywords per article
        kw_pipeline = [
            {"$project": {"kw_count": {"$size": "$keywords"}}},
            {"$group": {"_id": None, "avg": {"$avg": "$kw_count"}}},
        ]
        kw_docs = await self.db.processed_data.aggregate(kw_pipeline).to_list(length=1)
        avg_kw = round(kw_docs[0]["avg"], 2) if kw_docs else 0.0

        return AnalyticsSummary(
            total_raw=total_raw,
            total_processed=total_processed,
            processing_rate_pct=processing_rate,
            categories=[
                {"category": d["_id"], "count": d["count"]}
                for d in categories
            ],
            sources_count=sources_count,
            date_range={
                "oldest": oldest["published_at"].isoformat() if oldest else None,
                "newest": newest["published_at"].isoformat() if newest else None,
            },
            sentiment_breakdown=sentiment_breakdown,
            cache_stats=cache.stats,
            avg_keywords_per_article=avg_kw,
        )

    # ── Full-Text Search ──────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
        sentiment: Optional[str] = None,
        category: Optional[str] = None,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        import time
        start = time.time()

        match_filter: Dict[str, Any] = {
            "$text": {"$search": query}
        }
        if sentiment:
            match_filter["sentiment"] = sentiment
        if category:
            match_filter["category"] = category
        if days:
            since = datetime.utcnow() - timedelta(days=days)
            match_filter["published_at"] = {"$gte": since}

        total = await self.db.processed_data.count_documents(match_filter)
        skip = (page - 1) * page_size

        cursor = self.db.processed_data.find(
            match_filter,
            {"score_field": {"$meta": "textScore"}},
        ).sort(
            [("score_field", {"$meta": "textScore"}), ("published_at", -1)]
        ).skip(skip).limit(page_size)

        docs = await cursor.to_list(length=page_size)

        # Serialize ObjectId
        results = []
        for doc in docs:
            doc["id"] = str(doc.pop("_id"))
            doc.pop("score_field", None)
            if "published_at" in doc:
                doc["published_at"] = doc["published_at"].isoformat()
            if "processed_at" in doc:
                doc["processed_at"] = doc["processed_at"].isoformat()
            results.append(doc)

        elapsed_ms = round((time.time() - start) * 1000, 2)
        total_pages = max(1, -(-total // page_size))  # ceiling division

        return {
            "query": query,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "search_time_ms": elapsed_ms,
            "data": results,
        }
