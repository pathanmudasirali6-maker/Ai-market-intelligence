from fastapi import APIRouter
from app.api.endpoints import ingest, analytics, health

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(ingest.router)
api_router.include_router(analytics.router)
