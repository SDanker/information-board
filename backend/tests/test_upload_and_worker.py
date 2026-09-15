import io
import uuid

from PIL import Image

from app.worker import process_one_job


def _png_bytes(width=400, height=300) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 30, 40)).save(buffer, "PNG")
    return buffer.getvalue()


def _upload_image(client, auth_headers, title="Foto de portada"):
    return client.post(
        "/api/v1/content/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data={"kind": "IMAGE", "title": title},
        files={"file": ("foto.png", _png_bytes(), "image/png")},
    )


def test_upload_image_is_processed_by_worker_and_published(client, auth_headers):
    upload = _upload_image(client, auth_headers)
    assert upload.status_code == 201
    body = upload.json()
    content_id = body["id"]
    assert body["published_version"] is None
    assert body["latest_version"]["status"] == "PENDING"

    # The worker processes one job per call; a single upload needs a single call.
    assert process_one_job() is True

    fetched = client.get(f"/api/v1/content/{content_id}", headers=auth_headers).json()
    assert fetched["published_version"]["status"] == "READY"
    assets = fetched["published_version"]["assets"]
    kinds = {asset["kind"] for asset in assets}
    assert "PAGE" in kinds
    assert "THUMBNAIL" in kinds

    page_asset = next(a for a in assets if a["kind"] == "PAGE")
    served = client.get(f"/api/v1/public/assets/{page_asset['id']}/file")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"
    assert len(served.content) > 0

    partial = client.get(f"/api/v1/public/assets/{page_asset['id']}/file", headers={"Range": "bytes=0-9"})
    assert partial.status_code == 206
    assert len(partial.content) == 10


def test_upload_rejects_wrong_extension(client, auth_headers):
    response = client.post(
        "/api/v1/content/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data={"kind": "IMAGE", "title": "Documento"},
        files={"file": ("archivo.exe", b"MZ...", "application/octet-stream")},
    )
    assert response.status_code == 422


def test_upload_rejects_empty_file(client, auth_headers):
    response = client.post(
        "/api/v1/content/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data={"kind": "IMAGE", "title": "Vacío"},
        files={"file": ("vacio.png", b"", "image/png")},
    )
    assert response.status_code == 422


def test_upload_rejects_unknown_kind(client, auth_headers):
    response = client.post(
        "/api/v1/content/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data={"kind": "ANNOUNCEMENT", "title": "No aplica"},
        files={"file": ("foto.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 422


def test_upload_requires_authentication(client):
    response = client.post(
        "/api/v1/content/upload",
        data={"kind": "IMAGE", "title": "Sin sesión"},
        files={"file": ("foto.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 401


def test_retry_requeues_failed_version(client, auth_headers):
    upload = _upload_image(client, auth_headers, title="Para reintentar")
    content_id = upload.json()["id"]
    version_id = upload.json()["latest_version"]["id"]

    # Only a FAILED version can be retried.
    premature = client.post(f"/api/v1/content/{content_id}/versions/{version_id}/retry", headers=auth_headers)
    assert premature.status_code == 422

    from app.database import SessionLocal
    from app.models import ContentVersion

    with SessionLocal() as db:
        version = db.get(ContentVersion, uuid.UUID(version_id))
        version.status = "FAILED"
        version.error_message = "simulated failure"
        db.commit()

    retried = client.post(f"/api/v1/content/{content_id}/versions/{version_id}/retry", headers=auth_headers)
    assert retried.status_code == 200
    assert retried.json()["latest_version"]["status"] == "PENDING"

    assert process_one_job() is True
    fetched = client.get(f"/api/v1/content/{content_id}", headers=auth_headers).json()
    assert fetched["published_version"]["status"] == "READY"


def test_update_page_display_seconds(client, auth_headers):
    content_id = _upload_image(client, auth_headers, title="Con duración por página").json()["id"]
    assert process_one_job() is True

    fetched = client.get(f"/api/v1/content/{content_id}", headers=auth_headers).json()
    version_id = fetched["published_version"]["id"]
    assets = fetched["published_version"]["assets"]
    page_asset = next(a for a in assets if a["kind"] == "PAGE")
    thumbnail_asset = next(a for a in assets if a["kind"] == "THUMBNAIL")
    assert page_asset["display_seconds"] is None
    asset_url = f"/api/v1/content/{content_id}/versions/{version_id}/assets"

    updated = client.patch(f"{asset_url}/{page_asset['id']}", headers=auth_headers, json={"display_seconds": 12})
    assert updated.status_code == 200
    updated_page = next(a for a in updated.json()["published_version"]["assets"] if a["id"] == page_asset["id"])
    assert updated_page["display_seconds"] == 12

    # Only pages accept a custom duration, not thumbnails, videos or other assets.
    assert client.patch(f"{asset_url}/{thumbnail_asset['id']}", headers=auth_headers, json={"display_seconds": 5}).status_code == 422
    assert client.patch(f"{asset_url}/{page_asset['id']}", headers=auth_headers, json={"display_seconds": 1}).status_code == 422

    cleared = client.patch(f"{asset_url}/{page_asset['id']}", headers=auth_headers, json={"display_seconds": None})
    assert cleared.status_code == 200
    cleared_page = next(a for a in cleared.json()["published_version"]["assets"] if a["id"] == page_asset["id"])
    assert cleared_page["display_seconds"] is None
