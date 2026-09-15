import ipaddress

from starlette.requests import Request

from app.config import get_settings
from app.network import client_ip, is_loopback_url, parse_networks, public_base_url


def _request(headers: dict | None = None, peer: str = "172.18.0.5") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "query_string": b"",
            "server": ("backend", 8000),
            "client": (peer, 50000),
            "headers": [(name.lower().encode(), value.encode()) for name, value in (headers or {}).items()],
        }
    )


def test_automatic_address_follows_the_host_used(monkeypatch):
    monkeypatch.setattr(get_settings(), "public_base_url", "")
    assert public_base_url(_request({"host": "10.1.2.3:8085"})) == "http://10.1.2.3:8085"
    assert public_base_url(_request({"host": "board.lan"})) == "http://board.lan"
    assert public_base_url(_request({"host": "[fd00::5]:8080"})) == "http://[fd00::5]:8080"


def test_automatic_address_honors_proxy_headers_and_default_ports(monkeypatch):
    monkeypatch.setattr(get_settings(), "public_base_url", "auto")
    assert public_base_url(_request({"host": "board.example.org:443", "x-forwarded-proto": "https"})) == "https://board.example.org"
    assert public_base_url(_request({"host": "192.168.1.9:80"})) == "http://192.168.1.9"
    assert (
        public_base_url(_request({"host": "backend:8000", "x-forwarded-host": "board.example.org", "x-forwarded-proto": "https, http"}))
        == "https://board.example.org"
    )


def test_malformed_host_never_reaches_links(monkeypatch):
    monkeypatch.setattr(get_settings(), "public_base_url", "")
    assert public_base_url(_request({"host": "evil.example/phish?x="})) == "http://localhost"
    assert public_base_url(_request({"host": "user@evil.example"})) == "http://localhost"
    assert public_base_url(_request({"host": "board.lan", "x-forwarded-proto": "javascript"})) == "http://board.lan"


def test_fixed_address_wins_over_the_request(monkeypatch):
    monkeypatch.setattr(get_settings(), "public_base_url", "https://board.example.org/")
    assert public_base_url(_request({"host": "10.0.0.5"})) == "https://board.example.org"


def test_loopback_detection():
    assert is_loopback_url("http://localhost:8080")
    assert is_loopback_url("http://127.0.0.1")
    assert is_loopback_url("http://[::1]:3000")
    assert not is_loopback_url("http://192.168.1.50")
    assert not is_loopback_url("https://board.example.org")


def test_client_ip_trusts_x_real_ip_only_from_private_proxies():
    assert client_ip(_request({"x-real-ip": "192.168.1.40"}, peer="172.18.0.5")) == "192.168.1.40"
    # A public peer could forge the header, so its own address is used instead.
    assert client_ip(_request({"x-real-ip": "10.0.0.1"}, peer="8.8.4.4")) == "8.8.4.4"
    assert client_ip(_request({"x-real-ip": "not-an-ip"}, peer="172.18.0.5")) == "172.18.0.5"
    assert client_ip(_request(peer="172.18.0.5")) == "172.18.0.5"


def test_private_keyword_covers_every_private_range():
    networks = parse_networks("private, 203.0.113.0/24, not-a-network")

    def allowed(address: str) -> bool:
        return any(ipaddress.ip_address(address) in network for network in networks)

    for address in ("192.168.50.3", "10.9.8.7", "172.20.1.1", "127.0.0.1", "fd12::1", "203.0.113.7"):
        assert allowed(address), address
    assert not allowed("8.8.8.8")


def _playlist_with_announcement(client, auth_headers, slug="principal"):
    content = client.post(
        "/api/v1/content",
        headers=auth_headers,
        json={"kind": "ANNOUNCEMENT", "title": "Network", "library_visibility": "LOCAL_PUBLIC", "announcement": {"body": "Hi"}},
    ).json()
    playlist = client.post("/api/v1/playlists", headers=auth_headers, json={"name": "Network"}).json()
    client.post(f"/api/v1/playlists/{playlist['id']}/items", headers=auth_headers, json={"content_id": content["id"]})
    screen = next(s for s in client.get("/api/v1/screens", headers=auth_headers).json() if s["slug"] == slug)
    client.patch(f"/api/v1/screens/{screen['id']}", headers=auth_headers, json={"playlist_id": playlist["id"]})
    return content["id"]


def test_links_and_qr_codes_follow_the_address_each_device_uses(client, auth_headers):
    content_id = _playlist_with_announcement(client, auth_headers)

    first = client.get("/api/v1/public/screens/principal/playlist", headers={"host": "10.20.30.40:8085"}).json()["items"][0]["qr"]
    assert first["share_url"] == "http://10.20.30.40:8085/catalog/principal"
    moved = client.get("/api/v1/public/screens/principal/playlist", headers={"host": "board.lan"}).json()["items"][0]["qr"]
    assert moved["share_url"] == "http://board.lan/catalog/principal"
    assert moved["image_url"] != first["image_url"]  # new fingerprint, so the TV never reuses a cached code

    catalog = client.get("/api/v1/public/screens/principal/library", headers={"host": "board.lan"}).json()
    assert catalog["items"][0]["share_url"].startswith("http://board.lan/share/")
    library = client.get("/api/v1/public/library", headers={"host": "192.168.7.7"}).json()
    assert library[0]["share_url"].startswith("http://192.168.7.7/share/")
    info = client.get(f"/api/v1/content/{content_id}/share", headers={**auth_headers, "host": "192.168.7.7"}).json()
    assert info["share_url"].startswith("http://192.168.7.7/share/")
    assert "?v=" in info["qr_url"]


def test_system_status_reports_the_public_address(client, auth_headers, monkeypatch):
    body = client.get("/api/v1/system/status", headers={**auth_headers, "host": "localhost:8080"}).json()
    assert body["public_base_url"] == "http://localhost:8080"
    assert body["public_base_url_mode"] == "auto"
    assert body["public_base_url_is_loopback"] is True

    monkeypatch.setattr(get_settings(), "public_base_url", "http://board.lan")
    body = client.get("/api/v1/system/status", headers=auth_headers).json()
    assert body["public_base_url"] == "http://board.lan"
    assert body["public_base_url_mode"] == "fixed"
    assert body["public_base_url_is_loopback"] is False


def test_private_keyword_in_network_restriction(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "allowed_networks", "private")
    assert client.get("/api/v1/screens", headers={**auth_headers, "x-real-ip": "192.168.3.10"}).status_code == 200
    assert client.get("/api/v1/screens", headers={**auth_headers, "x-real-ip": "8.8.8.8"}).status_code == 403
