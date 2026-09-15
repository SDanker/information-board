import tempfile
from pathlib import Path
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.audit import record as record_audit
from app.config import get_settings
from app.content_paths import derived_prefix, safe_filename, source_prefix
from app.database import get_db
from app.geocoding import geocode_address
from app.i18n import _
from app.models import ACTIVE_EMERGENCY_KEY, Asset, Content, ContentVersion, ProcessingJob, SystemSetting, User, utc_now
from app.processing import optimize_image
from app.realtime import publish_event
from app.schemas import ContentResponse, ContentVersionResponse, EmergencyCreate, EmergencyLocationUpdate
from app.security import require_editor, require_operator
from app.storage import get_storage
from app.uploads import UPLOAD_RULES, max_size_bytes

router = APIRouter(tags=["emergencies"])

_VIDEO_RULE = UPLOAD_RULES["VIDEO"]
_IMAGE_RULE = UPLOAD_RULES["IMAGE"]


def _load(db: Session, content_id: uuid.UUID) -> Content:
    content = db.scalar(
        select(Content)
        .where(Content.id == content_id, Content.kind == "EMERGENCY", Content.deleted_at.is_(None))
        .options(selectinload(Content.versions).selectinload(ContentVersion.assets), selectinload(Content.published_version))
    )
    if content is None:
        raise HTTPException(status_code=404, detail=_("Emergency not found"))
    return content


def _published_version_or_404(content: Content) -> ContentVersion:
    if content.published_version is None:
        raise HTTPException(status_code=404, detail=_("The emergency has no published version"))
    return content.published_version


def _response(content: Content) -> ContentResponse:
    payload = ContentResponse.model_validate(content)
    if content.versions:
        payload.latest_version = ContentVersionResponse.model_validate(max(content.versions, key=lambda v: v.version_number))
    return payload


@router.post("/emergencies", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
def create_emergency(
    payload: EmergencyCreate, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_editor)]
) -> ContentResponse:
    latitude, longitude, provider = payload.latitude, payload.longitude, None
    if latitude is None or longitude is None:
        result = geocode_address(payload.address) if payload.address else None
        if result is not None:
            latitude, longitude, provider = result.latitude, result.longitude, result.provider
    else:
        provider = "manual"

    content = Content(kind="EMERGENCY", title=payload.title, library_visibility="LOCAL_PUBLIC", created_by=user.id)
    db.add(content)
    db.flush()
    version = ContentVersion(
        content_id=content.id,
        version_number=1,
        status="READY",
        published_at=utc_now(),
        payload={
            "address": payload.address,
            "description": payload.description,
            "sections": [section.model_dump() for section in payload.sections],
            "latitude": latitude,
            "longitude": longitude,
            "geocode_provider": provider,
        },
    )
    db.add(version)
    db.flush()
    content.published_version_id = version.id
    db.commit()
    db.refresh(content)
    record_audit(db, user, "create", "emergency", str(content.id), {"title": content.title, "address": payload.address})
    publish_event({"target": "admin", "type": "content_changed"})
    return _response(_load(db, content.id))


