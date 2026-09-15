import io
import zipfile

from PIL import Image


def _create_announcement(client, auth_headers, title="Anuncio", visibility="LOCAL_PUBLIC"):
    response = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "ANNOUNCEMENT", "title": title, "library_visibility": visibility, "announcement": {"body": "Hola"}},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _assign_playlist(client, auth_headers, slug, content_ids, name="Playlist"):
    playlist = client.post("/api/v1/playlists", headers=auth_headers, json={"name": name}).json()
    for content_id in content_ids:
        client.post(f"/api/v1/playlists/{playlist['id']}/items", headers=auth_headers, json={"content_id": content_id})
    screens = client.get("/api/v1/screens", headers=auth_headers).json()
    screen = next(s for s in screens if s["slug"] == slug)
    client.patch(f"/api/v1/screens/{screen['id']}", headers=auth_headers, json={"playlist_id": playlist["id"]})
    return screen


def test_share_info_created_lazily_and_reused(client, auth_headers):
    content_id = _create_announcement(client, auth_headers)

    first = client.get(f"/api/v1/content/{content_id}/share", headers=auth_headers)
    assert first.status_code == 200
    token = first.json()["token"]
    assert first.json()["share_url"].endswith(f"/share/{token}")

    second = client.get(f"/api/v1/content/{content_id}/share", headers=auth_headers)
    assert second.json()["token"] == token  # the same token until it is rotated


def test_rotate_invalidates_previous_token(client, auth_headers):
    content_id = _create_announcement(client, auth_headers)
    first = client.get(f"/api/v1/content/{content_id}/share", headers=auth_headers).json()

    rotated = client.post(f"/api/v1/content/{content_id}/share/rotate", headers=auth_headers)
    assert rotated.status_code == 200
    new_token = rotated.json()["token"]
    assert new_token != first["token"]

    assert client.get(f"/api/v1/public/share/{first['token']}").status_code == 404
    assert client.get(f"/api/v1/public/share/{new_token}").status_code == 200


def test_private_content_cannot_be_shared(client, auth_headers):
    content_id = _create_announcement(client, auth_headers, visibility="PRIVATE")
    response = client.get(f"/api/v1/content/{content_id}/share", headers=auth_headers)
    assert response.status_code == 422


