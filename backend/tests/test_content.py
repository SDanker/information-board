def test_announcement_lifecycle(client, auth_headers):
    created = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={
            "kind": "ANNOUNCEMENT",
            "title": "Bienvenida",
            "announcement": {"body": "Hola compañía", "background": "brand"},
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["kind"] == "ANNOUNCEMENT"
    assert body["published_version"]["status"] == "READY"
    assert body["published_version"]["payload"]["body"] == "Hola compañía"
    content_id = body["id"]

    listed = client.get("/api/v1/content", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == content_id for item in listed.json())

    fetched = client.get(f"/api/v1/content/{content_id}", headers=auth_headers)
    assert fetched.status_code == 200

    updated = client.patch(f"/api/v1/content/{content_id}", headers=auth_headers, json={"title": "Bienvenida 2026"})
    assert updated.status_code == 200
    assert updated.json()["title"] == "Bienvenida 2026"

    new_version = client.post(
        f"/api/v1/content/{content_id}/versions",
        headers=auth_headers,
        json={"kind": "ANNOUNCEMENT", "title": "irrelevante", "announcement": {"body": "Texto actualizado"}},
    )
    assert new_version.status_code == 201
    assert new_version.json()["published_version"]["version_number"] == 2
    assert new_version.json()["published_version"]["payload"]["body"] == "Texto actualizado"

    deleted = client.delete(f"/api/v1/content/{content_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/content/{content_id}", headers=auth_headers).status_code == 404
    listed_after = client.get("/api/v1/content", headers=auth_headers)
    assert all(item["id"] != content_id for item in listed_after.json())


def test_content_requires_authentication(client):
    assert client.get("/api/v1/content").status_code == 401


def test_announcement_requires_payload(client, auth_headers):
    response = client.post(
        "/api/v1/content", headers=auth_headers, json={"kind": "ANNOUNCEMENT", "title": "Sin cuerpo"}
    )
    assert response.status_code == 422


def test_unsupported_kind_rejected_for_now(client, auth_headers):
    response = client.post(
        "/api/v1/content", headers=auth_headers, json={"kind": "IMAGE", "title": "Imagen"}
    )
    assert response.status_code == 422
