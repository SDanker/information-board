from datetime import datetime, timedelta, timezone
from typing import Annotated
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.i18n import _
from app.models import User

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)

ROLES = ("ADMIN", "EDITOR", "OPERATOR")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user: User) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": str(user.id), "username": user.username, "role": user.role, "exp": expires},
        settings.secret_key,
        algorithm="HS256",
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_("Your session is invalid or has expired"),
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise error
    try:
        payload = jwt.decode(credentials.credentials, get_settings().secret_key, algorithms=["HS256"])
        user_id = uuid.UUID(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise error
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise error
    return user


def require_roles(*roles: str):
    allowed = set(roles)

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_("You do not have permission to perform this action"))
        return user

    return dependency


# ADMIN manages users and settings; EDITOR creates and publishes content and playlists;
# OPERATOR only views status (dashboard, screens, library) without changing anything.
require_admin = require_roles("ADMIN")
require_editor = require_roles("ADMIN", "EDITOR")
require_operator = require_roles("ADMIN", "EDITOR", "OPERATOR")
