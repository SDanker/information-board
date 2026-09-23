"""Editing featured events (the EMERGENCY content kind) after they were created."""

import io

from PIL import Image


def _create(client, auth_headers):
    return client.post(
        "/api/v1/emergencies",
        headers=auth_headers,
        json={
            "title": "Ejercicio de compañía",
            "address": "Camino lo pinto 2019",
            "description": "Jornada de entrenamiento.",
            "sections": [{"label": "Recursos", "text": "Material mayor"}],
            "latitude": -33.2377,
            "longitude": -70.7017,
        },
    ).json()


def _photo() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (120, 80), color=(10, 20, 30)).save(buffer, "PNG")
    return buffer.getvalue()


def test_edit_title_description_and_sections_keeps_location_and_media(client, auth_headers):
    created = _create(client, auth_headers)
    client.post(
        f"/api/v1/emergencies/{created['id']}/media",
        headers=auth_headers,
        files=[("photos", ("photo.png", _photo(), "image/png"))],
    )

    response = client.patch(
        f"/api/v1/emergencies/{created['id']}",
        headers=auth_headers,
        json={
            "title": "Ejercicio de zanjas",
            "description": "Texto corregido.",
            "sections": [{"label": "Participantes", "text": "14 y 15"}],
            "address": "Camino lo pinto 2019",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Ejercicio de zanjas"
    payload = body["published_version"]["payload"]
    assert payload["description"] == "Texto corregido."
    assert payload["sections"] == [{"label": "Participantes", "text": "14 y 15"}]
    # Same address: the coordinates set before are kept.
    assert payload["latitude"] == -33.2377
    assert payload["geocode_provider"] == "manual"
    assert [asset["kind"] for asset in body["published_version"]["assets"]].count("PHOTO") == 1


def test_changing_the_address_drops_coordinates_that_no_longer_match(client, auth_headers):
    # Geocoding is disabled in tests, so the new address cannot be located.
    created = _create(client, auth_headers)
    payload = client.patch(
        f"/api/v1/emergencies/{created['id']}", headers=auth_headers, json={"address": "Otra dirección 123"}
    ).json()["published_version"]["payload"]
    assert payload["address"] == "Otra dirección 123"
    assert payload["latitude"] is None
    assert payload["longitude"] is None
    assert payload["description"] == "Jornada de entrenamiento."


def test_editing_requires_a_valid_featured_event(client, auth_headers):
    created = _create(client, auth_headers)
    assert client.patch(f"/api/v1/emergencies/{created['id']}", headers=auth_headers, json={"title": "x"}).status_code == 422

    announcement = client.post(
        "/api/v1/content", headers=auth_headers, json={"kind": "ANNOUNCEMENT", "title": "Aviso", "announcement": {"body": "Hola"}}
    ).json()
    response = client.patch(
        f"/api/v1/emergencies/{announcement['id']}", headers={**auth_headers, "Accept-Language": "es"}, json={"title": "Otro"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Acto destacado no encontrado"
