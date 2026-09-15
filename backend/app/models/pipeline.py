import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from .screens_users import utc_now

ASSET_KINDS = ("SOURCE", "PAGE", "THUMBNAIL", "PHOTO", "VIDEO")
JOB_TYPES = ("CONVERT_DOCUMENT", "CONVERT_SPREADSHEET", "CONVERT_PRESENTATION", "TRANSCODE_VIDEO", "OPTIMIZE_IMAGE")
JOB_STATUSES = ("QUEUED", "RUNNING", "DONE", "FAILED")


class Asset(Base):
    """A source or derived file kept by the storage backend and attached to a content version."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    content_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("content_versions.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Only used by PAGE assets: seconds this page or slide stays on screen. None means the
    # playlist item's time is split evenly among the pages without their own value.
    display_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    content_version: Mapped["ContentVersion"] = relationship(back_populates="assets")  # noqa: F821


class ProcessingJob(Base):
    """Conversion queue: the worker picks QUEUED jobs, processes them and publishes the result."""

    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    content_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("content_versions.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
