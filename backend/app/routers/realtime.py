import uuid

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Screen, User
from app.realtime import manager
from app.security import ROLES

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/screens/{slug}")
async def screen_socket(websocket: WebSocket, slug: str) -> None:
    with SessionLocal() as db:
        screen = db.scalar(select(Screen).where(Screen.slug == slug, Screen.is_active.is_(True)))
    if screen is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    manager.register_screen(slug, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister_screen(slug, websocket)


@router.websocket("/ws/admin")
async def admin_socket(websocket: WebSocket, token: str = Query(default="")) -> None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None or user.role not in ROLES:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    manager.register_admin(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister_admin(websocket)
