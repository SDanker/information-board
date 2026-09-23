from datetime import datetime, timezone
from typing import Annotated
import io
import uuid

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.audit import record as record_audit
from app.branding import load_branding
from app.database import get_db
from app.i18n import _
from app.models import ACTIVE_EMERGENCY_KEY, Content, ContentVersion, Playlist, PlaylistItem, Screen, SystemSetting, User
from app.network import client_ip, public_base_url, url_version
from app.scheduling import is_item_scheduled_now, is_published_now
from app.schemas import HeartbeatRequest, LibraryItem, ScreenCreate, ScreenLibraryResponse, ScreenResponse, ScreenUpdate
from app.schemas.branding_schemas import DisplaySettings
from app.schemas.playlist_schemas import PlaylistPlaybackItem, PlaylistPlaybackResponse
from app.security import require_admin
from app.sharing_service import get_or_create_token, thumbnail_url_for

router = APIRouter(tags=["screens"])

# Public page a screen's QR code points to (frontend route /catalog/{slug}).
CATALOG_ROUTE = "catalog"


def get_or_404(db: Session, screen_id: uuid.UUID) -> Screen:
    screen = db.get(Screen, screen_id)
    if screen is None:
        raise HTTPException(status_code=404, detail=_("Screen not found"))
    return screen


def _active_screen_or_404(db: Session, slug: str) -> Screen:
    screen = db.scalar(select(Screen).where(Screen.slug == slug, Screen.is_active.is_(True)))
    if screen is None:
        raise HTTPException(status_code=404, detail=_("Screen not found or inactive"))
    return screen


def _playback_assets(version: ContentVersion) -> list[dict]:
    return [
        {
            "id": str(asset.id),
            "kind": asset.kind,
            "page_number": asset.page_number,
            "display_seconds": asset.display_seconds,
            "duration_seconds": asset.duration_seconds,
            "url": f"/api/v1/public/assets/{asset.id}/file",
        }
        for asset in sorted(version.assets, key=lambda a: (a.page_number or 0))
    ]


@router.get("/screens", response_model=list[ScreenResponse])
def list_screens(db: Annotated[Session, Depends(get_db)], _admin: Annotated[User, Depends(require_admin)]) -> list[ScreenResponse]:
    return [ScreenResponse.from_screen(item) for item in db.scalars(select(Screen).order_by(Screen.name)).all()]


@router.post("/screens", response_model=ScreenResponse, status_code=status.HTTP_201_CREATED)
def create_screen(
    payload: ScreenCreate, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_admin)]
) -> ScreenResponse:
    screen = Screen(**payload.model_dump())
    db.add(screen)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=_("A screen with that slug already exists"))
    db.refresh(screen)
    record_audit(db, user, "create", "screen", str(screen.id), {"name": screen.name, "slug": screen.slug})
    return ScreenResponse.from_screen(screen)


@router.patch("/screens/{screen_id}", response_model=ScreenResponse)
def update_screen(
    screen_id: uuid.UUID,
    payload: ScreenUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ScreenResponse:
    screen = get_or_404(db, screen_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("playlist_id") is not None and db.get(Playlist, updates["playlist_id"]) is None:
        raise HTTPException(status_code=404, detail=_("Playlist not found"))
    for field, value in updates.items():
        setattr(screen, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=_("A screen with that slug already exists"))
    db.refresh(screen)
    record_audit(db, user, "update", "screen", str(screen.id), {key: str(value) for key, value in updates.items()})
    return ScreenResponse.from_screen(screen)


@router.delete("/screens/{screen_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_screen(
    screen_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_admin)]
) -> Response:
    screen = get_or_404(db, screen_id)
    db.delete(screen)
    db.commit()
    record_audit(db, user, "delete", "screen", str(screen_id), {"name": screen.name, "slug": screen.slug})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/public/screens/{slug}", response_model=ScreenResponse)
def public_screen(slug: str, db: Annotated[Session, Depends(get_db)]) -> ScreenResponse:
    return ScreenResponse.from_screen(_active_screen_or_404(db, slug))


@router.post("/public/screens/{slug}/heartbeat", response_model=ScreenResponse)
def heartbeat(slug: str, payload: HeartbeatRequest, request: Request, db: Annotated[Session, Depends(get_db)]) -> ScreenResponse:
    screen = _active_screen_or_404(db, slug)
    screen.last_seen_at = datetime.now(timezone.utc)
    screen.last_ip = client_ip(request)
    screen.last_user_agent = request.headers.get("user-agent", "")[:500]
    if payload.resolution:
        screen.expected_resolution = payload.resolution
    db.commit()
    db.refresh(screen)
    return ScreenResponse.from_screen(screen)


