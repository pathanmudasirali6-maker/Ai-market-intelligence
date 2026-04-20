from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from loguru import logger
from app.core.config import settings
from typing import Optional


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    async def connect(cls):
        logger.info(f"Connecting to MongoDB | db={settings.MONGODB_DB_NAME}")
        try:
            cls.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000,
                maxPoolSize=20,
                minPoolSize=5,
            )
            # Verify connection
            await cls.client.admin.command("ping")
            cls.db = cls.client[settings.MONGODB_DB_NAME]
            await cls._create_indexes()
            logger.success("MongoDB connected successfully")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise

    @classmethod
    async def disconnect(cls):
        if cls.client:
            cls.client.close()
            logger.info("MongoDB disconnected")

    @classmethod
    async def _create_indexes(cls):
        """Create all necessary indexes for performance."""
        db = cls.db

        # raw_data indexes
        await db.raw_data.create_index([("url", ASCENDING)], unique=True, background=True)
        await db.raw_data.create_index([("published_at", DESCENDING)], background=True)
        await db.raw_data.create_index([("category", ASCENDING)], background=True)
        await db.raw_data.create_index([("source", ASCENDING)], background=True)
        await db.raw_data.create_index(
            [("title", TEXT), ("content", TEXT)],
            background=True,
            name="text_search_idx"
        )

        # processed_data indexes
        await db.processed_data.create_index([("raw_id", ASCENDING)], unique=True, background=True)
        await db.processed_data.create_index([("published_at", DESCENDING)], background=True)
        await db.processed_data.create_index([("sentiment", ASCENDING)], background=True)
        await db.processed_data.create_index([("keywords", ASCENDING)], background=True)
        await db.processed_data.create_index([("trend_score", DESCENDING)], background=True)
        await db.processed_data.create_index(
            [("title", TEXT)],
            background=True,
            name="processed_text_idx"
        )

        logger.info("Database indexes created/verified")

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        if cls.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return cls.db


mongodb = MongoDB()


async def get_database() -> AsyncIOMotorDatabase:
    return mongodb.get_db()
