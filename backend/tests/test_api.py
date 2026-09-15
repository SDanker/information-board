def login(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Strong-Test-Password-2026"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "ok"}


def test_login_rejects_invalid_password(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "incorrect-password"})
    assert response.status_code == 401


def test_screens_require_authentication(client):
    assert client.get("/api/v1/screens").status_code == 401


def test_screen_crud_and_public_heartbeat(client):
    headers = login(client)
    initial = client.get("/api/v1/screens", headers=headers)
    assert initial.status_code == 200
    assert {item["slug"] for item in initial.json()} == {"principal", "pasillo", "sala"}

    created = client.post(
        "/api/v1/screens",
        headers=headers,
        json={
            "name": "Pantalla Taller",
            "slug": "taller",
            "description": "Zona de capacitación",
            "expected_resolution": "1920x1080",
            "orientation": "landscape",
            "is_active": True,
        },
    )
    assert created.status_code == 201
    screen_id = created.json()["id"]

    heartbeat = client.post("/api/v1/public/screens/taller/heartbeat", json={"resolution": "1366x768"})
    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "ONLINE"
    assert heartbeat.json()["expected_resolution"] == "1366x768"

    updated = client.patch(f"/api/v1/screens/{screen_id}", headers=headers, json={"description": "Actualizada"})
    assert updated.status_code == 200
    assert updated.json()["description"] == "Actualizada"

    assert client.delete(f"/api/v1/screens/{screen_id}", headers=headers).status_code == 204
    assert client.get("/api/v1/public/screens/taller").status_code == 404
