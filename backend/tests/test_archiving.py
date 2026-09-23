"""Archiving of finished publications: the sweep, restore, and the archived downloads."""

import io
import zipfile
from datetime import datetime, timedelta

from PIL import Image

from app.archiving import archive_expired
from app.content_paths import safe_filename
from app.database import SessionLocal
from app.scheduling import local_wall_time

INPUT_FORMAT = "%Y-%m-%dT%H:%M"


def _from_now(offset: timedelta) -> str:
    return (local_wall_time().replace(second=0, microsecond=0) + offset).strftime(INPUT_FORMAT)


def _announcement(client, auth_headers, title, **fields):
    response = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "ANNOUNCEMENT", "title": title, "announcement": {"body": "Hi"}, **fields},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _end_now(client, auth_headers, content_id):
    """Move the end of a publication into the past, as if its period had run out."""
    body = {"publish_start_at": _from_now(timedelta(days=-8)), "publish_end_at": _from_now(timedelta(hours=-1))}
    assert client.patch(f"/api/v1/content/{content_id}", headers=auth_headers, json=body).status_code == 200


def _sweep() -> int:
    with SessionLocal() as db:
        return archive_expired(db)


def _playlist(client, auth_headers, content_ids, name="Archive"):
    playlist = client.post("/api/v1/playlists", headers=auth_headers, json={"name": name}).json()
    for content_id in content_ids:
        assert (
            client.post(f"/api/v1/playlists/{playlist['id']}/items", headers=auth_headers, json={"content_id": content_id}).status_code == 201
        )
    return playlist["id"]


def _playlist_titles(client, auth_headers, playlist_id):
    playlist = next(p for p in client.get("/api/v1/playlists", headers=auth_headers).json() if p["id"] == playlist_id)
    return [item["content"]["title"] for item in playlist["items"]]


def _png(color=(9, 9, 9)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (60, 40), color=color).save(buffer, "PNG")
    return buffer.getvalue()


def _upload_image(client, auth_headers, title, color):
    from app.worker import process_one_job

    response = client.post(
        "/api/v1/content/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data={"kind": "IMAGE", "title": title},
        files={"file": ("photo.png", _png(color), "image/png")},
    )
    assert response.status_code == 201
    assert process_one_job() is True
    return response.json()["id"]


def test_the_sweep_archives_finished_publications_and_removes_them_from_playlists(client, auth_headers):
    finished = _announcement(client, auth_headers, "Finished")
    running = _announcement(client, auth_headers, "Running")
    playlist_id = _playlist(client, auth_headers, [finished, running])
    _end_now(client, auth_headers, finished)

    assert _sweep() == 1
    assert _sweep() == 0  # nothing left to archive

    assert _playlist_titles(client, auth_headers, playlist_id) == ["Running"]
    by_title = {item["title"]: item for item in client.get("/api/v1/content", headers=auth_headers).json()}
    assert by_title["Finished"]["is_archived"] is True
    assert by_title["Running"]["is_archived"] is False


def test_the_sweep_leaves_a_featured_event_that_is_being_broadcast(client, auth_headers):
    event = client.post("/api/v1/emergencies", headers=auth_headers, json={"title": "Live event"}).json()
    assert client.post(f"/api/v1/emergencies/{event['id']}/broadcast", headers=auth_headers).status_code == 200
    _end_now(client, auth_headers, event["id"])

    assert _sweep() == 0  # the broadcast is a manual override and stays on screen
    assert client.get("/api/v1/public/active-emergency").json()["status"] == "ok"

    client.post("/api/v1/emergencies/clear-broadcast", headers=auth_headers)
    assert _sweep() == 1


def test_archiving_by_hand_also_takes_the_publication_out_of_the_playlists(client, auth_headers):
    content_id = _announcement(client, auth_headers, "By hand")
    playlist_id = _playlist(client, auth_headers, [content_id])
    assert client.patch(f"/api/v1/content/{content_id}", headers=auth_headers, json={"is_archived": True}).status_code == 200
    assert _playlist_titles(client, auth_headers, playlist_id) == []


def test_archived_publications_do_not_reach_the_screens(client, auth_headers):
    content_id = _announcement(client, auth_headers, "Hidden")
    playlist_id = _playlist(client, auth_headers, [content_id])
    screen = next(s for s in client.get("/api/v1/screens", headers=auth_headers).json() if s["slug"] == "principal")
    client.patch(f"/api/v1/screens/{screen['id']}", headers=auth_headers, json={"playlist_id": playlist_id})
    assert len(client.get("/api/v1/public/screens/principal/playlist").json()["items"]) == 1

    client.patch(f"/api/v1/content/{content_id}", headers=auth_headers, json={"is_archived": True})
    assert client.get("/api/v1/public/screens/principal/playlist").json()["items"] == []
    assert client.get("/api/v1/public/screens/principal/library").json()["items"] == []


