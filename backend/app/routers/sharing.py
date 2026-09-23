import io
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Annotated
import uuid
import zipfile

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.branding import load_branding
from app.content_paths import safe_filename
from app.database import get_db
from app.file_responses import storage_file_response
from app.i18n import _
from app.models import Content, ContentVersion, ShareToken, User, utc_now
from app.network import public_base_url
from app.scheduling import is_published_now, publication_status
from app.schemas import LibraryItem, PublicShareDetail, ShareDownloadItem, ShareInfo
from app.security import require_editor
from app.sharing_service import get_or_create_token, qr_url_for, share_url_for, thumbnail_url_for
from app.storage import content_disposition, get_storage

router = APIRouter(tags=["sharing"])


def _share_info(token: ShareToken, base_url: str) -> ShareInfo:
    share_url = share_url_for(token, base_url)
    return ShareInfo(
        token=token.token,
        share_url=share_url,
        qr_url=qr_url_for(token, share_url),
        download_url=f"/api/v1/public/share/{token.token}/download",
        revoked=token.revoked,
        download_count=token.download_count,
        created_at=token.created_at,
    )


def _emergency_items(version: ContentVersion | None) -> list[ShareDownloadItem]:
    """Photos and video of an emergency, listed separately so each can be downloaded on its own."""
    if version is None:
        return []
    items: list[ShareDownloadItem] = []
    photos = sorted((a for a in version.assets if a.kind == "PHOTO"), key=lambda a: (a.page_number or 0))
    for number, photo in enumerate(photos, start=1):
        items.append(
            ShareDownloadItem(id=photo.id, kind="PHOTO", label=_("Photo {number}", number=number), url=f"/api/v1/public/assets/{photo.id}/file")
        )
    video = next((a for a in version.assets if a.kind == "VIDEO"), None)
    if video is not None:
        items.append(ShareDownloadItem(id=video.id, kind="VIDEO", label=_("Video"), url=f"/api/v1/public/assets/{video.id}/file"))
    return items


def _zip_response(files: list[tuple[str, str]], title: str) -> StreamingResponse:
    """Bundle stored files (archive name, storage path) into a ZIP download."""
    storage = get_storage()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for archive_name, storage_path in files:
            if storage.exists(storage_path):
                archive.writestr(archive_name, storage.read_bytes(storage_path))
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/zip", headers={"Content-Disposition": content_disposition(f"{safe_filename(title)}.zip")}
    )


def _load_content(db: Session, content_id: uuid.UUID) -> Content:
    content = db.scalar(
        select(Content)
        .where(Content.id == content_id, Content.deleted_at.is_(None))
        .options(selectinload(Content.published_version).selectinload(ContentVersion.assets))
    )
    if content is None:
        raise HTTPException(status_code=404, detail=_("Content not found"))
    if content.library_visibility == "PRIVATE":
        raise HTTPException(status_code=422, detail=_("This content is private; change its visibility to share it"))
    return content


def _resolve_valid_token(db: Session, token_value: str) -> ShareToken:
    token = db.scalar(
        select(ShareToken)
        .where(ShareToken.token == token_value, ShareToken.revoked.is_(False))
        .options(selectinload(ShareToken.content).selectinload(Content.published_version).selectinload(ContentVersion.assets))
    )
    not_found = HTTPException(status_code=404, detail=_("Invalid or expired link"))
    if token is None or (token.expires_at and token.expires_at < utc_now()):
        raise not_found
    content = token.content
    if content is None or content.deleted_at is not None or content.library_visibility == "PRIVATE":
        raise not_found
    # A link opens once the publication has started and keeps working after it ends: archived
    # publications stay downloadable from the library, so older links and QR codes still deliver the file.
    if publication_status(start_at=content.publish_start_at, end_at=content.publish_end_at, days=content.publish_days) == "scheduled":
        raise not_found
    return token


