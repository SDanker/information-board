def test_create_and_list_users(client, auth_headers):
    created = client.post(
        "/api/v1/users", headers=auth_headers, json={"username": "editor1", "password": "Editor-Pass-2026", "role": "EDITOR"}
    )
    assert created.status_code == 201
    assert created.json()["role"] == "EDITOR"
    assert "password" not in created.json()
    assert "password_hash" not in created.json()

    listed = client.get("/api/v1/users", headers=auth_headers)
    assert listed.status_code == 200
    assert any(u["username"] == "editor1" for u in listed.json())


def test_duplicate_username_rejected(client, auth_headers):
    client.post("/api/v1/users", headers=auth_headers, json={"username": "dup", "password": "Password-2026", "role": "OPERATOR"})
    again = client.post("/api/v1/users", headers=auth_headers, json={"username": "dup", "password": "Password-2026", "role": "OPERATOR"})
    assert again.status_code == 409


def test_new_user_can_log_in_with_correct_role(client, auth_headers):
    client.post("/api/v1/users", headers=auth_headers, json={"username": "operador1", "password": "Operador-2026", "role": "OPERATOR"})
    login = client.post("/api/v1/auth/login", json={"username": "operador1", "password": "Operador-2026"})
    assert login.status_code == 200
    assert login.json()["role"] == "OPERATOR"
    op_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # OPERATOR can read playlists but not create them.
    assert client.get("/api/v1/playlists", headers=op_headers).status_code == 200
    assert client.post("/api/v1/playlists", headers=op_headers, json={"name": "x"}).status_code == 403


def test_cannot_delete_own_account(client, auth_headers):
    me = client.get("/api/v1/users", headers=auth_headers).json()
    admin_user = next(u for u in me if u["username"] == "admin")
    response = client.delete(f"/api/v1/users/{admin_user['id']}", headers=auth_headers)
    assert response.status_code == 422


def test_cannot_remove_last_active_admin(client, auth_headers):
    users = client.get("/api/v1/users", headers=auth_headers).json()
    admin_user = next(u for u in users if u["username"] == "admin")
    response = client.patch(f"/api/v1/users/{admin_user['id']}", headers=auth_headers, json={"is_active": False})
    assert response.status_code == 422


def test_deleting_second_admin_is_allowed(client, auth_headers):
    created = client.post(
        "/api/v1/users", headers=auth_headers, json={"username": "admin2", "password": "Admin2-Pass-2026", "role": "ADMIN"}
    ).json()
    response = client.delete(f"/api/v1/users/{created['id']}", headers=auth_headers)
    assert response.status_code == 204


def test_change_own_password(client, auth_headers):
    response = client.post(
        "/api/v1/users/me/password",
        headers=auth_headers,
        json={"current_password": "Strong-Test-Password-2026", "new_password": "Nueva-Password-2026"},
    )
    assert response.status_code == 204
    relogin = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Nueva-Password-2026"})
    assert relogin.status_code == 200


def test_change_password_rejects_wrong_current(client, auth_headers):
    response = client.post(
        "/api/v1/users/me/password", headers=auth_headers, json={"current_password": "incorrecta", "new_password": "Otra-Password-2026"}
    )
    assert response.status_code == 401


def test_audit_log_records_actions(client, auth_headers):
    client.post("/api/v1/playlists", headers=auth_headers, json={"name": "Auditada"})
    logs = client.get("/api/v1/audit-logs", headers=auth_headers)
    assert logs.status_code == 200
    actions = {(entry["action"], entry["entity_type"]) for entry in logs.json()}
    assert ("login", "auth") in actions
    assert ("create", "playlist") in actions


def test_audit_log_requires_admin(client, auth_headers):
    client.post("/api/v1/users", headers=auth_headers, json={"username": "operador2", "password": "Operador-2026", "role": "OPERATOR"})
    login = client.post("/api/v1/auth/login", json={"username": "operador2", "password": "Operador-2026"})
    op_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/audit-logs", headers=op_headers).status_code == 403


def test_system_status_reports_counts(client, auth_headers):
    response = client.get("/api/v1/system/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["screens"] == 3
    assert "storage_bytes" in body
    assert "worker_healthy" in body


def test_network_restriction_blocks_outside_allowed_range(client, auth_headers, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "allowed_networks", "10.0.0.0/8")
    try:
        blocked = client.get("/api/v1/screens", headers=auth_headers)
        assert blocked.status_code == 403
        assert client.get("/api/v1/screens", headers={**auth_headers, "Accept-Language": "es"}).json()["detail"] == (
            "Acceso administrativo no permitido desde esta red"
        )
        # Public and health routes stay open even when the restriction is active.
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/public/screens/principal").status_code in (200, 404)
    finally:
        monkeypatch.setattr(get_settings(), "allowed_networks", "")
