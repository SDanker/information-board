from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.audit import record as record_audit
from app.config import get_settings
from app.content_paths import safe_filename, source_prefix
from app.database import get_db
from app.file_responses import storage_file_response
from app.i18n import _
from app.models import LIBRARY_VISIBILITIES, Asset, Content, ContentVersion, ProcessingJob, User, utc_now
from app.realtime import publish_event
from app.schemas import AssetUpdate, ContentCreate, ContentResponse, ContentUpdate, ContentVersionResponse
from app.security import require_editor, require_operator
from app.storage import StorageError, get_storage
from app.uploads import UPLOAD_RULES, max_size_bytes

router = APIRouter(tags=["content"])


def _get_or_404(db: Session, content_id: uuid.UUID) -> Content:
    content = db.scalar(
        select(Content)
        .where(Content.id == content_id, Content.deleted_at.is_(None))
        .options(selectinload(Content.versions).selectinload(ContentVersion.assets), selectinload(Content.published_version))
    )
    if content is None:
        raise HTTPException(status_code=404, detail=_("Content not found"))
    return content


def _response(content: Content) -> ContentResponse:
    payload = ContentResponse.model_validate(content)
    if content.versions:
        latest = max(content.versions, key=lambda v: v.version_number)
        payload.latest_version = ContentVersionResponse.model_validate(latest)
    return payload


def _notify_content_changed(content_id: uuid.UUID | None = None, screen_event: str | None = None) -> None:
    if screen_event and content_id:
        publish_event({"target": "all_screens", "type": screen_event, "content_id": str(content_id)})
    publish_event({"target": "admin", "type": "content_changed"})


@router.get("/content", response_model=list[ContentResponse])
def list_content(
    db: Annotated[Session, Depends(get_db)],
    _operator: Annotated[User, Depends(require_operator)],
    kind: str | None = None,
) -> list[ContentResponse]:
    query = (
        select(Content)
        .where(Content.deleted_at.is_(None))
        .options(selectinload(Content.versions).selectinload(ContentVersion.assets), selectinload(Content.published_version))
        .order_by(Content.updated_at.desc())
    )
    if kind:
        query = query.where(Content.kind == kind)
    return [_response(item) for item in db.scalars(query).unique().all()]


@router.post("/content", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentCreate, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_editor)]
) -> ContentResponse:
    if payload.kind != "ANNOUNCEMENT":
        raise HTTPException(status_code=422, detail=_("Content of type {kind} cannot be created from this endpoint", kind=payload.kind))
    if payload.announcement is None:
        raise HTTPException(status_code=422, detail=_("Announcements require the 'announcement' field"))
    content = Content(
        kind=payload.kind,
        title=payload.title,
        library_visibility=payload.library_visibility,
        qr_overlay=payload.qr_overlay,
        created_by=user.id,
    )
    db.add(content)
    db.flush()
    version = ContentVersion(
        content_id=content.id, version_number=1, status="READY", payload=payload.announcement.model_dump(), published_at=utc_now()
    )
    db.add(version)
    db.flush()
    content.published_version_id = version.id
    db.commit()
    db.refresh(content)
    record_audit(db, user, "create", "content", str(content.id), {"kind": content.kind, "title": content.title})
    _notify_content_changed(content.id, "content_published")
    return _response(_get_or_404(db, content.id))


@router.post("/content/upload", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
def upload_content(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_editor)],
    kind: Annotated[str, Form()],
    title: Annotated[str, Form(min_length=2, max_length=200)],
    file: Annotated[UploadFile, File()],
    library_visibility: Annotated[str, Form()] = "LOCAL_PUBLIC",
) -> ContentResponse:
    rule = UPLOAD_RULES.get(kind)
    if rule is None:
        raise HTTPException(status_code=422, detail=_("Invalid content type for upload: {kind}", kind=kind))
    if library_visibility not in LIBRARY_VISIBILITIES:
        raise HTTPException(status_code=422, detail=_("Invalid visibility: {visibility}", visibility=library_visibility))
    original_name = file.filename or "file"
    if Path(original_name).suffix.lower() not in rule.extensions:
        raise HTTPException(
            status_code=422,
            detail=_("Extension not allowed for {kind}. Allowed formats: {formats}", kind=kind, formats=", ".join(sorted(rule.extensions))),
        )

    limit = max_size_bytes(get_settings(), rule)
    storage = get_storage()

    content = Content(kind=kind, title=title, library_visibility=library_visibility, created_by=user.id)
    db.add(content)
    db.flush()
    version = ContentVersion(content_id=content.id, version_number=1, status="PENDING", payload={})
    db.add(version)
    db.flush()

    relative_path = f"{source_prefix(content.id, version.id)}/{safe_filename(original_name)}"
    try:
        # nginx (client_max_body_size) already caps the whole request. This per-type check
        # is a second barrier applied after writing, because Starlette does not expose the
        # size before the stream is read.
        size = storage.save_stream(relative_path, file.file)
    except StorageError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    if size == 0:
        storage.delete(relative_path)
        db.rollback()
        raise HTTPException(status_code=422, detail=_("The file is empty"))
    if size > limit:
        storage.delete(f"contents/{content.id}")
        db.rollback()
        raise HTTPException(
            status_code=413, detail=_("The file exceeds the {limit} MB limit for {kind}", limit=limit // (1024 * 1024), kind=kind)
        )

    mime_type = file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    db.add(Asset(content_version_id=version.id, kind="SOURCE", storage_path=relative_path, mime_type=mime_type, size_bytes=size))
    db.add(ProcessingJob(content_version_id=version.id, job_type=rule.job_type, status="QUEUED"))
    db.commit()
    record_audit(db, user, "upload", "content", str(content.id), {"kind": content.kind, "title": content.title, "size_bytes": size})
    _notify_content_changed()
    return _response(_get_or_404(db, content.id))


@router.get("/content/{content_id}", response_model=ContentResponse)
def get_content(
    content_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], _operator: Annotated[User, Depends(require_operator)]
) -> ContentResponse:
    return _response(_get_or_404(db, content_id))