@router.get("/public/screens/{slug}/playlist", response_model=PlaylistPlaybackResponse)
def public_screen_playlist(slug: str, request: Request, db: Annotated[Session, Depends(get_db)]) -> PlaylistPlaybackResponse:
    """Ordered list, already filtered by schedule, of what the screen must rotate right now.

    The TV client caches this response and rotates locally using duration_seconds,
    so it keeps working through short network outages.
    """
    screen = _active_screen_or_404(db, slug)
    if screen.playlist_id is None:
        return PlaylistPlaybackResponse(status="empty", items=[])
    playlist = db.scalar(
        select(Playlist)
        .where(Playlist.id == screen.playlist_id)
        .options(
            selectinload(Playlist.items)
            .selectinload(PlaylistItem.content)
            .selectinload(Content.published_version)
            .selectinload(ContentVersion.assets)
        )
    )
    if playlist is None or not playlist.is_active:
        return PlaylistPlaybackResponse(status="empty", items=[])

    display = load_branding(db).display
    base_url = public_base_url(request)
    items: list[PlaylistPlaybackItem] = []
    for item in sorted(playlist.items, key=lambda entry: entry.order_index):
        content = item.content
        if content is None or content.deleted_at is not None or content.published_version is None:
            continue
        # The publication period applies to the content itself, whichever playlists include it.
        if not is_published_now(content):
            continue
        if not is_item_scheduled_now(
            is_active=item.is_active,
            start_date=item.start_date,
            end_date=item.end_date,
            days_of_week=item.days_of_week,
            start_time=item.start_time,
            end_time=item.end_time,
        ):
            continue
        version = content.published_version
        items.append(
            PlaylistPlaybackItem(
                item_id=item.id,
                content_id=content.id,
                kind=content.kind,
                title=content.title,
                duration_seconds=item.duration_seconds,
                payload=version.payload,
                assets=_playback_assets(version),
                qr=_resolve_qr_overlay(screen, content, display, base_url),
            )
        )
    return PlaylistPlaybackResponse(status="ok" if items else "empty", items=items)


@router.get("/public/active-emergency", response_model=PlaylistPlaybackResponse)
def public_active_emergency(db: Annotated[Session, Depends(get_db)]) -> PlaylistPlaybackResponse:
    """While an emergency is being broadcast every screen shows it, regardless of its playlist."""
    setting = db.get(SystemSetting, ACTIVE_EMERGENCY_KEY)
    if setting is None or not setting.value.get("content_id"):
        return PlaylistPlaybackResponse(status="empty", items=[])
    try:
        content_id = uuid.UUID(setting.value["content_id"])
    except ValueError:
        return PlaylistPlaybackResponse(status="empty", items=[])
    content = db.scalar(
        select(Content)
        .where(Content.id == content_id, Content.deleted_at.is_(None))
        .options(selectinload(Content.published_version).selectinload(ContentVersion.assets))
    )
    if content is None or content.published_version is None:
        return PlaylistPlaybackResponse(status="empty", items=[])
    version = content.published_version
    item = PlaylistPlaybackItem(
        item_id=content.id,
        content_id=content.id,
        kind=content.kind,
        title=content.title,
        duration_seconds=0,
        payload=version.payload,
        assets=_playback_assets(version),
        qr=None,
    )
    return PlaylistPlaybackResponse(status="ok", items=[item])


def _resolve_qr_overlay(screen: Screen, content: Content, display: DisplaySettings, base_url: str) -> dict | None:
    """QR badge for one playback item.

    The QR image always points to the screen's catalog (every shareable item of its
    playlist), never to the item currently on air: the code therefore stays identical
    while the playlist rotates, and a half-finished scan cannot switch to another code.
    Position and message come from branding unless the content overrides them.
    base_url is the address this TV used, so the code follows the server to a new network.
    """
    if not display.show_qr or content.library_visibility == "PRIVATE":
        return None
    # A calendar has nothing to download, so the code would only cover the grid.
    if content.kind == "CALENDAR":
        return None
    screen_config = screen.qr_config or {}
    content_config = content.qr_overlay or {}
    if screen_config.get("visible") is False or content_config.get("visible") is False:
        return None
    catalog_url = f"{base_url}/{CATALOG_ROUTE}/{screen.slug}"
    return {
        "position": content_config.get("position") or display.qr_position,
        "message": content_config.get("message") or display.qr_message or None,
        # The fingerprint changes with the encoded address, so the TV never shows a cached old code.
        "image_url": f"/api/v1/public/screens/{screen.slug}/library/qr.png?v={url_version(catalog_url)}",
        "share_url": catalog_url,
    }


@router.get("/public/screens/{slug}/library", response_model=ScreenLibraryResponse)
def public_screen_library(slug: str, request: Request, db: Annotated[Session, Depends(get_db)]) -> ScreenLibraryResponse:
    """Every shareable (non-private) item rotating on this screen, for the page its QR opens.

    Unlike /public/library (the general library), QR_ONLY content is listed here:
    this is exactly the channel that visibility level exists for.
    """
    screen = _active_screen_or_404(db, slug)
    if screen.playlist_id is None:
        return ScreenLibraryResponse(screen_name=screen.name, items=[])
    playlist = db.scalar(
        select(Playlist)
        .where(Playlist.id == screen.playlist_id)
        .options(
            selectinload(Playlist.items)
            .selectinload(PlaylistItem.content)
            .selectinload(Content.published_version)
            .selectinload(ContentVersion.assets)
        )
    )
    if playlist is None or not playlist.is_active:
        return ScreenLibraryResponse(screen_name=screen.name, items=[])

    base = public_base_url(request)
    seen: set[uuid.UUID] = set()
    items: list[LibraryItem] = []
    for item in sorted(playlist.items, key=lambda entry: entry.order_index):
        content = item.content
        if content is None or content.id in seen or content.deleted_at is not None or content.is_archived:
            continue
        if content.library_visibility == "PRIVATE" or content.published_version is None or not is_published_now(content):
            continue
        # Calendars are read live from their source: there is no file to offer here.
        if content.kind == "CALENDAR":
            continue
        seen.add(content.id)
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
    return ScreenLibraryResponse(screen_name=screen.name, items=items)


@router.get("/public/screens/{slug}/library/qr.png")
def public_screen_library_qr(slug: str, request: Request, db: Annotated[Session, Depends(get_db)]) -> Response:
    screen = _active_screen_or_404(db, slug)
    url = f"{public_base_url(request)}/{CATALOG_ROUTE}/{screen.slug}"
    image = qrcode.make(url, border=1)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
