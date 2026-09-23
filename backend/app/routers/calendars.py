"""Calendar feeds for the screens, and a preview used by the administration form."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.calendar_feed import CalendarError, feed_payload, load_events
from app.database import get_db
from app.i18n import _
from app.models import Content, User
from app.scheduling import is_published_now, local_now
from app.security import require_editor

router = APIRouter(tags=["calendars"])


@router.get("/public/calendar/{content_id}")
def public_calendar(content_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> dict:
    """Events of a published calendar, expanded for the view it was configured with."""
    content = db.scalar(
        select(Content)
        .where(Content.id == content_id, Content.kind == "CALENDAR", Content.deleted_at.is_(None))
        .options(selectinload(Content.published_version))
    )
    if content is None or content.published_version is None or not is_published_now(content):
        raise HTTPException(status_code=404, detail=_("Calendar not found"))
    payload = content.published_version.payload or {}
    try:
        return feed_payload(payload.get("ics_url", ""), payload.get("view", "month"))
    except (CalendarError, ValueError) as exc:
        # 502: the calendar exists here, but its provider could not be read right now.
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/calendar/preview")
def preview_calendar(
    _editor: Annotated[User, Depends(require_editor)], url: Annotated[str, Query(max_length=1000)]
) -> dict:
    """Check an address while filling the form: how many events it has and the next ones."""
    try:
        events, _fetched_at = load_events(url, force=True)
    except (CalendarError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    today = local_now().date().isoformat()
    return {"total": len(events), "upcoming": [event for event in events if event["start"][:10] >= today][:5]}
