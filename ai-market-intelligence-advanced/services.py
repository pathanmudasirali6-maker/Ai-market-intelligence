import requests
import os
from dotenv import load_dotenv

load_dotenv()

NEWS_API = "https://newsapi.org/v2/everything"

def fetch_news():
    params = {
        "q": "technology",
        "apiKey": os.getenv("NEWS_API_KEY")
    }
    res = requests.get(NEWS_API, params=params)
    return res.json().get("articles", [])
