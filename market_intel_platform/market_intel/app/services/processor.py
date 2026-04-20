"""
NLP Processing Service
- Sentiment analysis via TextBlob (VADER-inspired rule-based)
- Keyword extraction with TF-IDF style frequency scoring
- Trend scoring based on recency + social signals
- Reading time estimation
"""
import re
import math
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import Counter

from textblob import TextBlob
from loguru import logger
from app.models.schemas import RawArticleCreate, ProcessedArticleBase


# ─── Stopwords (English + Common News Junk) ─────────────────────────────────

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "dare",
    "ought", "used", "it", "its", "this", "that", "these", "those", "i",
    "we", "you", "he", "she", "they", "me", "us", "him", "her", "them",
    "my", "our", "your", "his", "their", "what", "which", "who", "whom",
    "when", "where", "why", "how", "all", "each", "every", "both", "few",
    "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "just", "about", "above",
    "after", "also", "as", "at", "back", "because", "before", "between",
    "during", "here", "however", "if", "into", "new", "now", "said", "says",
    "since", "through", "up", "via", "while", "within", "without", "yet",
    # News junk
    "click", "read", "more", "subscribe", "newsletter", "advertisement",
    "sponsored", "share", "follow", "like", "comment", "related", "articles",
    "get", "see", "make", "take", "one", "two", "three", "first", "last",
    "year", "years", "day", "days", "time", "times", "way", "ways",
    "percent", "per", "cent", "million", "billion", "thousand",
    "over", "under", "above", "below", "between", "among", "across",
}


class TextProcessor:
    """Core NLP processor for a single article."""

    WORDS_PER_MINUTE = 238  # average adult reading speed

    @staticmethod
    def clean_text(text: str) -> str:
        """Strip HTML, URLs, and normalise whitespace."""
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'https?://\S+', ' ', text)
        text = re.sub(r'[^\w\s\'-]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Lowercase tokenise, filter short tokens and stopwords."""
        tokens = re.findall(r"\b[a-zA-Z'][a-zA-Z']{2,}\b", text.lower())
        return [t for t in tokens if t not in STOPWORDS and len(t) > 2]

    def analyze_sentiment(self, text: str) -> Tuple[str, float, float]:
        """
        Returns (label, polarity[-1..1], subjectivity[0..1]).
        Uses TextBlob's pattern analyser (rule-based, no model download).
        """
        if not text or len(text.strip()) < 20:
            return "neutral", 0.0, 0.0

        blob = TextBlob(self.clean_text(text))
        polarity = blob.sentiment.polarity
        subjectivity = blob.sentiment.subjectivity

        if polarity >= 0.05:
            label = "positive"
        elif polarity <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        return label, round(polarity, 4), round(subjectivity, 4)

    def extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """
        TF-IDF-inspired keyword extraction:
        1. Tokenise & filter stopwords
        2. Prefer multi-word noun phrases via TextBlob
        3. Score by frequency, length bonus, position bonus
        """
        if not text:
            return []

        cleaned = self.clean_text(text)
        tokens = self.tokenize(cleaned)

        if not tokens:
            return []

        # Frequency count
        freq = Counter(tokens)
        total_tokens = len(tokens)

        # Extract significant bigrams (two consecutive non-stopword tokens)
        words = [w.lower() for w in re.findall(r"\b[a-zA-Z'][a-zA-Z']{2,}\b", cleaned)]
        bigrams = []
        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]
            if w1 not in STOPWORDS and w2 not in STOPWORDS and len(w1) > 2 and len(w2) > 2:
                bigrams.append(f"{w1} {w2}")
        bigram_freq = Counter(bigrams)

        # Score single tokens
        scores: Dict[str, float] = {}
        for token, count in freq.items():
            tf = count / total_tokens
            length_bonus = min(len(token) / 10, 0.3)
            scores[token] = tf + length_bonus

        # Boost tokens that appear in frequent bigrams
        for bigram, bcount in bigram_freq.most_common(15):
            for word in bigram.split():
                if word in scores:
                    scores[word] = scores[word] * (1 + 0.2 * min(bcount, 5))

        # Sort and return top keywords
        sorted_kw = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        keywords = [kw for kw, _ in sorted_kw[:top_n]]

        # Prepend top bigrams if they occur more than once
        top_bigrams = [bg for bg, c in bigram_freq.most_common(3) if c > 1]
        for bg in reversed(top_bigrams):
            if bg not in keywords:
                keywords.insert(0, bg)

        return keywords[:top_n]

    def compute_score(
        self,
        title: str,
        content: Optional[str],
        published_at: datetime,
        keyword_count: int,
    ) -> float:
        """
        Relevance/quality score [0..1]:
        - Recency score (exponential decay, half-life = 12h)
        - Content richness (length, keyword density)
        - Title quality (length)
        """
        now = datetime.utcnow()
        age_hours = max((now - published_at).total_seconds() / 3600, 0)
        half_life = 12.0
        recency = math.exp(-0.693 * age_hours / half_life)  # 0.5 at half_life

        content_len = len(content or "")
        richness = min(content_len / 2000, 1.0) * 0.4

        title_quality = min(len(title) / 80, 1.0) * 0.1

        kw_bonus = min(keyword_count / 10, 1.0) * 0.1

        raw_score = recency * 0.4 + richness + title_quality + kw_bonus
        return round(min(raw_score, 1.0), 4)

    def compute_trend_score(
        self,
        keywords: List[str],
        keyword_global_freq: Dict[str, int],
        published_at: datetime,
    ) -> int:
        """
        Trend score is an integer representing viral potential:
        - Sum of global frequencies of the article's keywords
        - Weighted by recency
        """
        now = datetime.utcnow()
        age_hours = max((now - published_at).total_seconds() / 3600, 0)
        recency_weight = max(1.0 - age_hours / 168, 0.1)  # 168h = 1 week

        raw = sum(keyword_global_freq.get(kw, 1) for kw in keywords[:10])
        return max(int(raw * recency_weight), 0)

    def word_count(self, text: str) -> int:
        return len((text or "").split())

    def reading_time(self, word_count: int) -> float:
        return round(word_count / self.WORDS_PER_MINUTE, 2)


