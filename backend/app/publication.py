"""Publication periods shared by every kind of content (announcements, files, calendars, featured events)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.branding import load_branding
from app.schemas.content_schemas import check_publication_window
from app.scheduling import current_minute, default_publication_window

PUBLICATION_FIELDS = {"publish_start_at", "publish_end_at", "publish_days"}


def initial_publication(db: Session, provided: dict) -> dict:
    """Publication period of new content: the values sent, completed with the defaults.

    A missing start means now; a missing end means start + the default length from
    Settings > Screens & TV (7 days unless changed; 0 = no end). An explicit null keeps that
    side open, so API clients can still create content without limits.
    """
    start = provided["publish_start_at"] if "publish_start_at" in provided else current_minute()
    if "publish_end_at" in provided:
        end = provided["publish_end_at"]
    else:
        end = default_publication_window(load_branding(db).display.default_publication_days, start)[1]
    try:
        check_publication_window(start, end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"publish_start_at": start, "publish_end_at": end, "publish_days": provided.get("publish_days")}