@router.patch("/content/{content_id}", response_model=ContentResponse)
def update_content(
    content_id: uuid.UUID,
    payload: ContentUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_editor)],
) -> ContentResponse:
    content = _get_or_404(db, content_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(content, field, value)
    db.commit()
    db.refresh(content)
    record_audit(db, user, "update", "content", str(content.id), {key: str(value) for key, value in updates.items()})
    _notify_content_changed(content.id, "content_updated")
    return _response(_get_or_404(db, content.id))


@router.post("/content/{content_id}/versions", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
def create_version(
    content_id: uuid.UUID,
    payload: ContentCreate,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> ContentResponse:
    """Publish a new version of an existing announcement (text or background edit)."""
    content = _get_or_404(db, content_id)
    if content.kind != "ANNOUNCEMENT":
        raise HTTPException(status_code=422, detail=_("Only announcements accept new versions through this endpoint"))
    if payload.announcement is None:
        raise HTTPException(status_code=422, detail=_("Announcements require the 'announcement' field"))
    next_number = max((v.version_number for v in content.versions), default=0) + 1
    version = ContentVersion(
        content_id=content.id, version_number=next_number, status="READY", payload=payload.announcement.model_dump(), published_at=utc_now()
    )
    db.add(version)
    db.flush()
    content.published_version_id = version.id
    db.commit()
    db.refresh(content)
    _notify_content_changed(content.id, "content_published")
    return _response(_get_or_404(db, content.id))


@router.post("/content/{content_id}/versions/{version_id}/retry", response_model=ContentResponse)
def retry_version(
    content_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> ContentResponse:
    content = _get_or_404(db, content_id)
    version = next((item for item in content.versions if item.id == version_id), None)
    if version is None:
        raise HTTPException(status_code=404, detail=_("Version not found"))
    if version.status != "FAILED":
        raise HTTPException(status_code=422, detail=_("Only failed versions can be retried"))
    job = db.scalar(
        select(ProcessingJob).where(ProcessingJob.content_version_id == version.id).order_by(ProcessingJob.created_at.desc())
    )
    if job is None:
        raise HTTPException(status_code=404, detail=_("There is no processing job for this version"))
    job.status = "QUEUED"
    job.error_message = None
    job.started_at = None
    job.finished_at = None
    version.status = "PENDING"
    version.error_message = None
    db.commit()
    _notify_content_changed()
    return _response(_get_or_404(db, content.id))


@router.patch("/content/{content_id}/versions/{version_id}/assets/{asset_id}", response_model=ContentResponse)
def update_asset(
    content_id: uuid.UUID,
    version_id: uuid.UUID,
    asset_id: uuid.UUID,
    payload: AssetUpdate,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> ContentResponse:
    """Set how many seconds a single page or slide stays on screen while rotating."""
    content = _get_or_404(db, content_id)
    version = next((item for item in content.versions if item.id == version_id), None)
    if version is None:
        raise HTTPException(status_code=404, detail=_("Version not found"))
    asset = next((item for item in version.assets if item.id == asset_id), None)
    if asset is None:
        raise HTTPException(status_code=404, detail=_("File not found"))
    if asset.kind != "PAGE":
        raise HTTPException(status_code=422, detail=_("Only pages of a document or presentation accept a custom duration"))
    asset.display_seconds = payload.display_seconds
    db.commit()
    publish_event({"target": "all_screens", "type": "content_updated", "content_id": str(content.id)})
    return _response(_get_or_404(db, content.id))


@router.get("/public/assets/{asset_id}/file")
def serve_asset(asset_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)]) -> Response:
    """Serve a derived file (page, thumbnail, converted video) for TV playback or admin previews.

    Public on purpose: screens download these files without a session, like every other
    /public/* endpoint. Asset ids are random UUIDs, so they cannot be enumerated.
    """
    asset = db.get(Asset, asset_id)
    if asset is None or not get_storage().exists(asset.storage_path):
        raise HTTPException(status_code=404, detail=_("File not found"))
    return storage_file_response(request, asset.storage_path, asset.mime_type, cache_control="public, max-age=3600")


@router.delete("/content/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content(
    content_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_editor)]
) -> None:
    content = _get_or_404(db, content_id)
    content.deleted_at = datetime.now(timezone.utc)
    content.is_archived = True
    db.commit()
    record_audit(db, user, "delete", "content", str(content.id), {"title": content.title})
    _notify_content_changed(content.id, "content_deleted")
