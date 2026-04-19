from textblob import TextBlob

def get_sentiment(text):
    analysis = TextBlob(text)
    if analysis.sentiment.polarity > 0:
        return "positive"
    elif analysis.sentiment.polarity < 0:
        return "negative"
    else:
        return "neutral"

def extract_keywords(text):
    words = text.split()
    return list(set([w.lower() for w in words if len(w) > 4]))

def trend_score(text):
    return len(text.split()) // 10
