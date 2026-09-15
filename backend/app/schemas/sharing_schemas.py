import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ShareInfo(BaseModel):
    token: str
    share_url: str
    qr_url: str
    download_url: str
    revoked: bool
    download_count: int
    created_at: datetime


class ShareDownloadItem(BaseModel):
    """A file that can be downloaded on its own, e.g. each photo or the video of an emergency."""

    id: uuid.UUID
    kind: str
    label: str
    url: str


class PublicShareDetail(BaseModel):
    title: str
    kind: str
    thumbnail_url: str | None
    downloadable: bool
    download_url: str | None
    items: list[ShareDownloadItem] = Field(default_factory=list)


class LibraryItem(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    thumbnail_url: str | None
    share_url: str


class ScreenLibraryResponse(BaseModel):
    """What a screen's QR code opens: every shareable item of that screen's playlist, not
    only the item that was on air when someone scanned it."""

    screen_name: str
    items: list[LibraryItem]
