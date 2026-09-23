"""Shared calendar feeds (ICS): parsing, windows, caching and the public endpoint."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import calendar_feed
from app.calendar_feed import CalendarError, events_in, load_events, parse_events, window_for
from app.config import get_settings

FEED_URL = "https://calendar.example.org/shared/calendar.ics"
SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//information board//test//EN
BEGIN:VEVENT
UID:single@test
SUMMARY:Ejercicio de compañía
LOCATION:Camino Lo Pinto 935
DESCRIPTION:Ejercicio de zanjas junto a la 14 y 15.
DTSTART;TZID=America/Santiago:20260909T200000
DTEND;TZID=America/Santiago:20260909T223000
END:VEVENT
BEGIN:VEVENT
UID:weekly@test
SUMMARY:Reunión semanal
DTSTART;TZID=America/Santiago:20260907T190000
DTEND;TZID=America/Santiago:20260907T200000
RRULE:FREQ=WEEKLY;COUNT=4
END:VEVENT
BEGIN:VEVENT
UID:allday@test
SUMMARY:Aniversario
DTSTART;VALUE=DATE:20260918
DTEND;VALUE=DATE:20260919
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture(autouse=True)
def santiago_timezone(monkeypatch):
    """Events are stored with a time zone; the board shows them in the installation's one."""
    monkeypatch.setattr(get_settings(), "timezone", "America/Santiago")
    calendar_feed._MEMORY_CACHE.clear()
    yield
    calendar_feed._MEMORY_CACHE.clear()


@pytest.fixture()
def feed(monkeypatch):
    """Serve the sample instead of downloading, and count the downloads."""
    calls = {"count": 0}

    def fake_download(url: str) -> str:
        calls["count"] += 1
        return SAMPLE_ICS

    monkeypatch.setattr(calendar_feed, "_download", fake_download)
    return calls


def _september(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 9, day, hour, tzinfo=ZoneInfo("America/Santiago"))


def test_parse_expands_repeats_and_keeps_local_times():
    events = parse_events(SAMPLE_ICS, _september(1, 0), _september(30, 23))
    titles = [event["title"] for event in events]
    assert titles.count("Reunión semanal") == 4  # weekly, four times
    assert "Ejercicio de compañía" in titles

    weekly = [event for event in events if event["title"] == "Reunión semanal"]
    assert [event["start"] for event in weekly] == [
        "2026-09-07T19:00", "2026-09-14T19:00", "2026-09-21T19:00", "2026-09-28T19:00"
    ]
    exercise = next(event for event in events if event["title"] == "Ejercicio de compañía")
    assert exercise["start"] == "2026-09-09T20:00"
    assert exercise["end"] == "2026-09-09T22:30"
    assert exercise["location"] == "Camino Lo Pinto 935"
    assert exercise["description"] == "Ejercicio de zanjas junto a la 14 y 15."
    assert exercise["all_day"] is False

    anniversary = next(event for event in events if event["title"] == "Aniversario")
    assert anniversary["all_day"] is True
    assert anniversary["start"] == "2026-09-18"


def test_invalid_feed_is_reported():
    with pytest.raises(CalendarError):
        parse_events("this is not a calendar", _september(1), _september(30))


def test_windows_cover_the_month_grid_the_week_and_the_day():
    monday = _september(21)  # 21 September 2026 is a Monday
    assert monday.weekday() == 0

    period_start, period_end, range_start, range_end = window_for("month", monday)
    assert (period_start.day, period_start.month) == (1, 9)
    assert (period_end.day, period_end.month) == (1, 10)
    assert range_start.weekday() == 0 and range_start <= period_start
    assert range_end.weekday() == 0 and range_end >= period_end

    assert window_for("week", monday)[:2] == (monday.date(), _september(28).date())
    assert window_for("day", monday)[:2] == (monday.date(), _september(22).date())


def test_events_in_respects_the_exclusive_end_of_all_day_entries():
    events = parse_events(SAMPLE_ICS, _september(1, 0), _september(30, 23))
    day_of = window_for("day", _september(18))
    assert [event["title"] for event in events_in(events, day_of[2], day_of[3])] == ["Aniversario"]
    # The ICS end is the next midnight, so the entry must not appear on the 19th.
    next_day = window_for("day", _september(19))
    assert events_in(events, next_day[2], next_day[3]) == []


def test_the_feed_is_downloaded_once_and_then_cached(feed):
    load_events(FEED_URL)
    load_events(FEED_URL)
    assert feed["count"] == 1
    assert load_events(FEED_URL, force=True) and feed["count"] == 2


def test_a_failing_provider_keeps_the_last_known_events(feed, monkeypatch):
    events, _fetched = load_events(FEED_URL)
    assert events

    def broken_download(url: str) -> str:
        raise CalendarError("provider down")

    monkeypatch.setattr(calendar_feed, "CACHE_FRESH_SECONDS", 0)
    monkeypatch.setattr(calendar_feed, "_download", broken_download)
    cached, _again = load_events(FEED_URL)
    assert [event["title"] for event in cached] == [event["title"] for event in events]


