import pytest
from starlette.websockets import WebSocketDisconnect


def test_screen_socket_rejects_unknown_slug(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/screens/no-existe"):
            pass


def test_screen_socket_accepts_known_slug(client):
    with client.websocket_connect("/ws/screens/principal") as ws:
        ws.close()


def test_admin_socket_rejects_missing_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/admin"):
            pass


def test_admin_socket_accepts_valid_token(client, auth_headers):
    token = auth_headers["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(f"/ws/admin?token={token}") as ws:
        ws.close()
