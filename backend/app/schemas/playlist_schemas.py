import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.i18n import _
from .content_schemas import ContentResponse


class PlaylistItemBase(BaseModel):
    content_id: uuid.UUID
    order_index: int = Field(default=0, ge=0)
    duration_seconds: int = Field(default=15, ge=3, le=3600)
    is_active: bool = True
    start_date: date | None = None
    end_date: date | None = None
    days_of_week: list[int] | None = None
    start_time: time | None = None
    end_time: time | None = None

    @field_validator("days_of_week")
    @classmethod
    def valid_days(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if not value or any(day < 0 or day > 6 for day in value):
            raise ValueError(_("days_of_week must contain values between 0 (Monday) and 6 (Sunday)"))
        return sorted(set(value))


class PlaylistItemCreate(PlaylistItemBase):
    pass


class PlaylistItemUpdate(BaseModel):
    content_id: uuid.UUID | None = None
    order_index: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=3, le=3600)
    is_active: bool | None = None
    start_date: date | None = None
    end_date: date | None = None
    days_of_week: list[int] | None = None
    start_time: time | None = None
    end_time: time | None = None


class PlaylistItemResponse(PlaylistItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: ContentResponse | None = None
    scheduled_now: bool = True


class PlaylistCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    is_active: bool = True


class PlaylistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


class PlaylistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    items: list[PlaylistItemResponse] = Field(default_factory=list)
    screen_count: int = 0


class PlaylistReorder(BaseModel):
    item_ids: list[uuid.UUID] = Field(min_length=1)


class PlaylistPlaybackItem(BaseModel):
    """An item already resolved for playback: schedule rules applied, ready to render."""

    item_id: uuid.UUID
    content_id: uuid.UUID
    kind: str
    title: str
    duration_seconds: int
    payload: dict
    assets: list[dict] = Field(default_factory=list)
    qr: dict | None = None


class PlaylistPlaybackResponse(BaseModel):
    status: str
    items: list[PlaylistPlaybackItem]
