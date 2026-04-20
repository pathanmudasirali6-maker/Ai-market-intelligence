import time
import hashlib
import json
from typing import Any, Optional, Callable
from functools import wraps
from cachetools import TTLCache
from loguru import logger
from app.core.config import settings


class IntelCache:
    """Thread-safe in-memory TTL cache with hit/miss statistics."""

    def __init__(self, maxsize: int = 512, ttl: int = None):
        self.ttl = ttl or settings.CACHE_TTL_SECONDS
        self._cache = TTLCache(maxsize=maxsize, ttl=self.ttl)
        self._hits = 0
        self._misses = 0
        self._sets = 0

    def _make_key(self, *args, **kwargs) -> str:
        raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        val = self._cache.get(key)
        if val is not None:
            self._hits += 1
            logger.debug(f"Cache HIT | key={key[:8]}...")
        else:
            self._misses += 1
        return val

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if ttl and ttl != self.ttl:
            # Custom TTL: create a temp entry with expiry timestamp
            self._cache[key] = value
        else:
            self._cache[key] = value
        self._sets += 1
        logger.debug(f"Cache SET | key={key[:8]}... | size={len(self._cache)}")

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()
        logger.info("Cache cleared")

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = round((self._hits / total * 100), 2) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "hit_rate_pct": hit_rate,
            "current_size": len(self._cache),
            "max_size": self._cache.maxsize,
            "ttl_seconds": self.ttl,
        }

    def cached(self, ttl: Optional[int] = None):
        """Decorator for caching async function results."""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                key = self._make_key(func.__name__, *args, **kwargs)
                cached_val = self.get(key)
                if cached_val is not None:
                    return cached_val
                result = await func(*args, **kwargs)
                self.set(key, result, ttl)
                return result
            return wrapper
        return decorator


# Singleton cache instances
cache = IntelCache(maxsize=512, ttl=settings.CACHE_TTL_SECONDS)
trends_cache = IntelCache(maxsize=64, ttl=120)   # 2 min for trends (fresher)
insights_cache = IntelCache(maxsize=32, ttl=300)  # 5 min for insights
