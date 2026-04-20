import httpx
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from loguru import logger
from app.core.config import settings
from app.models.schemas import RawArticleCreate


class NewsAPIClient:
    """
    Async client for NewsAPI.org with retry logic, rate-limit awareness,
    and full normalization of the raw response into our schema.
    """

    BASE_URL = settings.NEWS_API_BASE_URL
    MAX_RETRIES = 3
    RETRY_DELAY = 1.5  # seconds

    CATEGORY_MAP = {
        "business": "business",
        "entertainment": "entertainment",
        "general": "general",
        "health": "health",
        "science": "science",
        "sports": "sports",
        "technology": "technology",
    }

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={
                "X-Api-Key": settings.NEWS_API_KEY,
                "User-Agent": f"{settings.APP_NAME}/1.0",
            },
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def _request(self, endpoint: str, params: Dict) -> Dict[str, Any]:
        """Make a request with exponential backoff retry."""
        url = f"{self.BASE_URL}/{endpoint}"
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug(f"NewsAPI request | endpoint={endpoint} | attempt={attempt}")
                resp = await self._client.get(url, params=params)

                if resp.status_code == 429:
                    wait = self.RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"Rate limited by NewsAPI. Waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                if data.get("status") != "ok":
                    raise ValueError(f"NewsAPI error: {data.get('message', 'Unknown error')}")

                return data

            except httpx.HTTPStatusError as e:
                logger.error(f"NewsAPI HTTP error | status={e.response.status_code} | {e}")
                if attempt == self.MAX_RETRIES:
                    raise
                await asyncio.sleep(self.RETRY_DELAY * attempt)

            except httpx.RequestError as e:
                logger.error(f"NewsAPI request error | {e}")
                if attempt == self.MAX_RETRIES:
                    raise
                await asyncio.sleep(self.RETRY_DELAY * attempt)

        raise RuntimeError(f"NewsAPI request failed after {self.MAX_RETRIES} attempts")

    def _normalize_article(
        self, raw: Dict, category: str = "general"
    ) -> Optional[RawArticleCreate]:
        """Normalize a single NewsAPI article into our schema."""
        try:
            title = (raw.get("title") or "").strip()
            url = (raw.get("url") or "").strip()

            # Skip articles with missing critical fields or removed content
            if not title or not url:
                return None
            if title == "[Removed]" or url == "https://removed.com":
                return None

            # Parse source
            source_obj = raw.get("source", {})
            source = (
                source_obj.get("name")
                or source_obj.get("id")
                or "Unknown"
            ).strip()

            # Parse datetime (NewsAPI gives ISO8601 with Z suffix)
            published_str = raw.get("publishedAt", "")
            try:
                published_at = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except (ValueError, AttributeError):
                published_at = datetime.utcnow()

            # Content cleanup
            content = raw.get("content") or raw.get("description") or ""
            if content.endswith("… [+"):
                content = content.rsplit("…", 1)[0].strip()

            return RawArticleCreate(
                title=title,
                source=source,
                url=url,
                published_at=published_at,
                content=content[:5000] if content else None,
                description=(raw.get("description") or "")[:500] or None,
                author=raw.get("author") or None,
                category=self.CATEGORY_MAP.get(category, category),
                image_url=raw.get("urlToImage") or None,
            )
        except Exception as e:
            logger.warning(f"Failed to normalize article: {e} | raw={raw.get('title')}")
            return None

    async def fetch_top_headlines(
        self,
        query: Optional[str] = None,
        category: str = "general",
        page_size: int = 20,
        language: str = "en",
    ) -> List[RawArticleCreate]:
        """Fetch top headlines with optional query/category filter."""
        params: Dict = {
            "language": language,
            "pageSize": min(page_size, 100),
        }
        if query:
            params["q"] = query
        if category and category in self.CATEGORY_MAP:
            params["category"] = category
        else:
            params["country"] = "us"

        data = await self._request("top-headlines", params)
        articles = data.get("articles", [])
        logger.info(f"Fetched {len(articles)} headlines | category={category} | query={query}")

        normalized = [
            a for raw in articles
            if (a := self._normalize_article(raw, category)) is not None
        ]
        logger.info(f"Normalized {len(normalized)}/{len(articles)} articles")
        return normalized

    async def fetch_everything(
        self,
        query: str,
        days_back: int = 7,
        page_size: int = 50,
        language: str = "en",
        sort_by: str = "relevancy",
    ) -> List[RawArticleCreate]:
        """Fetch from 'everything' endpoint for deep search."""
        from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        params = {
            "q": query,
            "from": from_date,
            "language": language,
            "sortBy": sort_by,
            "pageSize": min(page_size, 100),
        }

        data = await self._request("everything", params)
        articles = data.get("articles", [])
        logger.info(f"Fetched {len(articles)} articles via everything | query={query}")

        normalized = [
            a for raw in articles
            if (a := self._normalize_article(raw, "general")) is not None
        ]
        return normalized

    async def fetch_multi_category(
        self, categories: List[str], page_size_each: int = 10
    ) -> List[RawArticleCreate]:
        """Concurrently fetch multiple categories."""
        tasks = [
            self.fetch_top_headlines(category=cat, page_size=page_size_each)
            for cat in categories
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_articles = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching category {categories[i]}: {result}")
            else:
                all_articles.extend(result)
        return all_articles