@router.get("/content/{content_id}/share", response_model=ShareInfo)
def get_share_info(
    content_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> ShareInfo:
    return _share_info(get_or_create_token(db, _load_content(db, content_id)), public_base_url(request))


@router.post("/content/{content_id}/share/rotate", response_model=ShareInfo)
def rotate_share(
    content_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> ShareInfo:
    """Invalidate the current link/QR code and create a new one (e.g. if the old one leaked)."""
    content = _load_content(db, content_id)
    existing = db.scalar(select(ShareToken).where(ShareToken.content_id == content.id, ShareToken.revoked.is_(False)))
    if existing is not None:
        existing.revoked = True
        db.commit()
    return _share_info(get_or_create_token(db, content), public_base_url(request))


@router.get("/public/share/{token_value}", response_model=PublicShareDetail)
def public_share_detail(token_value: str, db: Annotated[Session, Depends(get_db)]) -> PublicShareDetail:
    token = _resolve_valid_token(db, token_value)
    content = token.content
    version = content.published_version
    download_url = f"/api/v1/public/share/{token.token}/download"
    if content.kind == "EMERGENCY":
        items = _emergency_items(version)
        return PublicShareDetail(
            title=content.title,
            kind=content.kind,
            thumbnail_url=thumbnail_url_for(version),
            downloadable=bool(items),
            download_url=download_url if items else None,
            items=items,
        )
    has_download = bool(version and any(a.kind in ("SOURCE", "PAGE") for a in version.assets))
    return PublicShareDetail(
        title=content.title,
        kind=content.kind,
        thumbnail_url=thumbnail_url_for(version),
        downloadable=has_download,
        download_url=download_url if has_download else None,
        items=[],
    )


@router.get("/public/share/{token_value}/qr.png")
def public_share_qr(token_value: str, request: Request, db: Annotated[Session, Depends(get_db)]) -> Response:
    token = _resolve_valid_token(db, token_value)
    image = qrcode.make(share_url_for(token, public_base_url(request)), border=1)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/public/share/{token_value}/download")
def public_share_download(token_value: str, request: Request, db: Annotated[Session, Depends(get_db)]) -> Response:
    token = _resolve_valid_token(db, token_value)
    content = token.content
    version = content.published_version
    if version is None:
        raise HTTPException(status_code=404, detail=_("Nothing to download yet"))

    if content.kind == "EMERGENCY":
        # An emergency's SOURCE is the untranscoded upload (any format, not meant for
        # distribution); the package is the optimized photos plus the converted VIDEO.
        photos = sorted((a for a in version.assets if a.kind == "PHOTO"), key=lambda a: (a.page_number or 0))
        video = next((a for a in version.assets if a.kind == "VIDEO"), None)
        if not photos and video is None:
            raise HTTPException(status_code=404, detail=_("Nothing to download yet"))
        token.download_count += 1
        db.commit()
        files = [(f"photo-{number}{Path(photo.storage_path).suffix}", photo.storage_path) for number, photo in enumerate(photos, start=1)]
        if video is not None:
            files.append((f"video{Path(video.storage_path).suffix}", video.storage_path))
        return _zip_response(files, content.title)

    storage = get_storage()
    source = next((a for a in version.assets if a.kind == "SOURCE"), None)
    if source is not None and storage.exists(source.storage_path):
        token.download_count += 1
        db.commit()
        filename = safe_filename(content.title) + Path(source.storage_path).suffix
        return storage_file_response(request, source.storage_path, source.mime_type, filename=filename)

    pages = sorted((a for a in version.assets if a.kind == "PAGE"), key=lambda a: (a.page_number or 0))
    if not pages:
        raise HTTPException(status_code=404, detail=_("Nothing to download yet"))
    token.download_count += 1
    db.commit()
    return _zip_response([(f"page-{page.page_number or 0}.webp", page.storage_path) for page in pages], content.title)


@router.get("/public/library", response_model=list[LibraryItem])
def public_library(request: Request, db: Annotated[Session, Depends(get_db)]) -> list[LibraryItem]:
    if not load_branding(db).public_library_enabled:
        raise HTTPException(status_code=404, detail=_("The public library is disabled"))
    contents = db.scalars(
        select(Content)
        .where(Content.library_visibility == "LOCAL_PUBLIC", Content.deleted_at.is_(None), Content.is_archived.is_(False))
        # Calendars are read live from their source, so they have nothing to download.
        .where(Content.kind != "CALENDAR")
        .where(Content.published_version_id.is_not(None))
        .options(selectinload(Content.published_version).selectinload(ContentVersion.assets))
        .order_by(Content.updated_at.desc())
    ).all()
    base = public_base_url(request)
    items: list[LibraryItem] = []
    for content in contents:
        if not is_published_now(content):
            continue
        token = get_or_create_token(db, content)
        items.append(
            LibraryItem(
                id=content.id,
                kind=content.kind,
                title=content.title,
                thumbnail_url=thumbnail_url_for(content.published_version),
                share_url=f"{base}/share/{token.token}",
            )
        )
    return items


def _require_public_library(db: Session) -> None:
    if not load_branding(db).public_library_enabled:
        raise HTTPException(status_code=404, detail=_("The public library is disabled"))


def _archived_contents(db: Session) -> list[Content]:
    """Archived and expired publications that are public on the local network, most recent first.

    Expired ones are included even before the worker archives them, so the list never lags.
    Calendars are left out: they are read live from their source and have nothing to download.
    """
    contents = db.scalars(
        select(Content)
        .where(Content.library_visibility == "LOCAL_PUBLIC", Content.deleted_at.is_(None), Content.kind != "CALENDAR")
        .where(Content.published_version_id.is_not(None))
        .options(selectinload(Content.published_version).selectinload(ContentVersion.assets))
    ).all()
    finished = [
        content
        for content in contents
        if content.is_archived
        or publication_status(start_at=content.publish_start_at, end_at=content.publish_end_at, days=None) == "expired"
    ]
    return sorted(finished, key=lambda content: content.publish_end_at or datetime.min, reverse=True)


@router.get("/public/library/archived", response_model=list[LibraryItem])
def public_library_archived(request: Request, db: Annotated[Session, Depends(get_db)]) -> list[LibraryItem]:
    """The "Archived" segment of the download pages: publications whose period has ended."""
    _require_public_library(db)
    base = public_base_url(request)
    items: list[LibraryItem] = []
    for content in _archived_contents(db):
        token = get_or_create_token(db, content)
        items.append(
            LibraryItem(
                id=content.id,
                kind=content.kind,
                title=content.title,
                thumbnail_url=thumbnail_url_for(content.published_version),
                share_url=f"{base}/share/{token.token}",
                period_end=content.publish_end_at,
            )
        )
    return items


def _content_files(content: Content) -> list[tuple[str, str]]:
    """Files worth downloading from a publication, as (archive name, storage path)."""
    version = content.published_version
    if version is None:
        return []
    if content.kind == "EMERGENCY":
        photos = sorted((a for a in version.assets if a.kind == "PHOTO"), key=lambda a: (a.page_number or 0))
        files = [(f"photo-{number}{Path(photo.storage_path).suffix}", photo.storage_path) for number, photo in enumerate(photos, start=1)]
        video = next((a for a in version.assets if a.kind == "VIDEO"), None)
        if video is not None:
            files.append((f"video{Path(video.storage_path).suffix}", video.storage_path))
        return files
    source = next((a for a in version.assets if a.kind == "SOURCE"), None)
    if source is not None and get_storage().exists(source.storage_path):
        return [(safe_filename(content.title) + Path(source.storage_path).suffix, source.storage_path)]
    pages = sorted((a for a in version.assets if a.kind == "PAGE"), key=lambda a: (a.page_number or 0))
    return [(f"page-{page.page_number or 0}.webp", page.storage_path) for page in pages]


class _ZipSink(io.RawIOBase):
    """Write-only, non-seekable target for zipfile: collects what was written so it can be sent at once."""

    def __init__(self) -> None:
        self._chunks: list[bytes] = []
        self._position = 0

    def writable(self) -> bool:
        return True

    def write(self, data) -> int:
        self._chunks.append(bytes(data))
        self._position += len(data)
        return len(data)

    def tell(self) -> int:
        return self._position

    def drain(self) -> bytes:
        chunks, self._chunks = self._chunks, []
        return b"".join(chunks)


def _stream_zip(entries: list[tuple[str, str]]) -> Iterator[bytes]:
    """Zip the files while they are sent, so a large archive never sits in memory (one chunk at a time)."""
    storage = get_storage()
    sink = _ZipSink()
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for archive_name, storage_path in entries:
            if not storage.exists(storage_path):
                continue
            with archive.open(archive_name, "w", force_zip64=True) as target:
                for chunk in storage.iter_range(storage_path, 0, storage.size(storage_path) - 1):
                    target.write(chunk)
                    data = sink.drain()
                    if data:
                        yield data
            data = sink.drain()
            if data:
                yield data
    tail = sink.drain()  # the central directory, written when the archive closes
    if tail:
        yield tail


@router.get("/public/library/archived/download")
def public_library_archived_download(db: Annotated[Session, Depends(get_db)]) -> StreamingResponse:
    """Every archived publication in one zip, each in its own folder."""
    _require_public_library(db)
    entries: list[tuple[str, str]] = []
    folders: set[str] = set()
    for content in _archived_contents(db):
        folder = safe_filename(content.title)
        if folder in folders:
            folder = f"{folder}-{str(content.id)[:8]}"
        folders.add(folder)
        entries += [(f"{folder}/{name}", path) for name, path in _content_files(content)]
    if not entries:
        raise HTTPException(status_code=404, detail=_("Nothing to download yet"))
    return StreamingResponse(
        _stream_zip(entries), media_type="application/zip", headers={"Content-Disposition": content_disposition("archived-publications.zip")}
    )
