from textblob import TextBlob
import re
from typing import List

# Common English stopwords to filter out
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "that", "this", "these", "those",
    "it", "its", "he", "she", "they", "we", "you", "i", "my", "your",
    "his", "her", "our", "their", "as", "not", "no", "so", "if", "than",
    "then", "also", "just", "said", "says", "about", "after", "before",
    "into", "over", "more", "when", "which", "who", "what", "how", "new",
    "year", "time", "up", "out", "there", "can", "like", "other", "only",
    "now", "some", "them", "one", "two", "all", "get", "been", "very",
}


def get_sentiment(text: str) -> str:
    """Classify sentiment as positive, negative, or neutral."""
    if not text or not text.strip():
        return "neutral"
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    if polarity > 0.05:
        return "positive"
    elif polarity < -0.05:
        return "negative"
    else:
        return "neutral"


def get_sentiment_score(text: str) -> float:
    """Return raw polarity score between -1.0 and 1.0."""
    if not text:
        return 0.0
    return round(TextBlob(text).sentiment.polarity, 4)


def extract_keywords(text: str, max_keywords: int = 15) -> List[str]:
    """Extract meaningful keywords from text, filtering stopwords."""
    if not text:
        return []
    # Remove special characters, lowercase
    cleaned = re.sub(r"[^a-zA-Z\s]", "", text).lower()
    words = cleaned.split()
    keywords = [
        w for w in words
        if len(w) > 4 and w not in STOPWORDS
    ]
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique[:max_keywords]


def trend_score(text: str) -> int:
    """
    Compute a basic trend score based on word count and entity-like tokens.
    Higher = more signal-rich content.
    """
    if not text:
        return 0
    words = text.split()
    word_count = len(words)
    # Bonus for capitalized words (named entities, brands, places)
    capitalized_bonus = sum(1 for w in words if w.istitle() and len(w) > 2)
    score = (word_count // 10) + capitalized_bonus
    return min(score, 100)  # Cap at 100


def summarize_text(text: str, max_sentences: int = 2) -> str:
    """
    Naive extractive summarizer: returns the first N non-trivial sentences.
    """
    if not text or not text.strip():
        return ""
    blob = TextBlob(text)
    sentences = [str(s).strip() for s in blob.sentences if len(str(s).strip()) > 30]
    return " ".join(sentences[:max_sentences])
