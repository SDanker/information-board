from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.audit import record as record_audit
from app.branding import (
    LOGO_EXTENSIONS,
    LOGO_STORAGE_PATH,
    branding_response,
    logo_version,
    new_logo_version,
    prepare_logo,
    reset_branding,
    save_branding,
    set_logo_version,
)
from app.config import get_settings
from app.database import get_db
from app.file_responses import storage_file_response
from app.i18n import _
from app.models import User
from app.realtime import publish_event
from app.schemas.branding_schemas import BrandingResponse, BrandingSettings
from app.security import require_admin
from app.storage import get_storage

router = APIRouter(tags=["branding"])


def _notify() -> None:
    # Screens and open admin panels reload branding without a manual refresh.
    publish_event({"target": "all_screens", "type": "branding_updated"})
    publish_event({"target": "admin", "type": "branding_updated"})


@router.get("/public/branding", response_model=BrandingResponse)
def public_branding(db: Annotated[Session, Depends(get_db)]) -> BrandingResponse:
    """Public on purpose: the login page, TV screens and library render it before any sign-in."""
    return branding_response(db)


@router.put("/branding", response_model=BrandingResponse)
def update_branding(
    payload: BrandingSettings, db: Annotated[Session, Depends(get_db)], admin: Annotated[User, Depends(require_admin)]
) -> BrandingResponse:
    save_branding(db, payload)
    record_audit(db, admin, "update", "branding")
    _notify()
    return branding_response(db)


@router.delete("/branding", response_model=BrandingResponse)
def reset_branding_to_defaults(
    db: Annotated[Session, Depends(get_db)], admin: Annotated[User, Depends(require_admin)]
) -> BrandingResponse:
    reset_branding(db)
    record_audit(db, admin, "reset", "branding")
    _notify()
    return branding_response(db)


@router.post("/branding/logo", response_model=BrandingResponse)
def upload_logo(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    file: Annotated[UploadFile, File()],
) -> BrandingResponse:
    if Path(file.filename or "").suffix.lower() not in LOGO_EXTENSIONS:
        raise HTTPException(status_code=422, detail=_("Logo format not allowed. Use PNG, JPG, WEBP or GIF."))
    limit_mb = get_settings().max_logo_size_mb
    data = file.file.read(limit_mb * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(status_code=422, detail=_("The file is empty"))
    if len(data) > limit_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=_("The logo exceeds the {limit} MB limit", limit=limit_mb))
    try:
        png = prepare_logo(data)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        raise HTTPException(status_code=422, detail=_("The file is not a valid image"))
    get_storage().save_bytes(LOGO_STORAGE_PATH, png)
    set_logo_version(db, new_logo_version())
    record_audit(db, admin, "upload", "branding", detail={"item": "logo", "size_bytes": len(png)})
    _notify()
    return branding_response(db)


@router.delete("/branding/logo", response_model=BrandingResponse)
def delete_logo(db: Annotated[Session, Depends(get_db)], admin: Annotated[User, Depends(require_admin)]) -> BrandingResponse:
    get_storage().delete(LOGO_STORAGE_PATH)
    set_logo_version(db, None)
    record_audit(db, admin, "delete", "branding", detail={"item": "logo"})
    _notify()
    return branding_response(db)


@router.get("/public/branding/logo")
def public_logo(request: Request, db: Annotated[Session, Depends(get_db)]) -> Response:
    storage = get_storage()
    if logo_version(db) is None or not storage.exists(LOGO_STORAGE_PATH):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("No logo has been uploaded"))
    return storage_file_response(request, LOGO_STORAGE_PATH, "image/png", cache_control="public, max-age=300")