class ProcessingService:
    """Orchestrates bulk NLP processing of raw articles."""

    def __init__(self):
        self.processor = TextProcessor()

    def process_article(
        self,
        raw_article: Dict[str, Any],
        keyword_global_freq: Optional[Dict[str, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single raw article dict.
        Returns a dict ready for MongoDB insertion.
        """
        try:
            text = " ".join(filter(None, [
                raw_article.get("title", ""),
                raw_article.get("description", ""),
                raw_article.get("content", ""),
            ]))

            sentiment, polarity, subjectivity = self.processor.analyze_sentiment(text)
            keywords = self.processor.extract_keywords(text)
            wc = self.processor.word_count(text)
            rt = self.processor.reading_time(wc)

            published_at = raw_article.get("published_at", datetime.utcnow())
            if isinstance(published_at, str):
                published_at = datetime.fromisoformat(published_at)

            score = self.processor.compute_score(
                raw_article.get("title", ""),
                raw_article.get("content"),
                published_at,
                len(keywords),
            )

            trend_score = self.processor.compute_trend_score(
                keywords,
                keyword_global_freq or {},
                published_at,
            )

            return {
                "raw_id": str(raw_article["_id"]),
                "title": raw_article.get("title", ""),
                "source": raw_article.get("source", ""),
                "published_at": published_at,
                "category": raw_article.get("category", "general"),
                "sentiment": sentiment,
                "sentiment_score": polarity,
                "subjectivity": subjectivity,
                "keywords": keywords,
                "score": score,
                "trend_score": trend_score,
                "word_count": wc,
                "reading_time_minutes": rt,
                "processed_at": datetime.utcnow(),
            }

        except Exception as e:
            logger.error(f"Failed to process article {raw_article.get('_id')}: {e}")
            return None

    def build_keyword_frequency(
        self, articles: List[Dict]
    ) -> Dict[str, int]:
        """Pre-compute global keyword frequencies across batch for trend scoring."""
        counter: Counter = Counter()
        for art in articles:
            text = " ".join(filter(None, [
                art.get("title", ""),
                art.get("content", ""),
            ]))
            tokens = self.processor.tokenize(self.processor.clean_text(text))
            counter.update(tokens)
        return dict(counter)


processing_service = ProcessingService()
