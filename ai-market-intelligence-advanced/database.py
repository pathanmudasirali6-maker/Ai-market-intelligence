from pymongo import MongoClient, ASCENDING, DESCENDING
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "market_db")

# Lazy client — does NOT ping on startup, connects on first actual use
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]

raw_collection = db["raw_data"]
processed_collection = db["processed_data"]


def setup_indexes():
    """Create indexes — called from /health endpoint, not at import time."""
    try:
        raw_collection.create_index([("url", ASCENDING)], unique=True, sparse=True)
        processed_collection.create_index([("url", ASCENDING)], unique=True, sparse=True)
        processed_collection.create_index([("ingested_at", DESCENDING)])
        processed_collection.create_index([("sentiment", ASCENDING)])
        processed_collection.create_index([("keywords", ASCENDING)])
        processed_collection.create_index([("topic", ASCENDING)])
        logger.info("MongoDB indexes ensured.")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")


def get_db():
    """Returns the database instance."""
    return db
