"""Serve stored files over HTTP regardless of the storage backend.

Local files use Starlette's ``FileResponse``, which supports Range requests (Safari
and most smart-TV browsers require them to play ``<video>``). S3 files are either
streamed through the backend with the same Range semantics (``S3_SERVE_MODE=proxy``,
works on isolated networks) or redirected to a presigned URL
(``S3_SERVE_MODE=redirect``, saves server bandwidth).
"""

from __future__ import annotations

import re

from fastapi import Request
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse

from app.config import get_settings
from app.storage import content_disposition, get_storage

_RANGE_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")


class RangeNotSatisfiable(ValueError):
    pass


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Parse a single ``bytes=start-end`` range; ``None`` means "send the whole file"."""
    if not header:
        return None
    match = _RANGE_PATTERN.match(header.strip())
    if match is None:
        # Multiple or malformed ranges: answering with the full body is always valid.
        return None
    first, last = match.groups()
    if not first and not last:
        return None
    if not first:
        suffix_length = int(last)
        if suffix_length == 0:
            raise RangeNotSatisfiable
        start, end = max(0, size - suffix_length), size - 1
    else:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise RangeNotSatisfiable
    return start, end


def storage_file_response(
    request: Request,
    relative_path: str,
    media_type: str,
    *,
    filename: str | None = None,
    cache_control: str | None = None,
) -> Response:
    storage = get_storage()
    headers: dict[str, str] = {}
    if cache_control:
        headers["Cache-Control"] = cache_control

    local = storage.local_path(relative_path)
    if local is not None:
        return FileResponse(local, media_type=media_type, filename=filename, headers=headers)

    if get_settings().s3_serve_mode == "redirect":
        url = storage.presigned_url(relative_path, media_type=media_type, filename=filename)
        if url:
            # No cache headers: the presigned URL expires, the redirect must not outlive it.
            return RedirectResponse(url, status_code=307)

    size = storage.size(relative_path)
    headers["Accept-Ranges"] = "bytes"
    if filename:
        headers["Content-Disposition"] = content_disposition(filename)
    if size == 0:
        return Response(content=b"", media_type=media_type, headers=headers)
    try:
        byte_range = parse_range(request.headers.get("range"), size)
    except RangeNotSatisfiable:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    start, end = byte_range or (0, size - 1)
    headers["Content-Length"] = str(end - start + 1)
    status_code = 200
    if byte_range is not None:
        status_code = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(
        storage.iter_range(relative_path, start, end), status_code=status_code, media_type=media_type, headers=headers
    )
