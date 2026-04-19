from cachetools import TTLCache
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

# Main cache: up to 200 items, default 5-minute TTL
cache = TTLCache(maxsize=200, ttl=300)


def get_cached(key: str) -> Optional[Any]:
    """Retrieve a value from cache. Returns None on miss."""
    try:
        value = cache[key]
        logger.debug(f"Cache HIT: {key}")
        return value
    except KeyError:
        logger.debug(f"Cache MISS: {key}")
        return None


def set_cached(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """
    Store a value in cache.
    If ttl is provided, uses a separate short-lived cache entry approach
    by storing with a ttl-tagged key. For simplicity, we use the global cache.
    """
    try:
        cache[key] = value
        logger.debug(f"Cache SET: {key}")
    except Exception as e:
        logger.warning(f"Cache set failed for key '{key}': {e}")


def invalidate(key: str) -> None:
    """Remove a single key from the cache."""
    try:
        del cache[key]
        logger.debug(f"Cache INVALIDATED: {key}")
    except KeyError:
        pass


def clear_all() -> None:
    """Clear the entire cache."""
    cache.clear()
    logger.info("Cache cleared.")
