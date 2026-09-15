from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.audit import record as record_audit
from app.database import get_db
from app.i18n import _
from app.models import Content, ContentVersion, Playlist, PlaylistItem, Screen, User
from app.realtime import publish_event
from app.scheduling import is_item_scheduled_now
from app.schemas import (
    PlaylistCreate,
    PlaylistItemCreate,
    PlaylistItemResponse,
    PlaylistItemUpdate,
    PlaylistReorder,
    PlaylistResponse,
    PlaylistUpdate,
)
from app.schemas.content_schemas import ContentResponse
from app.security import require_editor, require_operator

router = APIRouter(tags=["playlists"])


def _load(db: Session, playlist_id: uuid.UUID) -> Playlist:
    playlist = db.scalar(
        select(Playlist)
        .where(Playlist.id == playlist_id)
        .options(
            selectinload(Playlist.items)
            .selectinload(PlaylistItem.content)
            .selectinload(Content.versions)
            .selectinload(ContentVersion.assets),
            selectinload(Playlist.items).selectinload(PlaylistItem.content).selectinload(Content.published_version),
        )
    )
    if playlist is None:
        raise HTTPException(status_code=404, detail=_("Playlist not found"))
    return playlist


def _active_content_or_404(db: Session, content_id: uuid.UUID) -> Content:
    content = db.scalar(select(Content).where(Content.id == content_id, Content.deleted_at.is_(None)))
    if content is None:
        raise HTTPException(status_code=404, detail=_("Content not found"))
    return content


def _item_or_404(db: Session, playlist_id: uuid.UUID, item_id: uuid.UUID) -> PlaylistItem:
    item = db.scalar(select(PlaylistItem).where(PlaylistItem.id == item_id, PlaylistItem.playlist_id == playlist_id))
    if item is None:
        raise HTTPException(status_code=404, detail=_("Item not found"))
    return item


def _response(db: Session, playlist: Playlist) -> PlaylistResponse:
    payload = PlaylistResponse.model_validate(playlist)
    payload.screen_count = db.scalar(select(func.count()).select_from(Screen).where(Screen.playlist_id == playlist.id)) or 0
    items: list[PlaylistItemResponse] = []
    for item in sorted(playlist.items, key=lambda entry: entry.order_index):
        item_payload = PlaylistItemResponse.model_validate(item)
        item_payload.content = ContentResponse.model_validate(item.content) if item.content else None
        item_payload.scheduled_now = is_item_scheduled_now(
            is_active=item.is_active,
            start_date=item.start_date,
            end_date=item.end_date,
            days_of_week=item.days_of_week,
            start_time=item.start_time,
            end_time=item.end_time,
        )
        items.append(item_payload)
    payload.items = items
    return payload


def _notify(playlist_id: uuid.UUID) -> None:
    publish_event({"target": "all_screens", "type": "playlist_updated", "playlist_id": str(playlist_id)})
    publish_event({"target": "admin", "type": "playlists_changed"})


@router.get("/playlists", response_model=list[PlaylistResponse])
def list_playlists(
    db: Annotated[Session, Depends(get_db)], _operator: Annotated[User, Depends(require_operator)]
) -> list[PlaylistResponse]:
    playlists = db.scalars(select(Playlist).order_by(Playlist.name)).unique().all()
    return [_response(db, _load(db, playlist.id)) for playlist in playlists]


@router.post("/playlists", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
def create_playlist(
    payload: PlaylistCreate, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_editor)]
) -> PlaylistResponse:
    playlist = Playlist(**payload.model_dump())
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    record_audit(db, user, "create", "playlist", str(playlist.id), {"name": playlist.name})
    return _response(db, _load(db, playlist.id))


@router.get("/playlists/{playlist_id}", response_model=PlaylistResponse)
def get_playlist(
    playlist_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], _operator: Annotated[User, Depends(require_operator)]
) -> PlaylistResponse:
    return _response(db, _load(db, playlist_id))


@router.patch("/playlists/{playlist_id}", response_model=PlaylistResponse)
def update_playlist(
    playlist_id: uuid.UUID,
    payload: PlaylistUpdate,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> PlaylistResponse:
    playlist = _load(db, playlist_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(playlist, field, value)
    db.commit()
    _notify(playlist_id)
    return _response(db, _load(db, playlist_id))


@router.delete("/playlists/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(
    playlist_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_editor)]
) -> None:
    playlist = _load(db, playlist_id)
    name = playlist.name
    db.delete(playlist)
    db.commit()
    record_audit(db, user, "delete", "playlist", str(playlist_id), {"name": name})
    _notify(playlist_id)


@router.post("/playlists/{playlist_id}/items", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
def add_item(
    playlist_id: uuid.UUID,
    payload: PlaylistItemCreate,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> PlaylistResponse:
    playlist = _load(db, playlist_id)
    _active_content_or_404(db, payload.content_id)
    data = payload.model_dump()
    if not data.get("order_index"):
        data["order_index"] = max((item.order_index for item in playlist.items), default=-1) + 1
    db.add(PlaylistItem(playlist_id=playlist_id, **data))
    db.commit()
    _notify(playlist_id)
    return _response(db, _load(db, playlist_id))


@router.patch("/playlists/{playlist_id}/items/{item_id}", response_model=PlaylistResponse)
def update_item(
    playlist_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: PlaylistItemUpdate,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> PlaylistResponse:
    item = _item_or_404(db, playlist_id, item_id)
    updates = payload.model_dump(exclude_unset=True)
    if "content_id" in updates:
        _active_content_or_404(db, updates["content_id"])
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    _notify(playlist_id)
    return _response(db, _load(db, playlist_id))


@router.delete("/playlists/{playlist_id}/items/{item_id}", response_model=PlaylistResponse)
def remove_item(
    playlist_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> PlaylistResponse:
    db.delete(_item_or_404(db, playlist_id, item_id))
    db.commit()
    _notify(playlist_id)
    return _response(db, _load(db, playlist_id))


@router.post("/playlists/{playlist_id}/reorder", response_model=PlaylistResponse)
def reorder_items(
    playlist_id: uuid.UUID,
    payload: PlaylistReorder,
    db: Annotated[Session, Depends(get_db)],
    _editor: Annotated[User, Depends(require_editor)],
) -> PlaylistResponse:
    playlist = _load(db, playlist_id)
    if set(payload.item_ids) != {item.id for item in playlist.items}:
        raise HTTPException(status_code=422, detail=_("The list must include exactly the current playlist items"))
    order_by_id = {item_id: index for index, item_id in enumerate(payload.item_ids)}
    for item in playlist.items:
        item.order_index = order_by_id[item.id]
    db.commit()
    _notify(playlist_id)
    return _response(db, _load(db, playlist_id))
