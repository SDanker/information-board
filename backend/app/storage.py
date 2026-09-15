"""Persistent file storage.

Two backends implement the same :class:`Storage` protocol:

* :class:`LocalStorage` writes under ``STORAGE_ROOT`` (``/data`` in the containers).
  That directory can be a Docker volume, a host folder, or a NAS share mounted on the
  host or through a Docker SMB/NFS volume (see ``docs/storage.md``).
* :class:`S3Storage` writes to any S3-compatible object storage reachable over the
  network or the Internet (AWS S3, Cloudflare R2, Backblaze B2, Wasabi, MinIO...).

The rest of the application only uses :func:`get_storage`, never a concrete backend.
"""

from __future__ import annotations

import re
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Protocol
from urllib.parse import quote

from app.config import get_settings
from app.i18n import _

_SAFE_SEGMENT = re.compile(r"^[a-zA-Z0-9._-]+$")
CHUNK_SIZE = 1024 * 1024


class StorageError(Exception):
    pass


class Storage(Protocol):
    def save_stream(self, relative_path: str, stream: BinaryIO) -> int:
        """Store the stream contents and return the size in bytes."""

    def save_bytes(self, relative_path: str, data: bytes) -> int: ...

    def save_local_file(self, relative_path: str, local_path: Path) -> int:
        """Store a file that already exists on local disk (e.g. ffmpeg output) without loading it in memory."""

    def read_bytes(self, relative_path: str) -> bytes: ...

    def download_to(self, relative_path: str, local_path: Path) -> None:
        """Copy a stored file to local disk so external tools (ffmpeg, LibreOffice) can read it."""

    def iter_range(self, relative_path: str, start: int, end: int) -> Iterator[bytes]:
        """Yield bytes ``start`` to ``end`` (both inclusive) of a stored file."""

    def size(self, relative_path: str) -> int: ...

    def local_path(self, relative_path: str) -> Path | None:
        """Absolute local path when the backend is a filesystem, otherwise ``None``."""

    def presigned_url(self, relative_path: str, *, media_type: str | None = None, filename: str | None = None) -> str | None:
        """Temporary direct download URL when the backend supports it, otherwise ``None``."""

    def delete(self, relative_path: str) -> None:
        """Delete a file, or every file under a folder-like prefix."""

    def exists(self, relative_path: str) -> bool: ...

    def usage_bytes(self) -> int: ...

    def describe(self) -> dict[str, str]:
        """Non-secret summary shown on the Settings page."""


def content_disposition(filename: str) -> str:
    """``attachment`` header value that preserves non-ASCII file names (RFC 6266 / RFC 5987)."""
    fallback = filename.encode("ascii", "ignore").decode().replace('"', "").strip() or "download"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


def _validate_relative_path(relative_path: str) -> Path:
    parts = Path(relative_path).parts
    if not parts or any(part in ("..", "") or not _SAFE_SEGMENT.match(part) for part in parts):
        raise StorageError(_("Invalid storage path: {path}", path=relative_path))
    return Path(*parts)


class LocalStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(get_settings().storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        safe = _validate_relative_path(relative_path)
        resolved = (self.root / safe).resolve()
        if self.root.resolve() not in resolved.parents and resolved != self.root.resolve():
            raise StorageError(_("The path is outside the storage directory"))
        return resolved

    def _atomic_destination(self, relative_path: str) -> tuple[Path, Path]:
        destination = self._resolve(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination, destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")

    def save_stream(self, relative_path: str, stream: BinaryIO) -> int:
        destination, tmp = self._atomic_destination(relative_path)
        size = 0
        with open(tmp, "wb") as out:
            while chunk := stream.read(CHUNK_SIZE):
                out.write(chunk)
                size += len(chunk)
        tmp.replace(destination)
        return size

    def save_bytes(self, relative_path: str, data: bytes) -> int:
        destination, tmp = self._atomic_destination(relative_path)
        tmp.write_bytes(data)
        tmp.replace(destination)
        return len(data)

    def save_local_file(self, relative_path: str, local_path: Path) -> int:
        destination = self._resolve(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, destination)
        return destination.stat().st_size

    def read_bytes(self, relative_path: str) -> bytes:
        return self._resolve(relative_path).read_bytes()

    def download_to(self, relative_path: str, local_path: Path) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._resolve(relative_path), local_path)

    def iter_range(self, relative_path: str, start: int, end: int) -> Iterator[bytes]:
        path = self._resolve(relative_path)
        remaining = end - start + 1
        with open(path, "rb") as handle:
            handle.seek(start)
            while remaining > 0:
                chunk = handle.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    def size(self, relative_path: str) -> int:
        return self._resolve(relative_path).stat().st_size

    def local_path(self, relative_path: str) -> Path | None:
        return self._resolve(relative_path)

    def presigned_url(self, relative_path: str, *, media_type: str | None = None, filename: str | None = None) -> str | None:
        return None

    def delete(self, relative_path: str) -> None:
        path = self._resolve(relative_path)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()

    def exists(self, relative_path: str) -> bool:
        return self._resolve(relative_path).exists()

    def usage_bytes(self) -> int:
        return sum(item.stat().st_size for item in self.root.rglob("*") if item.is_file())

    def describe(self) -> dict[str, str]:
        return {"backend": "local", "location": str(self.root)}


class _CountingReader:
    """Wraps an upload stream so its size is known without buffering the whole file."""

    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self._stream.read(size)
        self.bytes_read += len(chunk)
        return chunk

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False


class S3Storage:
    def __init__(self, client=None) -> None:
        settings = get_settings()
        if not settings.s3_bucket:
            raise StorageError(_("S3_BUCKET is required when STORAGE_BACKEND=s3"))
        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix.strip("/")
        self.endpoint = settings.s3_endpoint_url
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                region_name=settings.s3_region or None,
                endpoint_url=settings.s3_endpoint_url or None,
                aws_access_key_id=settings.s3_access_key_id or None,
                aws_secret_access_key=settings.s3_secret_access_key or None,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"},
                ),
            )
        self.client = client

    def _key(self, relative_path: str) -> str:
        key = "/".join(_validate_relative_path(relative_path).parts)
        return f"{self.prefix}/{key}" if self.prefix else key

    def save_stream(self, relative_path: str, stream: BinaryIO) -> int:
        reader = _CountingReader(stream)
        self.client.upload_fileobj(reader, self.bucket, self._key(relative_path))
        return reader.bytes_read

    def save_bytes(self, relative_path: str, data: bytes) -> int:
        self.client.put_object(Bucket=self.bucket, Key=self._key(relative_path), Body=data)
        return len(data)

    def save_local_file(self, relative_path: str, local_path: Path) -> int:
        self.client.upload_file(str(local_path), self.bucket, self._key(relative_path))
        return local_path.stat().st_size

    def read_bytes(self, relative_path: str) -> bytes:
        body = self.client.get_object(Bucket=self.bucket, Key=self._key(relative_path))["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def download_to(self, relative_path: str, local_path: Path) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, self._key(relative_path), str(local_path))

    def iter_range(self, relative_path: str, start: int, end: int) -> Iterator[bytes]:
        response = self.client.get_object(Bucket=self.bucket, Key=self._key(relative_path), Range=f"bytes={start}-{end}")
        body = response["Body"]
        try:
            yield from body.iter_chunks(chunk_size=CHUNK_SIZE)
        finally:
            body.close()

    def size(self, relative_path: str) -> int:
        return int(self.client.head_object(Bucket=self.bucket, Key=self._key(relative_path))["ContentLength"])

    def local_path(self, relative_path: str) -> Path | None:
        return None

    def presigned_url(self, relative_path: str, *, media_type: str | None = None, filename: str | None = None) -> str | None:
        params = {"Bucket": self.bucket, "Key": self._key(relative_path)}
        if media_type:
            params["ResponseContentType"] = media_type
        if filename:
            params["ResponseContentDisposition"] = content_disposition(filename)
        return self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=get_settings().s3_presign_seconds)

    def delete(self, relative_path: str) -> None:
        key = self._key(relative_path)
        self.client.delete_object(Bucket=self.bucket, Key=key)
        batch: list[dict[str, str]] = []
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=f"{key}/"):
            for item in page.get("Contents", []):
                batch.append({"Key": item["Key"]})
                if len(batch) == 1000:
                    self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch, "Quiet": True})
                    batch = []
        if batch:
            self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch, "Quiet": True})

    def exists(self, relative_path: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(relative_path))
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def usage_bytes(self) -> int:
        total = 0
        prefix = f"{self.prefix}/" if self.prefix else ""
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            total += sum(int(item["Size"]) for item in page.get("Contents", []))
        return total

    def describe(self) -> dict[str, str]:
        location = f"s3://{self.bucket}/{self.prefix}" if self.prefix else f"s3://{self.bucket}"
        return {"backend": "s3", "location": location, "endpoint": self.endpoint or "AWS"}


_storage: Storage | None = None


def create_storage() -> Storage:
    if get_settings().storage_backend == "s3":
        return S3Storage()
    return LocalStorage()


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = create_storage()
    return _storage


def set_storage(storage: Storage | None) -> None:
    """Replace the process-wide storage instance (used by tests)."""
    global _storage
    _storage = storage
