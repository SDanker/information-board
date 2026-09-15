import re
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.i18n import _

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESOLUTION_PATTERN = re.compile(r"^\d{2,5}x\d{2,5}$")
ONLINE_WINDOW_SECONDS = 45


def _normalize_slug(value: str) -> str:
    normalized = value.strip().lower()
    if not SLUG_PATTERN.fullmatch(normalized):
        raise ValueError(_("The slug may only contain lowercase letters, numbers and hyphens"))
    return normalized


def _check_resolution(value: str) -> str:
    if not RESOLUTION_PATTERN.fullmatch(value):
        raise ValueError(_("The resolution must use the WIDTHxHEIGHT format, e.g. 1920x1080"))
    return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class ScreenBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=1000)
    expected_resolution: str = Field(default="1920x1080", max_length=30)
    orientation: str = Field(default="landscape", pattern="^(landscape|portrait)$")
    is_active: bool = True
    qr_config: dict = Field(default_factory=lambda: {"visible": True})
    visual_config: dict = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        return _normalize_slug(value)

    @field_validator("expected_resolution")
    @classmethod
    def valid_resolution(cls, value: str) -> str:
        return _check_resolution(value)


class ScreenCreate(ScreenBase):
    pass


class ScreenUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    expected_resolution: str | None = Field(default=None, max_length=30)
    orientation: str | None = Field(default=None, pattern="^(landscape|portrait)$")
    is_active: bool | None = None
    qr_config: dict | None = None
    visual_config: dict | None = None
    playlist_id: uuid.UUID | None = None

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_slug(value)

    @field_validator("expected_resolution")
    @classmethod
    def valid_resolution(cls, value: str | None) -> str | None:
        return None if value is None else _check_resolution(value)


class ScreenResponse(ScreenBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    playlist_id: uuid.UUID | None
    last_seen_at: datetime | None
    last_ip: str | None
    last_user_agent: str | None
    created_at: datetime
    updated_at: datetime
    status: str = "OFFLINE"

    @classmethod
    def from_screen(cls, screen: object) -> "ScreenResponse":
        payload = cls.model_validate(screen)
        if payload.last_seen_at:
            seen = payload.last_seen_at
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - seen).total_seconds() <= ONLINE_WINDOW_SECONDS:
                payload.status = "ONLINE"
        return payload


class HeartbeatRequest(BaseModel):
    resolution: str | None = Field(default=None, max_length=30)

    @field_validator("resolution")
    @classmethod
    def valid_resolution(cls, value: str | None) -> str | None:
        # The heartbeat is public and keeps the screen ONLINE: an invalid value is dropped
        # instead of rejecting the whole heartbeat.
        if value is not None and not RESOLUTION_PATTERN.fullmatch(value):
            return None
        return value