def test_public_share_detail_and_qr(client, auth_headers):
    content_id = _create_announcement(client, auth_headers, title="Compartible")
    info = client.get(f"/api/v1/content/{content_id}/share", headers=auth_headers).json()

    detail = client.get(f"/api/v1/public/share/{info['token']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["title"] == "Compartible"
    assert body["downloadable"] is False  # a text announcement has no source file

    qr = client.get(f"/api/v1/public/share/{info['token']}/qr.png")
    assert qr.status_code == 200
    assert qr.headers["content-type"] == "image/png"
    assert qr.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_unknown_token_returns_404(client):
    assert client.get("/api/v1/public/share/does-not-exist").status_code == 404
    assert client.get("/api/v1/public/share/does-not-exist/qr.png").status_code == 404
    assert client.get("/api/v1/public/share/does-not-exist/download").status_code == 404


def test_library_lists_only_local_public(client, auth_headers):
    public_id = _create_announcement(client, auth_headers, title="Público", visibility="LOCAL_PUBLIC")
    _create_announcement(client, auth_headers, title="Sólo QR", visibility="QR_ONLY")
    _create_announcement(client, auth_headers, title="Privado", visibility="PRIVATE")

    library = client.get("/api/v1/public/library")
    assert library.status_code == 200
    titles = {item["title"] for item in library.json()}
    assert titles == {"Público"}
    assert any(item["id"] == public_id for item in library.json())


def test_qr_overlay_appears_in_public_playlist(client, auth_headers):
    content_id = _create_announcement(client, auth_headers)
    _assign_playlist(client, auth_headers, "principal", [content_id], name="Con QR")

    playback = client.get("/api/v1/public/screens/principal/playlist").json()
    assert playback["status"] == "ok"
    qr = playback["items"][0]["qr"]
    assert qr is not None
    assert qr["position"] == "bottom-right"
    # The QR opens the screen's whole catalog, so it stays identical while the playlist
    # rotates instead of pointing to whichever item happens to be on air.
    assert qr["image_url"].startswith("/api/v1/public/screens/principal/library/qr.png?v=")
    assert qr["share_url"] == "http://testserver/catalog/principal"


def test_screen_library_lists_playlist_items_including_qr_only(client, auth_headers):
    public_id = _create_announcement(client, auth_headers, title="Pública", visibility="LOCAL_PUBLIC")
    qr_only_id = _create_announcement(client, auth_headers, title="Sólo QR", visibility="QR_ONLY")
    private_id = _create_announcement(client, auth_headers, title="Privada", visibility="PRIVATE")
    sala = _assign_playlist(client, auth_headers, "sala", [public_id, qr_only_id, private_id], name="Catálogo de pantalla")

    library = client.get("/api/v1/public/screens/sala/library")
    assert library.status_code == 200
    body = library.json()
    assert body["screen_name"] == sala["name"]
    # QR_ONLY is listed here (the channel that visibility exists for); PRIVATE never is.
    assert {item["title"] for item in body["items"]} == {"Pública", "Sólo QR"}

    qr = client.get("/api/v1/public/screens/sala/library/qr.png")
    assert qr.status_code == 200
    assert qr.headers["content-type"] == "image/png"


def test_screen_library_404_for_unknown_screen(client):
    assert client.get("/api/v1/public/screens/does-not-exist/library").status_code == 404
    assert client.get("/api/v1/public/screens/does-not-exist/library/qr.png").status_code == 404


def test_emergency_share_lists_items_and_downloads_zip(client, auth_headers):
    created = client.post("/api/v1/emergencies", headers=auth_headers, json={"title": "Compartir emergencia"}).json()
    content_id = created["id"]

    buffer = io.BytesIO()
    Image.new("RGB", (100, 80), color=(10, 20, 30)).save(buffer, "PNG")
    upload = client.post(
        f"/api/v1/emergencies/{content_id}/media",
        headers=auth_headers,
        files=[("photos", ("foto1.png", buffer.getvalue(), "image/png"))],
    )
    assert upload.status_code == 200

    info = client.get(f"/api/v1/content/{content_id}/share", headers=auth_headers).json()
    # An emergency with photos only has neither SOURCE nor PAGE assets; it must still be downloadable.
    detail = client.get(f"/api/v1/public/share/{info['token']}").json()
    assert detail["downloadable"] is True
    assert len(detail["items"]) == 1
    assert detail["items"][0]["kind"] == "PHOTO"
    assert detail["items"][0]["label"] == "Photo 1"
    spanish = client.get(f"/api/v1/public/share/{info['token']}", headers={"Accept-Language": "es"}).json()
    assert spanish["items"][0]["label"] == "Foto 1"

    download = client.get(f"/api/v1/public/share/{info['token']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(download.content))
    assert any(name.startswith("photo-") for name in archive.namelist())


def test_emergency_without_media_is_not_downloadable(client, auth_headers):
    created = client.post("/api/v1/emergencies", headers=auth_headers, json={"title": "Sin media"}).json()
    info = client.get(f"/api/v1/content/{created['id']}/share", headers=auth_headers).json()
    detail = client.get(f"/api/v1/public/share/{info['token']}").json()
    assert detail["downloadable"] is False
    assert detail["items"] == []
    assert client.get(f"/api/v1/public/share/{info['token']}/download").status_code == 404


def test_qr_hidden_for_private_content_in_playlist(client, auth_headers):
    content_id = _create_announcement(client, auth_headers, visibility="PRIVATE")
    _assign_playlist(client, auth_headers, "sala", [content_id], name="Privada en playlist")

    playback = client.get("/api/v1/public/screens/sala/playlist").json()
    assert playback["items"][0]["qr"] is None


def test_download_source_file_for_uploaded_image(client, auth_headers):
    from app.worker import process_one_job

    buffer = io.BytesIO()
    Image.new("RGB", (200, 150), color=(5, 5, 5)).save(buffer, "PNG")
    upload = client.post(
        "/api/v1/content/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data={"kind": "IMAGE", "title": "Foto descargable"},
        files={"file": ("foto.png", buffer.getvalue(), "image/png")},
    )
    content_id = upload.json()["id"]
    assert process_one_job() is True

    info = client.get(f"/api/v1/content/{content_id}/share", headers=auth_headers).json()
    detail = client.get(f"/api/v1/public/share/{info['token']}").json()
    assert detail["downloadable"] is True

    download = client.get(f"/api/v1/public/share/{info['token']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("image/")
    assert "foto" in download.headers.get("content-disposition", "").lower()

    again = client.get(f"/api/v1/content/{content_id}/share", headers=auth_headers).json()
    assert again["download_count"] == 1
