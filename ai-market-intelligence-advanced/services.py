import requests
import os
import logging
from dotenv import load_dotenv
from typing import List, Dict, Optional

load_dotenv()

logger = logging.getLogger(__name__)

NEWS_API_BASE = "https://newsapi.org/v2/everything"
TOP_HEADLINES = "https://newsapi.org/v2/top-headlines"
NEWS_API_KEY = os.getenv("NEWS_API_KEY")


def fetch_news(query: str = "technology", page_size: int = 20) -> List[Dict]:
    """Fetch news articles for a given query."""
    if not NEWS_API_KEY:
        logger.error("NEWS_API_KEY not set.")
        return []
    try:
        params = {
            "q": query,
            "apiKey": NEWS_API_KEY,
            "pageSize": page_size,
            "sortBy": "publishedAt",
            "language": "en"
        }
        res = requests.get(NEWS_API_BASE, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        articles = data.get("articles", [])
        logger.info(f"Fetched {len(articles)} articles for query='{query}'")
        return articles
    except requests.RequestException as e:
        logger.error(f"News fetch failed: {e}")
        return []


def fetch_news_by_topic(topic: str, page_size: int = 30) -> List[Dict]:
    """Fetch news by topic with fallback to general search."""
    articles = fetch_news(query=topic, page_size=page_size)
    if not articles:
        logger.warning(f"No results for topic '{topic}', falling back to top headlines.")
        return fetch_top_headlines(category=topic)
    return articles


def fetch_top_headlines(category: str = "technology", country: str = "us") -> List[Dict]:
    """Fetch top headlines by category."""
    if not NEWS_API_KEY:
        return []
    try:
        params = {
            "category": category,
            "country": country,
            "apiKey": NEWS_API_KEY,
            "pageSize": 20
        }
        res = requests.get(TOP_HEADLINES, params=params, timeout=10)
        res.raise_for_status()
        return res.json().get("articles", [])
    except requests.RequestException as e:
        logger.error(f"Top headlines fetch failed: {e}")
        return []
