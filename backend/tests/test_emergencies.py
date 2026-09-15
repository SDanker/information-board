import io

from PIL import Image


def _png_bytes(width=300, height=200) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(220, 30, 30)).save(buffer, "PNG")
    return buffer.getvalue()


def test_create_emergency_with_manual_coordinates(client, auth_headers):
    response = client.post(
        "/api/v1/emergencies",
        headers=auth_headers,
        json={
            "title": "Incendio estructural",
            "address": "Av. Siempre Viva 742",
            "description": "Incendio en segundo piso, en control.",
            "sections": [{"label": "Recursos", "text": "2 carros bomba"}],
            "latitude": -33.45,
            "longitude": -70.65,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "EMERGENCY"
    assert body["published_version"]["status"] == "READY"
    payload = body["published_version"]["payload"]
    assert payload["latitude"] == -33.45
    assert payload["geocode_provider"] == "manual"
    assert payload["sections"] == [{"label": "Recursos", "text": "2 carros bomba"}]


def test_create_emergency_without_coordinates_does_not_fail(client, auth_headers):
    # Without coordinates or an address nothing is geocoded, and it is published anyway.
    response = client.post(
        "/api/v1/emergencies",
        headers=auth_headers,
        json={"title": "Aviso preventivo", "description": "Corte de agua programado."},
    )
    assert response.status_code == 201
    payload = response.json()["published_version"]["payload"]
    assert payload["latitude"] is None
    assert payload["geocode_provider"] is None


def test_manual_location_correction(client, auth_headers):
    created = client.post(
        "/api/v1/emergencies", headers=auth_headers, json={"title": "Rescate", "address": "dirección inexistente xyz"}
    ).json()
    updated = client.patch(
        f"/api/v1/emergencies/{created['id']}/location", headers=auth_headers, json={"latitude": -33.1, "longitude": -70.9}
    )
    assert updated.status_code == 200
    payload = updated.json()["published_version"]["payload"]
    assert payload["latitude"] == -33.1
    assert payload["geocode_provider"] == "manual"


def test_upload_photos_are_processed_synchronously(client, auth_headers):
    created = client.post("/api/v1/emergencies", headers=auth_headers, json={"title": "Con fotos"}).json()
    content_id = created["id"]

    response = client.post(
        f"/api/v1/emergencies/{content_id}/media",
        headers=auth_headers,
        files=[("photos", ("foto1.png", _png_bytes(), "image/png")), ("photos", ("foto2.png", _png_bytes(), "image/png"))],
    )
    assert response.status_code == 200
    assets = response.json()["published_version"]["assets"]
    photos = [a for a in assets if a["kind"] == "PHOTO"]
    assert len(photos) == 2
    assert {a["page_number"] for a in photos} == {1, 2}

    served = client.get(f"/api/v1/public/assets/{photos[0]['id']}/file")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"


def test_upload_rejects_a_photo_that_is_not_an_image(client, auth_headers):
    created = client.post("/api/v1/emergencies", headers=auth_headers, json={"title": "Foto rota"}).json()
    response = client.post(
        f"/api/v1/emergencies/{created['id']}/media",
        headers=auth_headers,
        files=[("photos", ("broken.png", b"this is not a png", "image/png"))],
    )
    assert response.status_code == 422


def test_delete_emergency_media(client, auth_headers):
    created = client.post("/api/v1/emergencies", headers=auth_headers, json={"title": "Para borrar"}).json()
    content_id = created["id"]
    uploaded = client.post(
        f"/api/v1/emergencies/{content_id}/media",
        headers=auth_headers,
        files=[("photos", ("foto.png", _png_bytes(), "image/png"))],
    ).json()
    photo_id = next(a["id"] for a in uploaded["published_version"]["assets"] if a["kind"] == "PHOTO")

    deleted = client.delete(f"/api/v1/emergencies/{content_id}/media/{photo_id}", headers=auth_headers)
    assert deleted.status_code == 200
    remaining = [a for a in deleted.json()["published_version"]["assets"] if a["kind"] == "PHOTO"]
    assert remaining == []


def test_broadcast_and_clear_emergency(client, auth_headers):
    created = client.post(
        "/api/v1/emergencies", headers=auth_headers, json={"title": "Emergencia activa", "description": "Evacuar sector norte"}
    ).json()
    content_id = created["id"]

    idle = client.get("/api/v1/public/active-emergency")
    assert idle.json()["status"] == "empty"

    broadcast = client.post(f"/api/v1/emergencies/{content_id}/broadcast", headers=auth_headers)
    assert broadcast.status_code == 200

    active = client.get("/api/v1/public/active-emergency")
    assert active.json()["status"] == "ok"
    assert active.json()["items"][0]["content_id"] == content_id
    assert active.json()["items"][0]["payload"]["description"] == "Evacuar sector norte"

    status_check = client.get("/api/v1/emergencies/active-status", headers=auth_headers)
    assert status_check.json() == {"active": True, "content_id": content_id}

    cleared = client.post("/api/v1/emergencies/clear-broadcast", headers=auth_headers)
    assert cleared.status_code == 204

    after = client.get("/api/v1/public/active-emergency")
    assert after.json()["status"] == "empty"


def test_emergency_endpoints_require_editor_role(client):
    assert client.post("/api/v1/emergencies", json={"title": "x"}).status_code == 401
    assert client.get("/api/v1/public/active-emergency").status_code == 200  # public, no session needed


def test_upload_video_only_without_photos(client, auth_headers):
    created = client.post("/api/v1/emergencies", headers=auth_headers, json={"title": "Solo video"}).json()
    content_id = created["id"]

    # The bytes do not need to be a real MP4: this checks that "video" is accepted without
    # any "photos" field (a missing field means an empty list).
    response = client.post(
        f"/api/v1/emergencies/{content_id}/media",
        headers=auth_headers,
        files={"video": ("clip.mp4", b"test-content-not-a-real-mp4", "video/mp4")},
    )
    assert response.status_code == 200
    assets = response.json()["published_version"]["assets"]
    assert any(a["kind"] == "SOURCE" for a in assets)
    assert [a for a in assets if a["kind"] == "PHOTO"] == []
