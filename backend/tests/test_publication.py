import io
from datetime import datetime, timedelta, timezone

from PIL import Image

from app.config import get_settings
from app.scheduling import local_wall_time, publication_status

INPUT_FORMAT = "%Y-%m-%dT%H:%M"


def _from_now(offset: timedelta) -> str:
    return (local_wall_time().replace(second=0, microsecond=0) + offset).strftime(INPUT_FORMAT)


def _announcement(client, auth_headers, title="Window", **window):
    return client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "ANNOUNCEMENT", "title": title, "announcement": {"body": "Hi"}, **window},
    )


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), color=(1, 2, 3)).save(buffer, "PNG")
    return buffer.getvalue()


def test_publication_status_rules():
    start = datetime(2026, 3, 2, 8, 0)  # Monday
    end = datetime(2026, 3, 9, 8, 0)
    assert publication_status(start_at=start, end_at=end, days=None, at=datetime(2026, 3, 2, 7, 59)) == "scheduled"
    assert publication_status(start_at=start, end_at=end, days=None, at=start) == "active"
    assert publication_status(start_at=start, end_at=end, days=None, at=end) == "expired"
    tuesday, wednesday = datetime(2026, 3, 3, 12, 0), datetime(2026, 3, 4, 12, 0)
    assert publication_status(start_at=start, end_at=end, days=[0, 2, 4], at=tuesday) == "off_day"
    assert publication_status(start_at=start, end_at=end, days=[0, 2, 4], at=wednesday) == "active"
    assert publication_status(start_at=None, end_at=None, days=None, at=wednesday) == "active"


def test_publication_status_uses_the_installation_time_zone(monkeypatch):
    monkeypatch.setattr(get_settings(), "timezone", "America/Santiago")
    noon_utc = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)  # 09:00 in Santiago (UTC-3)
    assert publication_status(start_at=datetime(2026, 3, 2, 9, 30), end_at=None, days=None, at=noon_utc) == "scheduled"
    assert publication_status(start_at=datetime(2026, 3, 2, 8, 30), end_at=None, days=None, at=noon_utc) == "active"


def test_new_publications_last_seven_days_by_default(client, auth_headers):
    body = _announcement(client, auth_headers).json()
    start = datetime.fromisoformat(body["publish_start_at"])
    end = datetime.fromisoformat(body["publish_end_at"])
    assert end - start == timedelta(days=7)
    assert abs(start - local_wall_time()) < timedelta(minutes=2)
    assert body["publish_days"] is None
    assert body["publication_status"] == "active"


def test_default_length_follows_settings(client, auth_headers):
    branding = client.get("/api/v1/public/branding").json()
    branding.pop("logo_url")
    assert branding["display"]["default_publication_days"] == 7

    branding["display"]["default_publication_days"] = 0
    assert client.put("/api/v1/branding", headers=auth_headers, json=branding).status_code == 200
    assert _announcement(client, auth_headers).json()["publish_end_at"] is None

    branding["display"]["default_publication_days"] = 3
    assert client.put("/api/v1/branding", headers=auth_headers, json=branding).status_code == 200
    body = _announcement(client, auth_headers).json()
    assert datetime.fromisoformat(body["publish_end_at"]) - datetime.fromisoformat(body["publish_start_at"]) == timedelta(days=3)


def test_custom_period_and_weekdays(client, auth_headers):
    body = _announcement(
        client, auth_headers, publish_start_at="2030-01-07T08:30", publish_end_at="2030-01-20T18:00", publish_days=[4, 0, 0]
    ).json()
    assert body["publish_start_at"] == "2030-01-07T08:30:00"
    assert body["publish_end_at"] == "2030-01-20T18:00:00"
    assert body["publish_days"] == [0, 4]
    assert body["publication_status"] == "scheduled"


def test_a_start_alone_gets_the_default_length_from_that_start(client, auth_headers):
    body = _announcement(client, auth_headers, publish_start_at="2030-01-07T08:30").json()
    assert body["publish_end_at"] == "2030-01-14T08:30:00"


def test_open_ended_publication(client, auth_headers):
    body = _announcement(client, auth_headers, publish_start_at=None, publish_end_at=None).json()
    assert body["publish_start_at"] is None
    assert body["publish_end_at"] is None
    assert body["publication_status"] == "active"


def test_invalid_periods_are_rejected(client, auth_headers):
    assert _announcement(client, auth_headers, publish_start_at="2030-01-10T10:00", publish_end_at="2030-01-10T09:00").status_code == 422
    assert _announcement(client, auth_headers, publish_days=[7]).status_code == 422

    content_id = _announcement(client, auth_headers).json()["id"]
    response = client.patch(f"/api/v1/content/{content_id}", headers=auth_headers, json={"publish_end_at": "2000-01-01T00:00"})
    assert response.status_code == 422
    spanish = client.patch(
        f"/api/v1/content/{content_id}", headers={**auth_headers, "Accept-Language": "es"}, json={"publish_end_at": "2000-01-01T00:00"}
    )
    assert spanish.json()["detail"] == "La publicación debe terminar después de su inicio"


def test_editing_changes_the_period(client, auth_headers):
    content_id = _announcement(client, auth_headers).json()["id"]
    body = client.patch(
        f"/api/v1/content/{content_id}",
        headers=auth_headers,
        json={"publish_start_at": None, "publish_end_at": _from_now(timedelta(hours=-1)), "publish_days": []},
    ).json()
    assert body["publish_start_at"] is None
    assert body["publish_days"] is None
    assert body["publication_status"] == "expired"