@router.patch("/emergencies/{content_id}/location", response_model=ContentResponse)
def update_location(
    content_id: uuid.UUID,
    payload: EmergencyLocationUpdate,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> ContentResponse:
    """Manual correction when automatic geocoding failed or is inaccurate."""
    content = _load(db, content_id)
    version = content.published_version or max(content.versions, key=lambda v: v.version_number, default=None)
    if version is None:
        raise HTTPException(status_code=404, detail=_("The emergency has no published version"))
    version.payload = {**version.payload, "latitude": payload.latitude, "longitude": payload.longitude, "geocode_provider": "manual"}
    db.commit()
    publish_event({"target": "all_screens", "type": "content_updated", "content_id": str(content.id)})
    publish_event({"target": "admin", "type": "content_changed"})
    return _response(_load(db, content.id))


@router.post("/emergencies/{content_id}/media", response_model=ContentResponse)
def upload_emergency_media(
    content_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
    photos: Annotated[list[UploadFile], File(default_factory=list)],
    video: Annotated[UploadFile | None, File()] = None,
) -> ContentResponse:
    """Photos are optimized synchronously; a video is queued for the worker to transcode."""
    content = _load(db, content_id)
    version = _published_version_or_404(content)
    storage = get_storage()
    settings = get_settings()

    next_page = 1 + max((a.page_number or 0 for a in version.assets if a.kind == "PHOTO"), default=0)
    for photo in photos:
        if not photo.filename:
            continue
        extension = Path(photo.filename).suffix.lower()
        if extension not in _IMAGE_RULE.extensions:
            raise HTTPException(status_code=422, detail=_("Photo extension not allowed: {extension}", extension=extension))
        data = photo.file.read()
        if not data:
            continue
        if len(data) > max_size_bytes(settings, _IMAGE_RULE):
            raise HTTPException(status_code=413, detail=_("Photo is too large: {name}", name=photo.filename))
        with tempfile.TemporaryDirectory(prefix="board-emergency-") as tmp:
            tmp_path = Path(tmp)
            local_source = tmp_path / "source" / safe_filename(photo.filename)
            local_source.parent.mkdir(parents=True, exist_ok=True)
            local_source.write_bytes(data)
            try:
                derived = optimize_image(local_source, tmp_path / "derived")
            except (UnidentifiedImageError, OSError):
                raise HTTPException(status_code=422, detail=_("The file is not a valid image"))
            prefix = derived_prefix(content.id, version.id)
            for item in derived:
                relative_path = f"{prefix}/{item.path.name}"
                size = storage.save_local_file(relative_path, item.path)
                kind = "PHOTO" if item.kind == "PAGE" else item.kind
                db.add(
                    Asset(
                        content_version_id=version.id,
                        kind=kind,
                        page_number=next_page if kind == "PHOTO" else None,
                        storage_path=relative_path,
                        mime_type=item.mime_type,
                        width=item.width,
                        height=item.height,
                        size_bytes=size,
                    )
                )
        next_page += 1

    if video is not None and video.filename:
        extension = Path(video.filename).suffix.lower()
        if extension not in _VIDEO_RULE.extensions:
            raise HTTPException(status_code=422, detail=_("Video extension not allowed: {extension}", extension=extension))
        relative_path = f"{source_prefix(content.id, version.id)}/{safe_filename(video.filename)}"
        size = storage.save_stream(relative_path, video.file)
        if size == 0:
            storage.delete(relative_path)
        elif size > max_size_bytes(settings, _VIDEO_RULE):
            storage.delete(relative_path)
            raise HTTPException(status_code=413, detail=_("The video exceeds the configured size limit"))
        else:
            db.add(
                Asset(
                    content_version_id=version.id,
                    kind="SOURCE",
                    storage_path=relative_path,
                    mime_type=video.content_type or "video/mp4",
                    size_bytes=size,
                )
            )
            db.add(ProcessingJob(content_version_id=version.id, job_type="TRANSCODE_VIDEO", status="QUEUED"))

    db.commit()
    publish_event({"target": "all_screens", "type": "content_updated", "content_id": str(content.id)})
    publish_event({"target": "admin", "type": "content_changed"})
    return _response(_load(db, content.id))


@router.delete("/emergencies/{content_id}/media/{asset_id}", response_model=ContentResponse)
def delete_emergency_media(
    content_id: uuid.UUID,
    asset_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> ContentResponse:
    content = _load(db, content_id)
    asset = db.scalar(select(Asset).where(Asset.id == asset_id))
    if asset is None or asset.content_version_id not in {v.id for v in content.versions}:
        raise HTTPException(status_code=404, detail=_("File not found"))
    get_storage().delete(asset.storage_path)
    db.delete(asset)
    db.commit()
    publish_event({"target": "all_screens", "type": "content_updated", "content_id": str(content.id)})
    return _response(_load(db, content.id))


@router.post("/emergencies/{content_id}/broadcast", response_model=ContentResponse)
def broadcast_emergency(
    content_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_editor)]
) -> ContentResponse:
    """Interrupt every screen with this emergency, regardless of the playlist assigned to it."""
    content = _load(db, content_id)
    setting = db.get(SystemSetting, ACTIVE_EMERGENCY_KEY)
    value = {"content_id": str(content.id)}
    if setting is None:
        db.add(SystemSetting(key=ACTIVE_EMERGENCY_KEY, value=value))
    else:
        setting.value = value
    db.commit()
    record_audit(db, user, "broadcast", "emergency", str(content.id), {"title": content.title})
    publish_event({"target": "all_screens", "type": "emergency_broadcast", "content_id": str(content.id)})
    publish_event({"target": "admin", "type": "content_changed"})
    return _response(_load(db, content.id))


@router.post("/emergencies/clear-broadcast", status_code=status.HTTP_204_NO_CONTENT)
def clear_broadcast(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_editor)]) -> None:
    setting = db.get(SystemSetting, ACTIVE_EMERGENCY_KEY)
    if setting is not None:
        db.delete(setting)
        db.commit()
    record_audit(db, user, "clear_broadcast", "emergency")
    publish_event({"target": "all_screens", "type": "emergency_cleared"})
    publish_event({"target": "admin", "type": "content_changed"})


@router.get("/emergencies/active-status")
def active_status(db: Annotated[Session, Depends(get_db)], _operator: Annotated[User, Depends(require_operator)]) -> dict:
    setting = db.get(SystemSetting, ACTIVE_EMERGENCY_KEY)
    return {"active": setting is not None, "content_id": setting.value.get("content_id") if setting else None}
