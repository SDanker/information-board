"""Archiving of publications whose period ended.

When a publication reaches its end date and time it is archived: it leaves every playlist, stops
appearing on screens and in the catalogs, and moves to the "Archived" segment of the admin and of
the download pages, where it can still be downloaded. Restoring it gives it a fresh period, but it
must be added to the playlists again, because archiving removed it from them.

The worker runs `archive_expired` every minute, so a publication is archived shortly after its end
time. Read paths never depend on the sweep: an expired publication is already hidden from screens
by its period alone (see scheduling.is_published_now).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ACTIVE_EMERGENCY_KEY, Content, PlaylistItem, SystemSetting
from app.realtime import publish_event
from app.scheduling import current_minute, default_publication_window

logger = logging.getLogger("archiving")


def _active_broadcast_id(db: Session) -> str | None:
    setting = db.get(SystemSetting, ACTIVE_EMERGENCY_KEY)
    return setting.value.get("content_id") if setting is not None else None


def remove_from_playlists(db: Session, content_id: uuid.UUID) -> set[uuid.UUID]:
    """Delete every playlist entry of a publication. Returns the playlists that changed."""
    playlist_ids = set(db.scalars(select(PlaylistItem.playlist_id).where(PlaylistItem.content_id == content_id)).all())
    if playlist_ids:
        db.execute(delete(PlaylistItem).where(PlaylistItem.content_id == content_id))
    return playlist_ids


def archive_content(db: Session, content: Content) -> set[uuid.UUID]:
    """Archive one publication and take it out of the playlists. The caller commits."""
    content.is_archived = True
    return remove_from_playlists(db, content.id)


def notify_archived(playlist_ids: set[uuid.UUID]) -> None:
    """Tell the screens to reload the playlists that lost items, and the admin to refresh its lists."""
    for playlist_id in playlist_ids:
        publish_event({"target": "all_screens", "type": "playlist_updated", "playlist_id": str(playlist_id)})
    publish_event({"target": "admin", "type": "playlists_changed"})
    publish_event({"target": "admin", "type": "content_changed"})


def archive_expired(db: Session) -> int:
    """Archive every publication whose end time has passed. Returns how many were archived.

    A featured event that is being broadcast right now is left alone until the broadcast is
    stopped: the broadcast is a manual override and must not vanish from the screens by itself.
    """
    broadcasting = _active_broadcast_id(db)
    expired = db.scalars(
        select(Content).where(
            Content.deleted_at.is_(None),
            Content.is_archived.is_(False),
            Content.publish_end_at.is_not(None),
            Content.publish_end_at <= current_minute(),
        )
    ).all()

    affected: set[uuid.UUID] = set()
    archived = 0
    for content in expired:
        if broadcasting is not None and str(content.id) == broadcasting:
            continue
        affected |= archive_content(db, content)
        archived += 1
    if archived:
        db.commit()
        notify_archived(affected)
        logger.info("Archived %s publication(s) whose period ended", archived)
    return archived


def restore_content(db: Session, content: Content, default_days: int) -> None:
    """Bring an archived publication back with a new period: from now for the default length.

    The weekdays it was limited to are kept. It is not put back into any playlist.
    """
    start, end = default_publication_window(default_days)
    content.is_archived = False
    content.publish_start_at = start
    content.publish_end_at = end
