from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record as record_audit
from app.config import get_settings
from app.database import get_db
from app.i18n import _
from app.models import User
from app.network import client_ip
from app.rate_limit import too_many_attempts
from app.schemas import LoginRequest, TokenResponse
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])

# Reference hash verified when the user does not exist, so the response time does not
# reveal whether a username is registered.
_DUMMY_HASH = hash_password("no-such-user-reference-hash")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    settings = get_settings()
    # The real browser address (not nginx's), so one person's failed attempts never lock out everyone.
    ip = client_ip(request) or "unknown"
    if too_many_attempts(f"login:{ip}", limit=settings.login_max_attempts, window_seconds=settings.login_window_seconds):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_("Too many attempts. Wait a few minutes before trying again."),
        )
    user = db.scalar(select(User).where(User.username == payload.username))
    password_ok = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not user.is_active or not password_ok:
        record_audit(db, user, "login_failed", "auth", entity_id=payload.username, ip=ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_("Incorrect username or password"))
    record_audit(db, user, "login", "auth", entity_id=str(user.id), ip=ip)
    return TokenResponse(access_token=create_access_token(user), username=user.username, role=user.role)
