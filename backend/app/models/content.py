import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from .screens_users import utc_now

# A single content model covers announcements, images, video, documents, spreadsheets,
# presentations and emergencies: `kind` tells them apart and `payload` holds the
# type-specific data.
CONTENT_KINDS = ("ANNOUNCEMENT", "IMAGE", "VIDEO", "DOCUMENT", "EXCEL", "PPTX", "EMERGENCY")
VERSION_STATUSES = ("PENDING", "PROCESSING", "READY", "FAILED")
LIBRARY_VISIBILITIES = ("LOCAL_PUBLIC", "QR_ONLY", "PRIVATE")


class Content(Base):
    __tablename__ = "contents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    library_visibility: Mapped[str] = mapped_column(String(20), default="LOCAL_PUBLIC")
    qr_overlay: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # The READY version screens must show. It is switched atomically on publish and never
    # points to an unfinished version.
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("content_versions.id", use_alter=True, name="fk_contents_published_version", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    versions: Mapped[list["ContentVersion"]] = relationship(
        back_populates="content", foreign_keys="ContentVersion.content_id", cascade="all, delete-orphan"
    )
    published_version: Mapped["ContentVersion | None"] = relationship(foreign_keys=[published_version_id], post_update=True)


class ContentVersion(Base):
    __tablename__ = "content_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    content_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("contents.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    # Type-specific data: announcement text and background, spreadsheet rows, emergency
    # address and coordinates, conversion metadata, etc.
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    content: Mapped["Content"] = relationship(back_populates="versions", foreign_keys=[content_id])
    assets: Mapped[list["Asset"]] = relationship(  # noqa: F821
        back_populates="content_version", cascade="all, delete-orphan", order_by="Asset.page_number"
    )