def test_only_content_inside_its_period_reaches_screens_catalogs_and_links(client, auth_headers):
    tomorrow = (local_wall_time().weekday() + 1) % 7
    ids = {
        "Active": _announcement(client, auth_headers, title="Active").json()["id"],
        "Expired": _announcement(client, auth_headers, title="Expired").json()["id"],
        "Upcoming": _announcement(client, auth_headers, title="Upcoming", publish_start_at=_from_now(timedelta(days=1))).json()["id"],
        "Off day": _announcement(client, auth_headers, title="Off day", publish_days=[tomorrow]).json()["id"],
    }
    playlist = client.post("/api/v1/playlists", headers=auth_headers, json={"name": "Periods"}).json()
    for content_id in ids.values():
        client.post(f"/api/v1/playlists/{playlist['id']}/items", headers=auth_headers, json={"content_id": content_id})
    # It ends after having been in the playlist: a finished publication cannot be added to one.
    ended = {"publish_start_at": _from_now(timedelta(days=-3)), "publish_end_at": _from_now(timedelta(days=-1))}
    assert client.patch(f"/api/v1/content/{ids['Expired']}", headers=auth_headers, json=ended).status_code == 200
    screen = next(s for s in client.get("/api/v1/screens", headers=auth_headers).json() if s["slug"] == "principal")
    client.patch(f"/api/v1/screens/{screen['id']}", headers=auth_headers, json={"playlist_id": playlist["id"]})

    playback = client.get("/api/v1/public/screens/principal/playlist").json()
    assert [item["title"] for item in playback["items"]] == ["Active"]

    playlists = client.get("/api/v1/playlists", headers=auth_headers).json()
    items = next(p for p in playlists if p["id"] == playlist["id"])["items"]
    assert {item["content"]["title"]: item["scheduled_now"] for item in items} == {
        "Active": True, "Expired": False, "Upcoming": False, "Off day": False
    }

    catalog = client.get("/api/v1/public/screens/principal/library").json()
    assert {item["title"] for item in catalog["items"]} == {"Active"}
    assert {item["title"] for item in client.get("/api/v1/public/library").json()} == {"Active"}

    # Links keep working after the period ends (archived publications stay downloadable) but not before it starts.
    expired_share = client.get(f"/api/v1/content/{ids['Expired']}/share", headers=auth_headers).json()
    assert client.get(f"/api/v1/public/share/{expired_share['token']}").status_code == 200
    upcoming_share = client.get(f"/api/v1/content/{ids['Upcoming']}/share", headers=auth_headers).json()
    assert client.get(f"/api/v1/public/share/{upcoming_share['token']}").status_code == 404
    active_share = client.get(f"/api/v1/content/{ids['Active']}/share", headers=auth_headers).json()
    assert client.get(f"/api/v1/public/share/{active_share['token']}").status_code == 200

    statuses = {item["title"]: item["publication_status"] for item in client.get("/api/v1/content", headers=auth_headers).json()}
    assert statuses == {"Active": "active", "Expired": "expired", "Upcoming": "scheduled", "Off day": "off_day"}


def test_uploads_accept_a_period(client, auth_headers):
    headers = {"Authorization": auth_headers["Authorization"]}

    def upload(**fields):
        return client.post(
            "/api/v1/content/upload",
            headers=headers,
            data={"kind": "IMAGE", "title": "Poster", **fields},
            files={"file": ("poster.png", _png(), "image/png")},
        )

    custom = upload(publish_start_at="2030-05-01T09:00", publish_end_at="", publish_days="1,3")
    assert custom.status_code == 201
    body = custom.json()
    assert body["publish_start_at"] == "2030-05-01T09:00:00"
    assert body["publish_end_at"] is None
    assert body["publish_days"] == [1, 3]

    default = upload().json()
    assert datetime.fromisoformat(default["publish_end_at"]) - datetime.fromisoformat(default["publish_start_at"]) == timedelta(days=7)

    invalid = upload(publish_end_at="not-a-date")
    assert invalid.status_code == 422
    assert "not-a-date" in invalid.json()["detail"]
    assert upload(publish_days="1,9").status_code == 422


def test_featured_events_get_the_default_period_and_can_change_it(client, auth_headers):
    body = client.post("/api/v1/emergencies", headers=auth_headers, json={"title": "Drill"}).json()
    start = datetime.fromisoformat(body["publish_start_at"])
    assert datetime.fromisoformat(body["publish_end_at"]) - start == timedelta(days=7)
    assert body["publication_status"] == "active"

    custom = client.post(
        "/api/v1/emergencies",
        headers=auth_headers,
        json={"title": "Custom", "publish_start_at": "2030-02-01T09:00", "publish_end_at": None, "publish_days": [5, 6]},
    ).json()
    assert custom["publish_start_at"] == "2030-02-01T09:00:00"
    assert custom["publish_end_at"] is None
    assert custom["publish_days"] == [5, 6]

    edited = client.patch(
        f"/api/v1/emergencies/{body['id']}", headers=auth_headers, json={"publish_end_at": "2031-01-01T00:00", "publish_days": [0]}
    ).json()
    assert edited["publish_end_at"] == "2031-01-01T00:00:00"
    assert edited["publish_days"] == [0]
    invalid = client.patch(f"/api/v1/emergencies/{body['id']}", headers=auth_headers, json={"publish_end_at": "2000-01-01T00:00"})
    assert invalid.status_code == 422
