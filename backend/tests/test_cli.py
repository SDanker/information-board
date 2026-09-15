import pytest

from app.cli import main


def _login(client, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_cli_creates_admins_resets_passwords_and_lists_users(client, capsys):
    assert main(["create-admin", "--username", "maria", "--password", "Maria-Pass-2026"]) == 0
    assert main(["create-admin", "--username", "maria", "--password", "Maria-Pass-2026"]) == 1
    login = _login(client, "maria", "Maria-Pass-2026")
    assert login.status_code == 200
    assert login.json()["role"] == "ADMIN"

    assert main(["reset-password", "--username", "maria", "--password", "Changed-Pass-2026"]) == 0
    assert _login(client, "maria", "Maria-Pass-2026").status_code == 401
    assert _login(client, "maria", "Changed-Pass-2026").status_code == 200
    assert main(["reset-password", "--username", "ghost", "--password", "Changed-Pass-2026"]) == 1

    capsys.readouterr()
    assert main(["list-users"]) == 0
    output = capsys.readouterr().out
    assert "maria\tADMIN\tactive" in output
    assert "admin\tADMIN\tactive" in output


def test_cli_reset_can_reactivate_an_account(client, auth_headers):
    created = client.post(
        "/api/v1/users", headers=auth_headers, json={"username": "locked", "password": "Locked-Pass-2026", "role": "EDITOR"}
    ).json()
    client.patch(f"/api/v1/users/{created['id']}", headers=auth_headers, json={"is_active": False})
    assert _login(client, "locked", "Locked-Pass-2026").status_code == 401

    assert main(["reset-password", "--username", "locked", "--password", "Unlocked-Pass-2026", "--activate"]) == 0
    assert _login(client, "locked", "Unlocked-Pass-2026").status_code == 200


def test_cli_rejects_short_passwords(client):
    with pytest.raises(SystemExit):
        main(["create-admin", "--username", "shorty", "--password", "short"])
