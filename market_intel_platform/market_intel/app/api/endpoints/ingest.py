from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger

from app.db.mongodb import get_database
from app.models.schemas import IngestRequest, IngestResponse
from app.services.ingestion import get_ingestion_service
from app.core.cache import cache, trends_cache, insights_cache
from app.core.rate_limiter import limiter
from fastapi import Request

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

# Track background task status
_task_registry: dict = {}


async def _run_ingestion_task(task_id: str, request: IngestRequest, db: AsyncIOMotorDatabase):
    """Background task wrapper with status tracking."""
    _task_registry[task_id] = {"status": "running", "started_at": None}
    try:
        from datetime import datetime
        _task_registry[task_id]["started_at"] = datetime.utcnow().isoformat()
        svc = await get_ingestion_service(db)
        result = await svc.ingest(request)
        _task_registry[task_id] = {
            "status": "completed",
            "result": result,
            "completed_at": datetime.utcnow().isoformat(),
        }
        # Invalidate caches after new data
        trends_cache.clear()
        insights_cache.clear()
        logger.success(f"Background task {task_id} completed: {result}")
    except Exception as e:
        logger.error(f"Background task {task_id} failed: {e}")
        _task_registry[task_id] = {"status": "failed", "error": str(e)}


@router.post(
    "",
    response_model=IngestResponse,
    summary="Trigger data ingestion",
    description=(
        "Fetches fresh articles from NewsAPI, stores raw data in MongoDB, "
        "performs NLP processing (sentiment + keywords + scoring), "
        "and stores results in processed_data. "
        "Use background=true for non-blocking execution."
    ),
)
@limiter.limit("10/minute")
async def ingest_data(
    request: Request,
    body: IngestRequest = None,
    background: bool = Query(False, description="Run ingestion as background task"),
    background_tasks: BackgroundTasks = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    if body is None:
        body = IngestRequest()

    if background:
        import uuid
        task_id = str(uuid.uuid4())[:8]
        background_tasks.add_task(_run_ingestion_task, task_id, body, db)
        logger.info(f"Started background ingestion task: {task_id}")
        return IngestResponse(
            status="accepted",
            fetched=0, stored=0, processed=0, duplicates_skipped=0,
            message=f"Ingestion started in background. Task ID: {task_id}",
            task_id=task_id,
        )

    try:
        svc = await get_ingestion_service(db)
        result = await svc.ingest(body)
        # Bust caches
        trends_cache.clear()
        insights_cache.clear()
        return IngestResponse(status="success", **result)
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get(
    "/task/{task_id}",
    summary="Get background task status",
)
async def get_task_status(task_id: str):
    task = _task_registry.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task
