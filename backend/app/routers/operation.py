import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.database import get_db
from app.models import AuditLog, Content, Playlist, Screen, User
from app.security import require_admin, require_operator
from app.storage import get_storage

router = APIRouter(tags=["operation"])
logger = logging.getLogger("operation")

WORKER_HEARTBEAT_KEY = "information-board:worker:heartbeat"
WORKER_STALE_AFTER_SECONDS = 20


@router.get("/audit-logs")
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    limit = max(1, min(limit, 500))
    logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)).all()
    return [
        {
            "id": str(log.id),
            "username": log.username,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "detail": log.detail,
            "ip": log.ip,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/system/status")
def system_status(db: Annotated[Session, Depends(get_db)], _operator: Annotated[User, Depends(require_operator)]) -> dict:
    settings = get_settings()
    storage = get_storage()
    try:
        storage_bytes: int | None = storage.usage_bytes()
    except Exception:
        # A slow or unreachable object storage must not break the whole status page.
        logger.warning("Could not measure storage usage", exc_info=True)
        storage_bytes = None

    worker_seconds_ago: float | None = None
    try:
        value = Redis.from_url(settings.redis_url, socket_timeout=1).get(WORKER_HEARTBEAT_KEY)
        if value is not None:
            worker_seconds_ago = round(time.time() - float(value), 1)
    except Exception:
        worker_seconds_ago = None

    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "version": __version__,
        "timezone": settings.timezone,
        "default_language": settings.default_language,
        "public_base_url": settings.public_base_url,
        "allowed_networks": settings.allowed_networks or None,
        "storage": storage.describe(),
        "storage_bytes": storage_bytes,
        "worker_seconds_since_heartbeat": worker_seconds_ago,
        "worker_healthy": worker_seconds_ago is not None and worker_seconds_ago < WORKER_STALE_AFTER_SECONDS,
        "counts": {
            "screens": db.scalar(select(func.count()).select_from(Screen)) or 0,
            "contents": db.scalar(select(func.count()).select_from(Content).where(Content.deleted_at.is_(None))) or 0,
            "playlists": db.scalar(select(func.count()).select_from(Playlist)) or 0,
        },
    }
