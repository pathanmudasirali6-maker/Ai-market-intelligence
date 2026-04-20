"""
Test suite for Market Intelligence Platform
Uses pytest + httpx AsyncClient for async FastAPI testing.
Run: pytest tests/ -v --asyncio-mode=auto
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_db():
    """Mock MongoDB database for unit tests."""
    db = MagicMock()
    db.raw_data = MagicMock()
    db.processed_data = MagicMock()
    return db


# ── Processor Unit Tests ──────────────────────────────────────────────────────

class TestTextProcessor:
    def setup_method(self):
        from app.services.processor import TextProcessor
        self.proc = TextProcessor()

    def test_clean_text_removes_html(self):
        dirty = "<p>Hello <b>world</b></p>"
        assert "<" not in self.proc.clean_text(dirty)
        assert "Hello" in self.proc.clean_text(dirty)

    def test_clean_text_removes_urls(self):
        text = "Visit https://example.com for more info"
        assert "https://" not in self.proc.clean_text(text)

    def test_tokenize_removes_stopwords(self):
        text = "the quick brown fox jumps over the lazy dog"
        tokens = self.proc.tokenize(text)
        assert "the" not in tokens
        assert "over" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens

    def test_sentiment_positive(self):
        label, polarity, _ = self.proc.analyze_sentiment(
            "This is an excellent, wonderful, fantastic product!"
        )
        assert label == "positive"
        assert polarity > 0

    def test_sentiment_negative(self):
        label, polarity, _ = self.proc.analyze_sentiment(
            "This is terrible, awful, horrible and disappointing."
        )
        assert label == "negative"
        assert polarity < 0

    def test_sentiment_neutral(self):
        label, polarity, _ = self.proc.analyze_sentiment(
            "The meeting is scheduled for Tuesday at 3pm."
        )
        assert label == "neutral"

    def test_sentiment_empty_text(self):
        label, polarity, subj = self.proc.analyze_sentiment("")
        assert label == "neutral"
        assert polarity == 0.0

    def test_extract_keywords_returns_list(self):
        text = "Artificial intelligence and machine learning are transforming technology industries worldwide."
        keywords = self.proc.extract_keywords(text)
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert len(keywords) <= 10

    def test_extract_keywords_no_stopwords(self):
        text = "The quick brown fox jumped over the lazy dog in the park."
        keywords = self.proc.extract_keywords(text)
        for kw in keywords:
            assert kw not in {"the", "over", "in"}

    def test_word_count(self):
        assert self.proc.word_count("hello world foo bar") == 4
        assert self.proc.word_count("") == 0
        assert self.proc.word_count(None) == 0

    def test_reading_time(self):
        # 238 words = 1 minute
        rt = self.proc.reading_time(238)
        assert rt == pytest.approx(1.0, abs=0.1)

    def test_compute_score_recent_article(self):
        score = self.proc.compute_score(
            title="AI Breaks New Record in Performance",
            content="Detailed content " * 100,
            published_at=datetime.utcnow(),
            keyword_count=8,
        )
        assert 0.0 <= score <= 1.0

    def test_compute_score_old_article(self):
        from datetime import timedelta
        old = datetime.utcnow() - timedelta(days=30)
        score = self.proc.compute_score(
            title="Old News",
            content="Some content",
            published_at=old,
            keyword_count=3,
        )
        # Old article should have lower score than recent
        recent_score = self.proc.compute_score(
            title="Old News",
            content="Some content",
            published_at=datetime.utcnow(),
            keyword_count=3,
        )
        assert score < recent_score


# ── Cache Unit Tests ──────────────────────────────────────────────────────────

class TestCache:
    def setup_method(self):
        from app.core.cache import IntelCache
        self.cache = IntelCache(maxsize=10, ttl=60)

    def test_set_and_get(self):
        self.cache.set("key1", {"data": 42})
        result = self.cache.get("key1")
        assert result == {"data": 42}

    def test_miss_returns_none(self):
        result = self.cache.get("nonexistent_key_xyz")
        assert result is None

    def test_stats_track_hits_misses(self):
        self.cache.set("k", "v")
        self.cache.get("k")      # hit
        self.cache.get("k")      # hit
        self.cache.get("miss")   # miss
        stats = self.cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate_pct"] == pytest.approx(66.67, abs=0.1)

    def test_delete(self):
        self.cache.set("del_key", "value")
        self.cache.delete("del_key")
        assert self.cache.get("del_key") is None

    def test_clear(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.clear()
        assert self.cache.get("a") is None
        assert self.cache.get("b") is None


# ── Schema Validation Tests ───────────────────────────────────────────────────

class TestSchemas:
    def test_ingest_request_defaults(self):
        from app.models.schemas import IngestRequest
        req = IngestRequest()
        assert req.page_size == 20
        assert req.language == "en"

    def test_ingest_request_validation(self):
        from app.models.schemas import IngestRequest
        import pytest
        with pytest.raises(Exception):
            IngestRequest(page_size=200)  # max is 100

    def test_raw_article_cleans_title(self):
        from app.models.schemas import RawArticleCreate
        art = RawArticleCreate(
            title="  Hello   World  ",
            source="Test",
            url="https://example.com/article",
            published_at=datetime.utcnow(),
        )
        assert art.title == "Hello World"

    def test_raw_article_normalizes_category(self):
        from app.models.schemas import RawArticleCreate
        art = RawArticleCreate(
            title="Test Article",
            source="Source",
            url="https://example.com/test",
            published_at=datetime.utcnow(),
            category="TECHNOLOGY",
        )
        assert art.category == "technology"

    def test_processed_article_sentiment_score_range(self):
        from app.models.schemas import ProcessedArticleBase
        import pytest
        with pytest.raises(Exception):
            ProcessedArticleBase(
                raw_id="abc",
                title="Test",
                source="S",
                published_at=datetime.utcnow(),
                category="tech",
                sentiment="positive",
                sentiment_score=2.0,  # invalid: max 1.0
                subjectivity=0.5,
                score=0.5,
                trend_score=10,
                word_count=100,
                reading_time_minutes=0.5,
            )


# ── News Client Tests (mocked) ────────────────────────────────────────────────

class TestNewsClient:
    def test_normalize_article_skips_removed(self):
        from app.services.news_client import NewsAPIClient
        client = NewsAPIClient()
        raw = {
            "title": "[Removed]",
            "url": "https://removed.com",
            "source": {"name": "Test"},
            "publishedAt": "2024-01-01T00:00:00Z",
        }
        result = client._normalize_article(raw)
        assert result is None

    def test_normalize_article_skips_missing_fields(self):
        from app.services.news_client import NewsAPIClient
        client = NewsAPIClient()
        result = client._normalize_article({"title": "", "url": ""})
        assert result is None

    def test_normalize_valid_article(self):
        from app.services.news_client import NewsAPIClient
        client = NewsAPIClient()
        raw = {
            "title": "AI Makes Breakthrough in Drug Discovery",
            "url": "https://techcrunch.com/2024/01/ai-drug",
            "source": {"name": "TechCrunch"},
            "publishedAt": "2024-01-15T10:30:00Z",
            "content": "Scientists using AI have discovered...",
            "description": "A major breakthrough...",
            "author": "Jane Doe",
            "urlToImage": "https://techcrunch.com/img.jpg",
        }
        result = client._normalize_article(raw, category="technology")
        assert result is not None
        assert result.title == "AI Makes Breakthrough in Drug Discovery"
        assert result.source == "TechCrunch"
        assert result.category == "technology"

    def test_normalize_handles_bad_date(self):
        from app.services.news_client import NewsAPIClient
        client = NewsAPIClient()
        raw = {
            "title": "Valid Title Here",
            "url": "https://example.com/article-123",
            "source": {"name": "Source"},
            "publishedAt": "not-a-date",
        }
        result = client._normalize_article(raw)
        assert result is not None
        assert isinstance(result.published_at, datetime)


# ── Integration Tests (require running app + DB) ──────────────────────────────

@pytest.mark.integration
class TestAPIEndpoints:
    """
    These tests require a running MongoDB instance.
    Run with: pytest tests/ -v -m integration
    Set MONGODB_URL env var before running.
    """

    @pytest.fixture
    async def client(self):
        from main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "endpoints" in data

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data
        assert "uptime_seconds" in data

    @pytest.mark.asyncio
    async def test_trends_endpoint(self, client):
        resp = await client.get("/trends?days=7&top_n=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "days" in data
        assert "keywords" in data
        assert isinstance(data["keywords"], list)

    @pytest.mark.asyncio
    async def test_trends_invalid_days(self, client):
        resp = await client.get("/trends?days=0")
        assert resp.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_insights_endpoint(self, client):
        resp = await client.get("/insights?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert "sentiment" in data
        assert "time_series" in data
        assert "top_sources" in data

    @pytest.mark.asyncio
    async def test_search_requires_query(self, client):
        resp = await client.get("/search")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_short_query(self, client):
        resp = await client.get("/search?q=a")  # min_length=2
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_valid(self, client):
        resp = await client.get("/search?q=technology&page=1&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "data" in data
        assert "page" in data

    @pytest.mark.asyncio
    async def test_analytics_summary(self, client):
        resp = await client.get("/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_raw" in data
        assert "total_processed" in data
        assert "processing_rate_pct" in data

    @pytest.mark.asyncio
    async def test_ingest_endpoint_structure(self, client):
        """Test ingest with a mock (avoids hitting real NewsAPI in CI)."""
        with patch("app.services.news_client.NewsAPIClient.fetch_top_headlines") as mock_fetch:
            mock_fetch.return_value = []
            resp = await client.post("/ingest", json={
                "category": "technology",
                "page_size": 5,
            })
            assert resp.status_code in [200, 500]  # 500 if NewsAPI key not set

    @pytest.mark.asyncio
    async def test_pagination_params(self, client):
        resp = await client.get("/search?q=news&page=1&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) <= 5

    @pytest.mark.asyncio
    async def test_search_sentiment_filter(self, client):
        resp = await client.get("/search?q=market&sentiment=positive")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_headers(self, client):
        resp = await client.get("/health")
        assert "x-process-time" in resp.headers
        assert "x-api-version" in resp.headers
