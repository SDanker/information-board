from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> JSONResponse:
    result = {"status": "ok", "database": "ok", "redis": "ok"}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        result.update(status="degraded", database="error")
    try:
        settings = get_settings()
        if not settings.testing:
            Redis.from_url(settings.redis_url, socket_timeout=1).ping()
    except Exception:
        result.update(status="degraded", redis="error")
    return JSONResponse(status_code=200 if result["status"] == "ok" else 503, content=result)
