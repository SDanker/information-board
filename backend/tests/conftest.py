import os
import tempfile

# Settings are read once per process, so the test environment must be fully defined before
# the application is imported. Values are set explicitly (not only when missing) so a
# container's real .env can never leak into the tests.
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": "sqlite://",
        "REDIS_URL": "redis://unused:6379/0",
        "TESTING": "true",
        "SECRET_KEY": "test-secret-key-that-is-long-enough",
        "INITIAL_ADMIN_USERNAME": "admin",
        "INITIAL_ADMIN_PASSWORD": "Strong-Test-Password-2026",
        "INITIAL_SCREENS": "principal:Pantalla Principal,pasillo:Pantalla Pasillo,sala:Pantalla Sala",
        "DEFAULT_LANGUAGE": "en",
        "ALLOWED_NETWORKS": "",
        "PUBLIC_BASE_URL": "",
        "GEOCODING_ENABLED": "false",
        "STORAGE_BACKEND": "local",
        "STORAGE_ROOT": tempfile.mkdtemp(prefix="board-test-storage-"),
    }
)

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client: TestClient) -> dict:
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Strong-Test-Password-2026"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
