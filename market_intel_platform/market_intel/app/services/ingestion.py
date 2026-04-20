"""
Ingestion Service
Orchestrates: NewsAPI fetch → MongoDB raw_data → NLP processing → processed_data
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, BulkWriteError
from loguru import logger

from app.services.news_client import NewsAPIClient
from app.services.processor import processing_service
from app.models.schemas import IngestRequest


class IngestionService:

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def ingest(self, request: IngestRequest) -> Dict[str, Any]:
        """
        Full pipeline:
        1. Fetch articles from NewsAPI
        2. Bulk upsert raw_data (skip duplicates by URL)
        3. Bulk process and upsert processed_data
        """
        fetched = 0
        stored = 0
        processed = 0
        duplicates_skipped = 0

        async with NewsAPIClient() as client:
            # Decide fetch strategy
            if request.query:
                articles = await client.fetch_everything(
                    query=request.query,
                    page_size=request.page_size,
                    language=request.language,
                )
            elif request.category and request.category != "all":
                articles = await client.fetch_top_headlines(
                    category=request.category,
                    page_size=request.page_size,
                    language=request.language,
                )
            else:
                # Fetch multiple important categories concurrently
                articles = await client.fetch_multi_category(
                    categories=["business", "technology", "science", "health"],
                    page_size_each=max(request.page_size // 4, 5),
                )

        fetched = len(articles)
        logger.info(f"Fetched {fetched} articles from NewsAPI")

        if not articles:
            return {
                "fetched": 0, "stored": 0, "processed": 0,
                "duplicates_skipped": 0,
                "message": "No articles fetched from NewsAPI",
            }

        # ── Step 2: Store raw data ───────────────────────────────────────────
        raw_docs = [art.model_dump() for art in articles]
        for doc in raw_docs:
            doc["ingested_at"] = datetime.utcnow()

        inserted_ids = []
        for doc in raw_docs:
            try:
                result = await self.db.raw_data.insert_one(doc)
                inserted_ids.append(result.inserted_id)
                stored += 1
            except DuplicateKeyError:
                duplicates_skipped += 1
            except Exception as e:
                logger.warning(f"Failed to insert raw article: {e}")

        logger.info(f"Stored {stored} new articles | skipped {duplicates_skipped} duplicates")

        if not inserted_ids:
            return {
                "fetched": fetched,
                "stored": 0,
                "processed": 0,
                "duplicates_skipped": duplicates_skipped,
                "message": "All articles were duplicates. Nothing new to process.",
            }

        # ── Step 3: Process newly stored articles ───────────────────────────
        newly_stored = await self.db.raw_data.find(
            {"_id": {"$in": inserted_ids}}
        ).to_list(length=None)

        # Pre-build global keyword frequency for trend scoring
        global_freq = processing_service.build_keyword_frequency(newly_stored)

        processed_docs = []
        for raw_doc in newly_stored:
            result = processing_service.process_article(raw_doc, global_freq)
            if result:
                processed_docs.append(result)

        if processed_docs:
            try:
                # Upsert by raw_id to avoid double-processing
                for doc in processed_docs:
                    await self.db.processed_data.update_one(
                        {"raw_id": doc["raw_id"]},
                        {"$set": doc},
                        upsert=True,
                    )
                    processed += 1
            except Exception as e:
                logger.error(f"Bulk process insert error: {e}")

        logger.success(
            f"Ingestion complete | fetched={fetched} stored={stored} "
            f"processed={processed} duplicates={duplicates_skipped}"
        )

        return {
            "fetched": fetched,
            "stored": stored,
            "processed": processed,
            "duplicates_skipped": duplicates_skipped,
            "message": f"Successfully ingested and processed {processed} articles",
        }


async def get_ingestion_service(db: AsyncIOMotorDatabase) -> IngestionService:
    return IngestionService(db)