def test_public_calendar_endpoint_serves_the_configured_view(client, auth_headers, feed):
    created = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "CALENDAR", "title": "Calendario", "calendar": {"ics_url": FEED_URL, "view": "month"}},
    )
    assert created.status_code == 201
    assert created.json()["published_version"]["payload"] == {"ics_url": FEED_URL, "view": "month"}

    response = client.get(f"/api/v1/public/calendar/{created.json()['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["view"] == "month"
    assert body["timezone"] == "America/Santiago"
    assert body["range_start"] <= body["period_start"] < body["period_end"] <= body["range_end"]
    assert all(body["range_start"] <= event["start"][:10] < body["range_end"] for event in body["events"])


def test_calendar_without_a_valid_address_is_rejected(client, auth_headers):
    response = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "CALENDAR", "title": "Calendario", "calendar": {"ics_url": "ftp://example.org/x.ics"}},
    )
    assert response.status_code == 422
    missing = client.post("/api/v1/content", headers=auth_headers, json={"kind": "CALENDAR", "title": "Calendario"})
    assert missing.status_code == 422


def test_public_endpoint_ignores_other_content_and_reports_provider_errors(client, auth_headers, monkeypatch):
    announcement = client.post(
        "/api/v1/content", headers=auth_headers, json={"kind": "ANNOUNCEMENT", "title": "Aviso", "announcement": {"body": "Hola"}}
    ).json()
    assert client.get(f"/api/v1/public/calendar/{announcement['id']}").status_code == 404

    monkeypatch.setattr(calendar_feed, "_download", lambda url: SAMPLE_ICS)
    calendar = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "CALENDAR", "title": "Calendario", "calendar": {"ics_url": FEED_URL, "view": "week"}},
    ).json()

    def broken_download(url: str) -> str:
        raise CalendarError("caído")

    calendar_feed._MEMORY_CACHE.clear()
    monkeypatch.setattr(calendar_feed, "_download", broken_download)
    failed = client.get(f"/api/v1/public/calendar/{calendar['id']}")
    assert failed.status_code == 502
    assert failed.json()["detail"] == "caído"


def test_preview_requires_an_editor_and_summarizes_the_feed(client, auth_headers, feed):
    assert client.get("/api/v1/calendar/preview", params={"url": FEED_URL}).status_code == 401
    response = client.get("/api/v1/calendar/preview", headers=auth_headers, params={"url": FEED_URL})
    assert response.status_code == 200
    assert response.json()["total"] >= 1
    invalid = client.get("/api/v1/calendar/preview", headers=auth_headers, params={"url": "not-a-url"})
    assert invalid.status_code == 422

def test_default_calendar_address_is_stored_and_validated(client, auth_headers):
    branding = client.get("/api/v1/public/branding").json()
    branding.pop("logo_url")
    assert branding["default_calendar_ics_url"] == ""

    branding["default_calendar_ics_url"] = "not-an-address"
    assert client.put("/api/v1/branding", headers=auth_headers, json=branding).status_code == 422

    branding["default_calendar_ics_url"] = FEED_URL
    assert client.put("/api/v1/branding", headers=auth_headers, json=branding).status_code == 200
    assert client.get("/api/v1/public/branding").json()["default_calendar_ics_url"] == FEED_URL

def test_calendars_show_no_qr_and_stay_out_of_the_catalog(client, auth_headers, feed):
    calendar = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "CALENDAR", "title": "Calendario", "calendar": {"ics_url": FEED_URL, "view": "month"}},
    ).json()
    announcement = client.post(
        "/api/v1/content", headers=auth_headers, json={"kind": "ANNOUNCEMENT", "title": "Aviso", "announcement": {"body": "Hola"}}
    ).json()
    playlist = client.post("/api/v1/playlists", headers=auth_headers, json={"name": "Con calendario"}).json()
    for content_id in (calendar["id"], announcement["id"]):
        client.post(f"/api/v1/playlists/{playlist['id']}/items", headers=auth_headers, json={"content_id": content_id})
    screen = next(s for s in client.get("/api/v1/screens", headers=auth_headers).json() if s["slug"] == "principal")
    client.patch(f"/api/v1/screens/{screen['id']}", headers=auth_headers, json={"playlist_id": playlist["id"]})

    playback = client.get("/api/v1/public/screens/principal/playlist").json()
    qr_by_title = {item["title"]: item["qr"] for item in playback["items"]}
    assert qr_by_title["Calendario"] is None  # the code would cover the grid
    assert qr_by_title["Aviso"] is not None

    catalog = client.get("/api/v1/public/screens/principal/library").json()
    assert [item["title"] for item in catalog["items"]] == ["Aviso"]
    assert all(item["title"] != "Calendario" for item in client.get("/api/v1/public/library").json())


def test_a_publication_can_hide_the_qr_on_its_own(client, auth_headers):
    announcement = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "ANNOUNCEMENT", "title": "Sin QR", "announcement": {"body": "Hola"}, "qr_overlay": {"visible": False}},
    ).json()
    playlist = client.post("/api/v1/playlists", headers=auth_headers, json={"name": "Sin QR"}).json()
    client.post(f"/api/v1/playlists/{playlist['id']}/items", headers=auth_headers, json={"content_id": announcement["id"]})
    screen = next(s for s in client.get("/api/v1/screens", headers=auth_headers).json() if s["slug"] == "sala")
    client.patch(f"/api/v1/screens/{screen['id']}", headers=auth_headers, json={"playlist_id": playlist["id"]})

    playback = client.get("/api/v1/public/screens/sala/playlist").json()
    assert playback["items"][0]["qr"] is None

    client.patch(f"/api/v1/content/{announcement['id']}", headers=auth_headers, json={"qr_overlay": None})
    playback = client.get("/api/v1/public/screens/sala/playlist").json()
    assert playback["items"][0]["qr"] is not None
