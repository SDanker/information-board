from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record as record_audit
from app.database import get_db
from app.i18n import _
from app.models import User
from app.schemas import PasswordChange, UserCreate, UserResponse, UserUpdate
from app.security import get_current_user, hash_password, require_admin, verify_password

router = APIRouter(tags=["users"])


def _ensure_another_active_admin(db: Session, user: User) -> None:
    """Block changes that would leave the installation without any active administrator."""
    remaining_admins = db.scalar(
        select(func.count()).select_from(User).where(User.role == "ADMIN", User.is_active.is_(True), User.id != user.id)
    )
    if not remaining_admins:
        raise HTTPException(status_code=422, detail=_("At least one active administrator must remain"))


@router.get("/users", response_model=list[UserResponse])
def list_users(db: Annotated[Session, Depends(get_db)], _admin: Annotated[User, Depends(require_admin)]) -> list[UserResponse]:
    return list(db.scalars(select(User).order_by(User.username)).all())


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate, db: Annotated[Session, Depends(get_db)], admin: Annotated[User, Depends(require_admin)]
) -> UserResponse:
    if db.scalar(select(User).where(User.username == payload.username)) is not None:
        raise HTTPException(status_code=409, detail=_("A user with that name already exists"))
    user = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    record_audit(db, admin, "create", "user", str(user.id), {"username": user.username, "role": user.role})
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> UserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=_("User not found"))
    updates = payload.model_dump(exclude_unset=True)
    if user.role == "ADMIN" and ("role" in updates and updates["role"] != "ADMIN" or updates.get("is_active") is False):
        _ensure_another_active_admin(db, user)
    if "password" in updates:
        password = updates.pop("password")
        if password:
            user.password_hash = hash_password(password)
    for field, value in updates.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    record_audit(db, admin, "update", "user", str(user.id), {key: str(value) for key, value in updates.items()})
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], admin: Annotated[User, Depends(require_admin)]
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=422, detail=_("You cannot delete your own account"))
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=_("User not found"))
    if user.role == "ADMIN":
        _ensure_another_active_admin(db, user)
    username = user.username
    db.delete(user)
    db.commit()
    record_audit(db, admin, "delete", "user", str(user_id), {"username": username})


@router.post("/users/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_own_password(
    payload: PasswordChange, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail=_("The current password is incorrect"))
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    record_audit(db, user, "change_password", "user", str(user.id))
