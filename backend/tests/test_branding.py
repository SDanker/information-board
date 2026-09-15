import io

from PIL import Image


def _png(width=900, height=300) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (width, height), color=(255, 0, 0, 128)).save(buffer, "PNG")
    return buffer.getvalue()


def _branding(client) -> dict:
    return client.get("/api/v1/public/branding").json()


def test_public_branding_uses_environment_defaults(client):
    body = _branding(client)
    assert body["app_name"] == "Information Board"
    assert body["default_language"] == "en"
    assert body["date_locale"] == "en-US"
    assert body["logo_url"] is None
    assert body["display"]["default_item_seconds"] == 15
    assert body["public_library_enabled"] is True


def test_admin_can_update_branding(client, auth_headers):
    payload = _branding(client)
    payload.update(
        app_name="Fire Station 14",
        organization_name="14th Company",
        primary_color="#B91C1C",
        default_language="es",
        date_locale="es-CL",
        timezone="America/Santiago",
        page_labels={"content": "Posts", "library": "   "},
        public_library_enabled=False,
    )
    payload["display"].update(show_qr=False, emergency_pane_seconds=10)

    response = client.put("/api/v1/branding", headers=auth_headers, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["primary_color"] == "#b91c1c"
    assert body["page_labels"] == {"content": "Posts"}  # blank labels fall back to the default name
    assert body["display"]["emergency_pane_seconds"] == 10
    assert _branding(client)["app_name"] == "Fire Station 14"
    assert client.get("/api/v1/public/library").status_code == 404


def test_branding_validation_rejects_bad_values(client, auth_headers):
    base = _branding(client)
    invalid_values = {
        "primary_color": "red",
        "timezone": "Mars/Olympus_Mons",
        "page_labels": {"not-a-page": "x"},
        "app_name": "   ",
        "date_locale": "not a locale",
    }
    for field, value in invalid_values.items():
        response = client.put("/api/v1/branding", headers=auth_headers, json={**base, field: value})
        assert response.status_code == 422, field


def test_branding_changes_require_an_administrator(client, auth_headers):
    client.post("/api/v1/users", headers=auth_headers, json={"username": "editor9", "password": "Editor-Pass-2026", "role": "EDITOR"})
    token = client.post("/api/v1/auth/login", json={"username": "editor9", "password": "Editor-Pass-2026"}).json()["access_token"]
    editor_headers = {"Authorization": f"Bearer {token}"}

    assert client.put("/api/v1/branding", headers=editor_headers, json=_branding(client)).status_code == 403
    assert client.post("/api/v1/branding/logo", headers=editor_headers, files={"file": ("logo.png", _png(), "image/png")}).status_code == 403


def test_reset_restores_environment_defaults(client, auth_headers):
    client.put("/api/v1/branding", headers=auth_headers, json={**_branding(client), "app_name": "Temporary"})
    assert _branding(client)["app_name"] == "Temporary"

    reset = client.delete("/api/v1/branding", headers=auth_headers)

    assert reset.status_code == 200
    assert reset.json()["app_name"] == "Information Board"


def test_logo_upload_serve_and_delete(client, auth_headers):
    uploaded = client.post("/api/v1/branding/logo", headers=auth_headers, files={"file": ("logo.png", _png(), "image/png")})
    assert uploaded.status_code == 200
    logo_url = uploaded.json()["logo_url"]
    assert logo_url.startswith("/api/v1/public/branding/logo?v=")

    served = client.get(logo_url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    image = Image.open(io.BytesIO(served.content))
    assert max(image.size) <= 512  # normalized size
    assert image.mode == "RGBA"  # transparency kept

    replaced = client.post("/api/v1/branding/logo", headers=auth_headers, files={"file": ("logo.png", _png(200, 200), "image/png")})
    assert replaced.json()["logo_url"] != logo_url  # a new version busts browser caches

    deleted = client.delete("/api/v1/branding/logo", headers=auth_headers)
    assert deleted.status_code == 200
    assert deleted.json()["logo_url"] is None
    assert client.get("/api/v1/public/branding/logo").status_code == 404


def test_logo_upload_rejects_unsupported_files(client, auth_headers):
    svg = client.post("/api/v1/branding/logo", headers=auth_headers, files={"file": ("logo.svg", b"<svg/>", "image/svg+xml")})
    assert svg.status_code == 422
    fake = client.post("/api/v1/branding/logo", headers=auth_headers, files={"file": ("logo.png", b"not an image", "image/png")})
    assert fake.status_code == 422


def test_display_settings_control_the_qr_overlay(client, auth_headers):
    content = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "ANNOUNCEMENT", "title": "Con QR", "announcement": {"body": "Hola"}},
    ).json()
    playlist = client.post("/api/v1/playlists", headers=auth_headers, json={"name": "QR"}).json()
    client.post(f"/api/v1/playlists/{playlist['id']}/items", headers=auth_headers, json={"content_id": content["id"]})
    principal = next(s for s in client.get("/api/v1/screens", headers=auth_headers).json() if s["slug"] == "principal")
    client.patch(f"/api/v1/screens/{principal['id']}", headers=auth_headers, json={"playlist_id": playlist["id"]})

    branding = _branding(client)
    branding["display"].update(show_qr=True, qr_position="top-left", qr_message="Scan me")
    client.put("/api/v1/branding", headers=auth_headers, json=branding)
    qr = client.get("/api/v1/public/screens/principal/playlist").json()["items"][0]["qr"]
    assert qr["position"] == "top-left"
    assert qr["message"] == "Scan me"

    branding["display"]["show_qr"] = False
    client.put("/api/v1/branding", headers=auth_headers, json=branding)
    assert client.get("/api/v1/public/screens/principal/playlist").json()["items"][0]["qr"] is None
