import pytest

from app.config import get_settings
from app.geocoding import GeocodeResult, _geocode_cached, geocode_address


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def geocoding_enabled(monkeypatch):
    # The test environment disables geocoding so other tests never reach the Internet.
    monkeypatch.setattr(get_settings(), "geocoding_enabled", True)
    _geocode_cached.cache_clear()
    yield
    _geocode_cached.cache_clear()


def test_geocode_restricts_to_configured_country(monkeypatch):
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured.update(url=url, params=params, headers=headers)
        return _FakeResponse([{"lat": "-33.45", "lon": "-70.65", "display_name": "Santiago, Chile"}])

    monkeypatch.setattr(get_settings(), "geocode_country_codes", "cl")
    monkeypatch.setattr(get_settings(), "geocode_url", "https://geocoder.example/search")
    monkeypatch.setattr("app.geocoding.httpx.get", fake_get)

    result = geocode_address("Alameda 1234")

    assert captured["url"] == "https://geocoder.example/search"
    assert captured["params"]["countrycodes"] == "cl"
    assert captured["headers"]["User-Agent"]
    assert isinstance(result, GeocodeResult)
    assert result.latitude == -33.45
    assert result.longitude == -70.65


def test_geocode_without_country_restriction(monkeypatch):
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured["params"] = params
        return _FakeResponse([{"lat": "1", "lon": "2"}])

    monkeypatch.setattr(get_settings(), "geocode_country_codes", "")
    monkeypatch.setattr("app.geocoding.httpx.get", fake_get)

    assert geocode_address("Somewhere 1") is not None
    assert "countrycodes" not in captured["params"]


def test_geocode_disabled_never_calls_the_network(monkeypatch):
    def fake_get(*args, **kwargs):
        raise AssertionError("geocoding is disabled and must not call the network")

    monkeypatch.setattr(get_settings(), "geocoding_enabled", False)
    monkeypatch.setattr("app.geocoding.httpx.get", fake_get)

    assert geocode_address("Alameda 1234") is None


def test_geocode_empty_address_returns_none():
    assert geocode_address("") is None
    assert geocode_address("   ") is None


def test_geocode_returns_none_on_network_error(monkeypatch):
    import httpx

    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr("app.geocoding.httpx.get", fake_get)

    assert geocode_address("Any address without network 999") is None


def test_geocode_returns_none_when_no_results(monkeypatch):
    def fake_get(url, params, headers, timeout):
        return _FakeResponse([])

    monkeypatch.setattr("app.geocoding.httpx.get", fake_get)

    assert geocode_address("Address without results 123") is None
