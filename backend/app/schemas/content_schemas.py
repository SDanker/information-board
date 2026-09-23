import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.calendar_feed import normalize_feed_url
from app.i18n import _
from app.models import CONTENT_KINDS, LIBRARY_VISIBILITIES
from app.scheduling import local_wall_time, publication_status


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    page_number: int | None
    mime_type: str
    width: int | None
    height: int | None
    duration_seconds: int | None
    display_seconds: int | None
    size_bytes: int | None
    url: str = ""


class AssetUpdate(BaseModel):
    """Custom seconds a page or slide stays on screen while rotating. None = automatic."""

    display_seconds: int | None = Field(default=None, ge=2, le=600)


class ContentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    status: str
    payload: dict
    error_message: str | None
    created_at: datetime
    published_at: datetime | None
    assets: list[AssetResponse] = Field(default_factory=list)


class AnnouncementPayload(BaseModel):
    """Body of a text announcement, the simplest content type (no conversion pipeline)."""

    body: str = Field(min_length=1, max_length=4000)
    background: str = Field(default="brand", max_length=40)
    accent: str | None = Field(default=None, max_length=40)


class CalendarPayload(BaseModel):
    """Shared calendar (ICS) that the screens draw as a month, week or day view."""

    ics_url: str = Field(min_length=8, max_length=1000)
    view: Literal["month", "week", "day"] = "month"

    @field_validator("ics_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        return normalize_feed_url(value)


def _check_visibility(value: str | None) -> str | None:
    if value is not None and value not in LIBRARY_VISIBILITIES:
        raise ValueError(_("Invalid visibility: {visibility}", visibility=value))
    return value


def normalize_weekdays(value: list[int] | None) -> list[int] | None:
    """Weekdays 0 (Monday) .. 6 (Sunday). An empty list means every day and is stored as None."""
    if not value:
        return None
    if any(day < 0 or day > 6 for day in value):
        raise ValueError(_("Weekdays must be numbers between 0 (Monday) and 6 (Sunday)"))
    return sorted(set(value))


def normalize_wall_time(value: datetime | None) -> datetime | None:
    """Periods are kept as local wall time to the minute; a value with a zone is converted first."""
    return None if value is None else local_wall_time(value).replace(second=0, microsecond=0)


def check_publication_window(start_at: datetime | None, end_at: datetime | None) -> None:
    if start_at is not None and end_at is not None and end_at <= start_at:
        raise ValueError(_("The publication must end after it starts"))


class PublicationWindow(BaseModel):
    """When content may be shown. On creation, omitted fields take the default period."""

    publish_start_at: datetime | None = None
    publish_end_at: datetime | None = None
    publish_days: list[int] | None = None

    @field_validator("publish_start_at", "publish_end_at")
    @classmethod
    def wall_time(cls, value: datetime | None) -> datetime | None:
        return normalize_wall_time(value)

    @field_validator("publish_days")
    @classmethod
    def weekdays(cls, value: list[int] | None) -> list[int] | None:
        return normalize_weekdays(value)

    @model_validator(mode="after")
    def end_after_start(self) -> "PublicationWindow":
        check_publication_window(self.publish_start_at, self.publish_end_at)
        return self


class ContentCreate(PublicationWindow):
    kind: str = Field(default="ANNOUNCEMENT")
    title: str = Field(min_length=2, max_length=200)
    library_visibility: str = Field(default="LOCAL_PUBLIC")
    qr_overlay: dict | None = None
    announcement: AnnouncementPayload | None = None
    calendar: CalendarPayload | None = None

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, value: str) -> str:
        if value not in CONTENT_KINDS:
            raise ValueError(_("Invalid content type: {kind}", kind=value))
        return value

    @field_validator("library_visibility")
    @classmethod
    def valid_visibility(cls, value: str) -> str:
        return _check_visibility(value)


class ContentUpdate(PublicationWindow):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    library_visibility: str | None = None
    qr_overlay: dict | None = None
    is_archived: bool | None = None

    @field_validator("library_visibility")
    @classmethod
    def valid_visibility(cls, value: str | None) -> str | None:
        return _check_visibility(value)


class ContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    library_visibility: str
    qr_overlay: dict | None
    is_archived: bool
    publish_start_at: datetime | None = None
    publish_end_at: datetime | None = None
    publish_days: list[int] | None = None
    # Computed when the response is built: active, scheduled, expired or off_day.
    publication_status: str = "active"
    created_at: datetime
    updated_at: datetime
    published_version: ContentVersionResponse | None = None
    latest_version: ContentVersionResponse | None = None

    @model_validator(mode="after")
    def current_publication_status(self) -> "ContentResponse":
        self.publication_status = publication_status(
            start_at=self.publish_start_at, end_at=self.publish_end_at, days=self.publish_days
        )
        return self
