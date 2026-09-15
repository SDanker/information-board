"""Smoke test of a running deployment, executed inside the backend container.

    docker compose exec -T backend python - < scripts/deployment_smoke.py

It signs in with INITIAL_ADMIN_USERNAME / INITIAL_ADMIN_PASSWORD from the container environment
(never printed). If that password was changed after the first start, pass the current one:

    docker compose exec -T -e SMOKE_PASSWORD='current-password' backend python - < scripts/deployment_smoke.py

Temporary data created by the checks is removed at the end.
"""

import os

import httpx


def main() -> None:
    username = os.environ.get("SMOKE_USERNAME") or os.environ["INITIAL_ADMIN_USERNAME"]
    password = os.environ.get("SMOKE_PASSWORD") or os.environ["INITIAL_ADMIN_PASSWORD"]

    with httpx.Client(base_url="http://nginx", timeout=15) as client:
        health = client.get("/api/v1/health")
        health.raise_for_status()
        assert health.json() == {"status": "ok", "database": "ok", "redis": "ok"}, health.json()

        branding = client.get("/api/v1/public/branding")
        branding.raise_for_status()
        assert branding.json()["app_name"], "branding without an application name"

        assert client.get("/api/v1/screens").status_code == 401
        login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        screens = client.get("/api/v1/screens", headers=headers)
        screens.raise_for_status()
        assert screens.json(), "there are no screens"
        screen = screens.json()[0]

        for route in ("/login", "/admin", "/admin/settings", "/library", f"/screen/{screen['slug']}", f"/catalog/{screen['slug']}"):
            client.get(route).raise_for_status()
        print("PASS: nginx routes, PostgreSQL, Redis, branding, sign-in and access control")

        content = client.post(
            "/api/v1/content",
            headers=headers,
            json={"kind": "ANNOUNCEMENT", "title": "__smoke__", "announcement": {"body": "Deployment check"}},
        )
        content.raise_for_status()
        content_id = content.json()["id"]
        assert content.json()["published_version"]["status"] == "READY"
        playlist = client.post("/api/v1/playlists", headers=headers, json={"name": "__smoke__"})
        playlist.raise_for_status()
        playlist_id = playlist.json()["id"]
        client.post(
            f"/api/v1/playlists/{playlist_id}/items", headers=headers, json={"content_id": content_id, "duration_seconds": 9}
        ).raise_for_status()

        previous_playlist_id = screen.get("playlist_id")
        try:
            client.patch(f"/api/v1/screens/{screen['id']}", headers=headers, json={"playlist_id": playlist_id}).raise_for_status()
            playback = client.get(f"/api/v1/public/screens/{screen['slug']}/playlist")
            playback.raise_for_status()
            body = playback.json()
            assert body["status"] == "ok", body
            assert body["items"][0]["payload"]["body"] == "Deployment check"
            assert body["items"][0]["duration_seconds"] == 9
        finally:
            # Leave the screen as it was and remove the temporary data.
            client.patch(f"/api/v1/screens/{screen['id']}", headers=headers, json={"playlist_id": previous_playlist_id})
            client.delete(f"/api/v1/playlists/{playlist_id}", headers=headers)
            client.delete(f"/api/v1/content/{content_id}", headers=headers)
        print("PASS: content, playlists and public playback")


if __name__ == "__main__":
    main()
