"""Storage path conventions for content files.

contents/<content_id>/<version_id>/source/<original file>
contents/<content_id>/<version_id>/derived/<pages, thumbnail, converted video>
"""

import re
import uuid

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(original: str) -> str:
    name = _UNSAFE.sub("_", original.strip()) or "file"
    return name[-150:]  # avoid extremely long names while keeping the extension


def source_prefix(content_id: uuid.UUID, version_id: uuid.UUID) -> str:
    return f"contents/{content_id}/{version_id}/source"


def derived_prefix(content_id: uuid.UUID, version_id: uuid.UUID) -> str:
    return f"contents/{content_id}/{version_id}/derived"
