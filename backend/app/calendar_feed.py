"""Shared calendar feeds (ICS) shown on the screens.

An administrator pastes the ICS address of a published calendar (Outlook, Google, Nextcloud,
an intranet server...). The backend downloads and expands it, never the TV: screens without
Internet access still show the calendar, the link stays out of the page, and one download
serves every screen. Results are cached in Redis, refreshed every CACHE_FRESH_SECONDS and kept
for CACHE_TTL_SECONDS, so an outage at the provider keeps showing the last known events.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
import icalendar
import recurring_ical_events
from redis import Redis

from app.config import get_settings
from app.i18n import _
from app.scheduling import local_now

logger = logging.getLogger("calendar_feed")

VIEWS = ("month", "week", "day")
CACHE_PREFIX = "information-board:calendar:"
CACHE_FRESH_SECONDS = 600  # a feed is downloaded again at most every 10 minutes
CACHE_TTL_SECONDS = 7 * 24 * 3600  # ...and kept a week, to survive an outage at the provider
MAX_FEED_BYTES = 8 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 15
PAST_DAYS = 60
FUTURE_DAYS = 400
MAX_EVENTS = 1000
MAX_DESCRIPTION_CHARS = 600  # the day view shows it; screens cannot read more than this

# Fallback when Redis is unavailable, and the only cache during tests.
_MEMORY_CACHE: dict[str, tuple[float, list[dict]]] = {}


class CalendarError(RuntimeError):
    """Carries a translated message explaining why a calendar could not be read."""


def normalize_feed_url(raw: str) -> str:
    url = (raw or "").strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(_("Enter the calendar address (ICS), starting with https://"))
    # A calendar on the local network (Nextcloud, an intranet server) is a valid source, so
    # private addresses are allowed: only an administrator can configure this address.
    return url


def _local_zone() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def _cache_key(url: str) -> str:
    return CACHE_PREFIX + hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


def _redis() -> Redis | None:
    settings = get_settings()
    if settings.testing:
        return None
    try:
        return Redis.from_url(settings.redis_url, socket_timeout=2)
    except Exception:
        logger.warning("Redis unavailable for the calendar cache", exc_info=True)
        return None


def _read_cache(key: str) -> tuple[float, list[dict]] | None:
    client = _redis()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                stored = json.loads(raw)
                return float(stored["fetched_at"]), list(stored["events"])
        except Exception:
            logger.warning("Could not read the cached calendar", exc_info=True)
    return _MEMORY_CACHE.get(key)


def _write_cache(key: str, events: list[dict]) -> float:
    fetched_at = time.time()
    _MEMORY_CACHE[key] = (fetched_at, events)
    client = _redis()
    if client is not None:
        try:
            client.set(key, json.dumps({"fetched_at": fetched_at, "events": events}), ex=CACHE_TTL_SECONDS)
        except Exception:
            logger.warning("Could not store the calendar in the cache", exc_info=True)
    return fetched_at


def _download(url: str) -> str:
    try:
        with httpx.stream(
            "GET", url, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True, headers={"User-Agent": "information-board"}
        ) as response:
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_FEED_BYTES:
                    raise CalendarError(_("The calendar file is too large"))
                chunks.append(chunk)
    except httpx.HTTPStatusError as exc:
        raise CalendarError(_("The calendar link answered with an error ({status})", status=exc.response.status_code))
    except httpx.HTTPError:
        raise CalendarError(_("The calendar link could not be reached"))
    return b"".join(chunks).decode("utf-8", errors="replace")


def _as_local_text(value: datetime | date, zone: ZoneInfo) -> str:
    """Local wall time "YYYY-MM-DDTHH:MM", or "YYYY-MM-DD" for an all-day entry."""
    if isinstance(value, datetime):
        moment = value.astimezone(zone) if value.tzinfo else value
        return moment.strftime("%Y-%m-%dT%H:%M")
    return value.strftime("%Y-%m-%d")


def parse_events(text: str, start: datetime, end: datetime) -> list[dict]:
    """Expand the feed between two moments, repeated events included."""
    try:
        calendar = icalendar.Calendar.from_ical(text)
        occurrences = recurring_ical_events.of(calendar).between(start, end)
    except Exception:
        logger.warning("Could not read the calendar feed", exc_info=True)
        raise CalendarError(_("The file is not a valid calendar (ICS)"))

    zone = _local_zone()
    events: list[dict] = []
    for occurrence in occurrences:
        begins = occurrence.get("DTSTART")
        if begins is None:
            continue
        finishes = occurrence.get("DTEND") or begins
        events.append(
            {
                "uid": str(occurrence.get("UID", "")),
                "title": str(occurrence.get("SUMMARY", "")).strip(),
                "location": str(occurrence.get("LOCATION", "")).strip(),
                "description": str(occurrence.get("DESCRIPTION", "")).strip()[:MAX_DESCRIPTION_CHARS],
                "start": _as_local_text(begins.dt, zone),
                # For all-day entries ICS stores an exclusive end (the next midnight).
                "end": _as_local_text(finishes.dt, zone),
                "all_day": not isinstance(begins.dt, datetime),
            }
        )
    events.sort(key=lambda event: (event["start"], event["title"]))
    return events[:MAX_EVENTS]


def load_events(url: str, *, force: bool = False) -> tuple[list[dict], float]:
    """Events of the whole cached window and when they were downloaded (epoch seconds)."""
    url = normalize_feed_url(url)
    key = _cache_key(url)
    cached = None if force else _read_cache(key)
    if cached is not None and time.time() - cached[0] < CACHE_FRESH_SECONDS:
        return cached[1], cached[0]

    now = datetime.now(_local_zone())
    try:
        events = parse_events(_download(url), now - timedelta(days=PAST_DAYS), now + timedelta(days=FUTURE_DAYS))
    except CalendarError:
        if cached is not None:
            # The provider is unreachable: keep showing the last good copy instead of an error.
            logger.warning("Serving the cached calendar after a failed refresh")
            return cached[1], cached[0]
        raise
    return events, _write_cache(key, events)


def window_for(view: str, at: datetime | None = None) -> tuple[date, date, date, date]:
    """(period_start, period_end, range_start, range_end); both ends are exclusive.

    The month view also returns the full grid (whole weeks starting on Monday), so the screen
    can draw the leading and trailing days that belong to the neighbouring months.
    """
    today = (at or local_now()).date()
    if view == "day":
        return today, today + timedelta(days=1), today, today + timedelta(days=1)
    if view == "week":
        monday = today - timedelta(days=today.weekday())
        return monday, monday + timedelta(days=7), monday, monday + timedelta(days=7)
    first = today.replace(day=1)
    next_month = (first + timedelta(days=32)).replace(day=1)
    grid_start = first - timedelta(days=first.weekday())
    grid_end = next_month + timedelta(days=(7 - next_month.weekday()) % 7)
    return first, next_month, grid_start, grid_end


def _last_day(event: dict) -> str:
    """Last day the event is visible on; the ICS end of an all-day entry is exclusive."""
    end = event["end"][:10]
    if event["all_day"] and end > event["start"][:10]:
        return (date.fromisoformat(end) - timedelta(days=1)).isoformat()
    return end


def events_in(events: list[dict], start: date, end: date) -> list[dict]:
    """Events overlapping [start, end); comparing the local date text needs no zone maths."""
    lower, upper = start.isoformat(), end.isoformat()
    return [event for event in events if event["start"][:10] < upper and _last_day(event) >= lower]


def feed_payload(url: str, view: str) -> dict:
    """Everything a screen needs to draw one calendar view."""
    view = view if view in VIEWS else "month"
    events, fetched_at = load_events(url)
    period_start, period_end, range_start, range_end = window_for(view)
    return {
        "view": view,
        "timezone": get_settings().timezone,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "updated_at": datetime.fromtimestamp(fetched_at, _local_zone()).strftime("%Y-%m-%dT%H:%M"),
        "events": events_in(events, range_start, range_end),
    }
