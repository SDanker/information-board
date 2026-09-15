"""Playlist item schedule rules: date range, weekdays and time of day.

Everything is evaluated in the local time of ``settings.timezone`` (TIMEZONE or TZ), not
in UTC, because people enter schedules in their local time.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings


def local_now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


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
