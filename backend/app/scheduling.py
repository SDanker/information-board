"""Schedule rules: playlist items (date range, weekdays, time of day) and publication periods.

Everything is evaluated in the local time of ``settings.timezone`` (TIMEZONE or TZ), not
in UTC, because people enter schedules in their local time. Publication periods are stored
as local wall time too (datetimes without a zone), exactly as they are typed in the form.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo

from app.config import get_settings

if TYPE_CHECKING:
    from app.models import Content

PublicationStatus = Literal["active", "scheduled", "expired", "off_day"]


def local_now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


def local_wall_time(value: datetime | None = None) -> datetime:
    """A moment as local wall time without a zone, comparable with stored publication periods."""
    moment = value or local_now()
    if moment.tzinfo is not None:
        moment = moment.astimezone(ZoneInfo(get_settings().timezone)).replace(tzinfo=None)
    return moment


def current_minute() -> datetime:
    return local_wall_time().replace(second=0, microsecond=0)


def _time_in_range(current: time, start: time | None, end: time | None) -> bool:
    if start is None or end is None:
        return True
    if start <= end:
        return start <= current <= end
    # Overnight range that crosses midnight, e.g. 22:00-06:00.
    return current >= start or current <= end


def is_item_scheduled_now(
    *,
    is_active: bool,
    start_date: date | None,
    end_date: date | None,
    days_of_week: list[int] | None,
    start_time: time | None,
    end_time: time | None,
    at: datetime | None = None,
) -> bool:
    """0=Monday .. 6=Sunday. Without restrictions the item is always scheduled."""
    if not is_active:
        return False
    moment = at or local_now()
    today = moment.date()
    if start_date and today < start_date:
        return False
    if end_date and today > end_date:
        return False
    if days_of_week and moment.weekday() not in days_of_week:
        return False
    return _time_in_range(moment.time(), start_time, end_time)


def next_boundary(*, at: datetime | None = None) -> datetime:
    """Next exact minute; clients can refresh then, when a schedule may have changed."""
    moment = at or local_now()
    return moment.replace(second=0, microsecond=0) + timedelta(minutes=1)


def publication_status(
    *,
    start_at: datetime | None,
    end_at: datetime | None,
    days: list[int] | None,
    at: datetime | None = None,
) -> PublicationStatus:
    """Where a publication stands at a moment. A missing start or end leaves that side open.

    The start is inclusive and the end exclusive, so a period ending at 18:00 is no longer
    shown at 18:00. Weekdays (0=Monday .. 6=Sunday) restrict the days inside the period.
    """
    moment = local_wall_time(at)
    if start_at is not None and moment < start_at:
        return "scheduled"
    if end_at is not None and moment >= end_at:
        return "expired"
    if days and moment.weekday() not in days:
        return "off_day"
    return "active"


def is_published_now(content: Content, at: datetime | None = None) -> bool:
    """True when content may be shown: inside its publication period and on an allowed weekday."""
    status = publication_status(start_at=content.publish_start_at, end_at=content.publish_end_at, days=content.publish_days, at=at)
    return status == "active"


def default_publication_window(days: int, start_at: datetime | None = None) -> tuple[datetime, datetime | None]:
    """Default period: from start_at (or the current minute) for ``days`` days; 0 days = no end."""
    start = start_at or current_minute()
    return start, (start + timedelta(days=days) if days > 0 else None)
