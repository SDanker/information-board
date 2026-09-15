from app.bootstrap import ensure_initial_data, parse_initial_screens
from app.config import Settings


def test_parse_initial_screens():
    assert parse_initial_screens("lobby:Main Lobby, hall : Hallway ,Bad Slug:X, kitchen,") == [
        ("Main Lobby", "lobby", ""),
        ("Hallway", "hall", ""),
        ("kitchen", "kitchen", ""),
    ]
    assert parse_initial_screens("") == []


def test_initial_screens_are_not_recreated_after_deletion(client, auth_headers):
    screens = client.get("/api/v1/screens", headers=auth_headers).json()
    hallway = next(s for s in screens if s["slug"] == "pasillo")
    assert client.delete(f"/api/v1/screens/{hallway['id']}", headers=auth_headers).status_code == 204

    ensure_initial_data()  # what every backend restart runs

    slugs = {s["slug"] for s in client.get("/api/v1/screens", headers=auth_headers).json()}
    assert "pasillo" not in slugs


def test_production_refuses_placeholder_secrets():
    unsafe = Settings(
        app_env="production",
        secret_key="CHANGE_ME_WITH_AT_LEAST_32_RANDOM_CHARACTERS",
        initial_admin_password="CHANGE_ME_BEFORE_USE",
        database_url="postgresql+psycopg://board:CHANGE_ME@postgres:5432/board",
    )
    assert set(unsafe.insecure_production_settings()) == {"SECRET_KEY", "INITIAL_ADMIN_PASSWORD", "DATABASE_URL"}

    safe = Settings(
        app_env="production",
        secret_key="x" * 64,
        initial_admin_password="A-Strong-Admin-Password-2026",
        database_url="postgresql+psycopg://board:a-real-password@postgres:5432/board",
    )
    assert safe.insecure_production_settings() == []