def test_a_finished_publication_cannot_join_a_playlist_until_it_is_restored(client, auth_headers):
    content_id = _announcement(client, auth_headers, "Comes back", publish_days=[0, 1])
    _end_now(client, auth_headers, content_id)
    _sweep()

    playlist = client.post("/api/v1/playlists", headers=auth_headers, json={"name": "Restore"}).json()
    add = {"content_id": content_id}
    refused = client.post(f"/api/v1/playlists/{playlist['id']}/items", headers={**auth_headers, "Accept-Language": "es"}, json=add)
    assert refused.status_code == 422
    assert "restáuralas primero" in refused.json()["detail"]

    restored = client.post(f"/api/v1/content/{content_id}/restore", headers=auth_headers)
    assert restored.status_code == 200
    body = restored.json()
    assert body["is_archived"] is False
    assert datetime.fromisoformat(body["publish_end_at"]) - datetime.fromisoformat(body["publish_start_at"]) == timedelta(days=7)
    assert body["publish_days"] == [0, 1]  # the weekday limits it had are kept
    assert client.post(f"/api/v1/playlists/{playlist['id']}/items", headers=auth_headers, json=add).status_code == 201


def test_restoring_follows_the_default_length_from_settings(client, auth_headers):
    branding = client.get("/api/v1/public/branding").json()
    branding.pop("logo_url")
    branding["display"]["default_publication_days"] = 0
    client.put("/api/v1/branding", headers=auth_headers, json=branding)

    content_id = _announcement(client, auth_headers, "No end")
    client.patch(f"/api/v1/content/{content_id}", headers=auth_headers, json={"is_archived": True})
    restored = client.post(f"/api/v1/content/{content_id}/restore", headers=auth_headers).json()
    assert restored["publish_end_at"] is None
    assert restored["publication_status"] == "active"


def test_the_archived_library_lists_only_public_finished_publications(client, auth_headers):
    public = _announcement(client, auth_headers, "Public finished")
    hidden = _announcement(client, auth_headers, "QR only finished", library_visibility="QR_ONLY")
    _announcement(client, auth_headers, "Still running")
    calendar = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "CALENDAR", "title": "A calendar", "calendar": {"ics_url": "https://calendar.example.org/x.ics"}},
    ).json()["id"]
    for content_id in (public, hidden, calendar):
        _end_now(client, auth_headers, content_id)

    # Not swept yet: an expired publication already belongs to the archive, so the list never lags.
    archived = client.get("/api/v1/public/library/archived").json()
    assert [item["title"] for item in archived] == ["Public finished"]
    assert archived[0]["period_end"] is not None
    assert {item["title"] for item in client.get("/api/v1/public/library").json()} == {"Still running"}

    # Its link keeps working, and so does the file it points to.
    token = archived[0]["share_url"].rsplit("/share/", 1)[1]
    assert client.get(f"/api/v1/public/share/{token}").status_code == 200

    client.post("/api/v1/emergencies", headers=auth_headers, json={"title": "Featured"})
    assert _sweep() == 3
    assert [item["title"] for item in client.get("/api/v1/public/library/archived").json()] == ["Public finished"]


def test_the_archived_library_follows_the_public_library_switch(client, auth_headers):
    branding = client.get("/api/v1/public/branding").json()
    branding.pop("logo_url")
    branding["public_library_enabled"] = False
    client.put("/api/v1/branding", headers=auth_headers, json=branding)
    assert client.get("/api/v1/public/library/archived").status_code == 404
    assert client.get("/api/v1/public/library/archived/download").status_code == 404


def test_all_archived_publications_download_as_one_zip(client, auth_headers):
    first = _upload_image(client, auth_headers, "Same title", (200, 0, 0))
    second = _upload_image(client, auth_headers, "Same title", (0, 200, 0))
    other = _upload_image(client, auth_headers, "Another one", (0, 0, 200))
    running = _upload_image(client, auth_headers, "Still running", (50, 50, 50))
    for content_id in (first, second, other):
        _end_now(client, auth_headers, content_id)
    assert _sweep() == 3

    response = client.get("/api/v1/public/library/archived/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "archived-publications.zip" in response.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert archive.testzip() is None
    names = archive.namelist()
    assert len(names) == 3  # the running publication is not included
    assert all(name.endswith(".png") for name in names)
    folders = {name.split("/")[0] for name in names}
    assert safe_filename("Another one") in folders
    assert safe_filename("Same title") in folders
    assert len(folders) == 3  # repeated titles get their own folder each
    assert all(archive.read(name)[:8] == b"\x89PNG\r\n\x1a\n" for name in names)
    assert running not in {first, second, other}


def test_downloading_the_archive_with_nothing_archived_is_a_404(client, auth_headers):
    _announcement(client, auth_headers, "Running")
    assert client.get("/api/v1/public/library/archived/download").status_code == 404
