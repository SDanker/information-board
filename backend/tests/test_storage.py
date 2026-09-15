import io

import pytest
from PIL import Image

from app.config import get_settings
from app.storage import LocalStorage, StorageError, content_disposition, set_storage


def test_local_storage_roundtrip(tmp_path):
    storage = LocalStorage(root=tmp_path / "data")

    assert storage.save_stream("contents/a/source/file.txt", io.BytesIO(b"hello world")) == 11
    assert storage.exists("contents/a/source/file.txt")
    assert storage.read_bytes("contents/a/source/file.txt") == b"hello world"
    assert storage.size("contents/a/source/file.txt") == 11
    assert b"".join(storage.iter_range("contents/a/source/file.txt", 6, 10)) == b"world"
    assert storage.local_path("contents/a/source/file.txt").is_file()
    assert storage.presigned_url("contents/a/source/file.txt") is None

    copy = tmp_path / "copy" / "file.txt"
    storage.download_to("contents/a/source/file.txt", copy)
    assert copy.read_bytes() == b"hello world"

    storage.save_bytes("contents/a/derived/page.webp", b"12345")
    assert storage.usage_bytes() == 16

    storage.delete("contents/a")
    assert not storage.exists("contents/a/source/file.txt")
    assert storage.usage_bytes() == 0
    assert storage.describe()["backend"] == "local"


def test_storage_rejects_unsafe_paths(tmp_path):
    storage = LocalStorage(root=tmp_path / "data")
    for path in ("../escape.txt", "contents/../../escape.txt", "contents/with space/file.txt", ""):
        with pytest.raises(StorageError):
            storage.save_bytes(path, b"x")


def test_content_disposition_keeps_unicode_names():
    value = content_disposition("Informe año.pdf")
    assert 'filename="Informe ao.pdf"' in value
    assert "filename*=UTF-8''Informe%20a%C3%B1o.pdf" in value


@pytest.fixture()
def s3_storage(monkeypatch):
    moto = pytest.importorskip("moto")
    import boto3
    from botocore.config import Config

    from app.storage import S3Storage

    monkeypatch.setattr(get_settings(), "s3_bucket", "board-test")
    monkeypatch.setattr(get_settings(), "s3_prefix", "tenant-a")
    with moto.mock_aws():
        # Same signature version as the production client built by S3Storage.
        client = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
            config=Config(signature_version="s3v4"),
        )
        client.create_bucket(Bucket="board-test")
        yield S3Storage(client=client)


def test_s3_storage_roundtrip(s3_storage, tmp_path):
    path = "contents/a/source/file.txt"
    assert s3_storage.save_stream(path, io.BytesIO(b"hello world")) == 11
    assert s3_storage.exists(path)
    assert not s3_storage.exists("contents/a/source/missing.txt")
    # Objects live under the configured prefix, so several installations can share a bucket.
    assert s3_storage.client.head_object(Bucket="board-test", Key=f"tenant-a/{path}")["ContentLength"] == 11
    assert s3_storage.read_bytes(path) == b"hello world"
    assert s3_storage.size(path) == 11
    assert b"".join(s3_storage.iter_range(path, 6, 10)) == b"world"
    assert s3_storage.local_path(path) is None

    copy = tmp_path / "copy.txt"
    s3_storage.download_to(path, copy)
    assert copy.read_bytes() == b"hello world"

    local_file = tmp_path / "derived.webp"
    local_file.write_bytes(b"12345")
    assert s3_storage.save_local_file("contents/a/derived/page.webp", local_file) == 5
    assert s3_storage.usage_bytes() == 16

    url = s3_storage.presigned_url(path, media_type="text/plain", filename="file.txt")
    assert "X-Amz-Signature" in url

    s3_storage.delete("contents/a")
    assert not s3_storage.exists(path)
    assert s3_storage.usage_bytes() == 0
    assert s3_storage.describe() == {"backend": "s3", "location": "s3://board-test/tenant-a", "endpoint": "AWS"}


def test_s3_storage_rejects_unsafe_paths(s3_storage):
    with pytest.raises(StorageError):
        s3_storage.save_bytes("../escape.txt", b"x")


def test_uploads_and_downloads_work_end_to_end_on_s3(client, auth_headers, s3_storage, monkeypatch):
    from app.worker import process_one_job

    buffer = io.BytesIO()
    Image.new("RGB", (640, 480), color=(0, 90, 200)).save(buffer, "PNG")
    set_storage(s3_storage)
    try:
        upload = client.post(
            "/api/v1/content/upload",
            headers=auth_headers,
            data={"kind": "IMAGE", "title": "Cloud image"},
            files={"file": ("cloud.png", buffer.getvalue(), "image/png")},
        )
        assert upload.status_code == 201
        assert process_one_job() is True

        content = client.get(f"/api/v1/content/{upload.json()['id']}", headers=auth_headers).json()
        page = next(a for a in content["published_version"]["assets"] if a["kind"] == "PAGE")
        url = f"/api/v1/public/assets/{page['id']}/file"

        full = client.get(url)
        assert full.status_code == 200
        assert full.headers["content-type"] == "image/webp"
        assert full.headers["accept-ranges"] == "bytes"
        assert len(full.content) == page["size_bytes"]

        partial = client.get(url, headers={"Range": "bytes=0-9"})
        assert partial.status_code == 206
        assert partial.content == full.content[:10]
        assert partial.headers["content-range"] == f"bytes 0-9/{page['size_bytes']}"

        assert client.get(url, headers={"Range": f"bytes={page['size_bytes'] + 10}-"}).status_code == 416

        monkeypatch.setattr(get_settings(), "s3_serve_mode", "redirect")
        redirected = client.get(url, follow_redirects=False)
        assert redirected.status_code == 307
        assert "X-Amz-Signature" in redirected.headers["location"]
    finally:
        set_storage(None)
