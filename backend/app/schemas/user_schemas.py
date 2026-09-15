import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.i18n import _
from app.security import ROLES


def _check_role(value: str | None) -> str | None:
    if value is not None and value not in ROLES:
        raise ValueError(_("Invalid role: {role}", role=value))
    return value


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=200)
    role: str = Field(default="OPERATOR")

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        return _check_role(value)


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str | None) -> str | None:
        return _check_role(value)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: str
    is_active: bool
    created_at: datetime
