import re
from pathlib import Path

from app.i18n import normalize_language, translate
from app.locales import es

APP_DIR = Path(__file__).resolve().parent.parent / "app"
_MESSAGE_CALL = re.compile(r'\b_\(\s*"((?:[^"\\]|\\.)*)"')
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def test_normalize_language_picks_the_best_supported_match():
    assert normalize_language("es-CL,es;q=0.9,en;q=0.8") == "es"
    assert normalize_language("fr-FR,en;q=0.5") == "en"
    assert normalize_language("en;q=0.2, es;q=0.9") == "es"
    assert normalize_language("de") is None
    assert normalize_language(None) is None


def test_translate_fills_placeholders():
    assert translate("Invalid role: {role}", "es", role="X") == "Rol inválido: X"
    assert translate("Invalid role: {role}", "en", role="X") == "Invalid role: X"
    assert translate("A message without translation", "es") == "A message without translation"


def test_every_translatable_message_has_a_spanish_translation():
    missing = sorted(
        {
            message
            for path in APP_DIR.rglob("*.py")
            for message in _MESSAGE_CALL.findall(path.read_text(encoding="utf-8"))
            if message not in es.MESSAGES
        }
    )
    assert not missing, f"Missing Spanish translations: {missing}"


def test_translations_keep_the_same_placeholders():
    for source, translated in es.MESSAGES.items():
        assert set(_PLACEHOLDER.findall(source)) == set(_PLACEHOLDER.findall(translated)), source


def test_api_errors_follow_the_request_language(client):
    credentials = {"username": "nobody", "password": "wrong-password"}
    english = client.post("/api/v1/auth/login", json=credentials)
    assert english.json()["detail"] == "Incorrect username or password"

    spanish = client.post("/api/v1/auth/login", json=credentials, headers={"Accept-Language": "es-CL,es;q=0.9"})
    assert spanish.json()["detail"] == "Usuario o contraseña incorrectos"

    # X-Language (set by the frontend from the user's choice) wins over the browser header.
    explicit = client.post("/api/v1/auth/login", json=credentials, headers={"Accept-Language": "es", "X-Language": "en"})
    assert explicit.json()["detail"] == "Incorrect username or password"


def test_validation_messages_are_translated(client, auth_headers):
    response = client.post(
        "/api/v1/screens",
        headers={**auth_headers, "Accept-Language": "es"},
        json={"name": "Lobby", "slug": "Not A Slug!", "expected_resolution": "1920x1080"},
    )
    assert response.status_code == 422
    assert "El slug sólo admite minúsculas" in response.text
