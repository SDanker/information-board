import uuid
from datetime import date as date_, datetime, time as time_

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from .screens_users import utc_now


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    items: Mapped[list["PlaylistItem"]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan", order_by="PlaylistItem.order_index"
    )


class PlaylistItem(Base):
    """One entry of a playlist, with order, duration and an optional schedule.

    days_of_week uses 0=Monday .. 6=Sunday (None = every day). When start_time is later
    than end_time the range is overnight and crosses midnight.
    """

    __tablename__ = "playlist_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    playlist_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("playlists.id", ondelete="CASCADE"), index=True)
    content_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("contents.id", ondelete="CASCADE"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    days_of_week: Mapped[list | None] = mapped_column(JSON, nullable=True)
    start_time: Mapped[time_ | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time_ | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    playlist: Mapped["Playlist"] = relationship(back_populates="items")
    content: Mapped["Content"] = relationship()  # noqa: F821
