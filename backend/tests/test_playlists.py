def _create_announcement(client, auth_headers, title="Anuncio", body="Hola"):
    response = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "ANNOUNCEMENT", "title": title, "announcement": {"body": body}},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_playlist_crud_and_items(client, auth_headers):
    content_id = _create_announcement(client, auth_headers)

    created = client.post(
        "/api/v1/playlists", headers=auth_headers, json={"name": "Principal", "description": "Rotación de entrada"}
    )
    assert created.status_code == 201
    playlist_id = created.json()["id"]
    assert created.json()["screen_count"] == 0

    added = client.post(
        f"/api/v1/playlists/{playlist_id}/items",
        headers=auth_headers,
        json={"content_id": content_id, "duration_seconds": 20},
    )
    assert added.status_code == 201
    items = added.json()["items"]
    assert len(items) == 1
    assert items[0]["content"]["id"] == content_id
    assert items[0]["scheduled_now"] is True
    item_id = items[0]["id"]

    second_content = _create_announcement(client, auth_headers, title="Segundo", body="Otro mensaje")
    added2 = client.post(
        f"/api/v1/playlists/{playlist_id}/items", headers=auth_headers, json={"content_id": second_content}
    )
    assert added2.status_code == 201
    item_ids = [item["id"] for item in added2.json()["items"]]
    assert len(item_ids) == 2

    reordered = client.post(
        f"/api/v1/playlists/{playlist_id}/reorder", headers=auth_headers, json={"item_ids": list(reversed(item_ids))}
    )
    assert reordered.status_code == 200
    assert [item["id"] for item in reordered.json()["items"]] == list(reversed(item_ids))

    removed = client.delete(f"/api/v1/playlists/{playlist_id}/items/{item_id}", headers=auth_headers)
    assert removed.status_code == 200
    assert len(removed.json()["items"]) == 1

    deleted = client.delete(f"/api/v1/playlists/{playlist_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/playlists/{playlist_id}", headers=auth_headers).status_code == 404


def test_assigning_playlist_to_screen_and_public_playback(client, auth_headers):
    content_id = _create_announcement(client, auth_headers, body="Contenido en vivo")
    playlist = client.post("/api/v1/playlists", headers=auth_headers, json={"name": "TV Principal"}).json()
    client.post(
        f"/api/v1/playlists/{playlist['id']}/items",
        headers=auth_headers,
        json={"content_id": content_id, "duration_seconds": 12},
    )

    screens = client.get("/api/v1/screens", headers=auth_headers).json()
    principal = next(s for s in screens if s["slug"] == "principal")

    empty = client.get("/api/v1/public/screens/principal/playlist")
    assert empty.status_code == 200
    assert empty.json()["status"] == "empty"

    assign = client.patch(
        f"/api/v1/screens/{principal['id']}", headers=auth_headers, json={"playlist_id": playlist["id"]}
    )
    assert assign.status_code == 200
    assert assign.json()["playlist_id"] == playlist["id"]

    playback = client.get("/api/v1/public/screens/principal/playlist")
    assert playback.status_code == 200
    body = playback.json()
    assert body["status"] == "ok"
    assert len(body["items"]) == 1
    assert body["items"][0]["payload"]["body"] == "Contenido en vivo"
    assert body["items"][0]["duration_seconds"] == 12

    reloaded = client.get(f"/api/v1/playlists/{playlist['id']}", headers=auth_headers)
    assert reloaded.json()["screen_count"] == 1


def test_assign_nonexistent_playlist_returns_404(client, auth_headers):
    screens = client.get("/api/v1/screens", headers=auth_headers).json()
    screen_id = screens[0]["id"]
    response = client.patch(
        f"/api/v1/screens/{screen_id}",
        headers=auth_headers,
        json={"playlist_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


def test_deleting_playlist_unassigns_screens(client, auth_headers):
    content_id = _create_announcement(client, auth_headers)
    playlist = client.post("/api/v1/playlists", headers=auth_headers, json={"name": "Temporal"}).json()
    client.post(f"/api/v1/playlists/{playlist['id']}/items", headers=auth_headers, json={"content_id": content_id})
    screens = client.get("/api/v1/screens", headers=auth_headers).json()
    screen_id = screens[0]["id"]
    client.patch(f"/api/v1/screens/{screen_id}", headers=auth_headers, json={"playlist_id": playlist["id"]})

    client.delete(f"/api/v1/playlists/{playlist['id']}", headers=auth_headers)

    refreshed = client.get("/api/v1/screens", headers=auth_headers).json()
    updated_screen = next(s for s in refreshed if s["id"] == screen_id)
    assert updated_screen["playlist_id"] is None
