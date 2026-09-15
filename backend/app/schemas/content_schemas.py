import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.i18n import _
from app.models import CONTENT_KINDS, LIBRARY_VISIBILITIES


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


def _check_visibility(value: str | None) -> str | None:
    if value is not None and value not in LIBRARY_VISIBILITIES:
        raise ValueError(_("Invalid visibility: {visibility}", visibility=value))
    return value


class ContentCreate(BaseModel):
    kind: str = Field(default="ANNOUNCEMENT")
    title: str = Field(min_length=2, max_length=200)
    library_visibility: str = Field(default="LOCAL_PUBLIC")
    qr_overlay: dict | None = None
    announcement: AnnouncementPayload | None = None

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


class ContentUpdate(BaseModel):
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
    created_at: datetime
    updated_at: datetime
    published_version: ContentVersionResponse | None = None
    latest_version: ContentVersionResponse | None = None
