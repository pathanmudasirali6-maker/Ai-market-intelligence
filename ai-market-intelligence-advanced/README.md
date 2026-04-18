# AI Market Intelligence API (Advanced)

## Features
- Background ingestion (FastAPI BackgroundTasks)
- Caching (TTLCache)
- MongoDB integration
- Sentiment analysis
- Trend detection

## Deployment (Render)
- Uses render.yaml
- Add environment variables in dashboard

## Run
pip install -r requirements.txt
uvicorn app.main:app --reload
