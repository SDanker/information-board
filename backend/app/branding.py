"""Runtime branding and display preferences.

Defaults come from environment settings (see :mod:`app.config`). Administrators can
override them from Settings > Branding; overrides are stored as JSON in the
``system_settings`` table under :data:`BRANDING_KEY`, so adding an option never needs
a database migration. Invalid stored values fall back to the defaults instead of
breaking public pages such as the login screen or the TV view.
"""

from __future__ import annotations

import io
import logging
import uuid

from PIL import Image, ImageOps
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SystemSetting
from app.schemas.branding_schemas import BrandingResponse, BrandingSettings

logger = logging.getLogger("branding")

BRANDING_KEY = "branding"
LOGO_STORAGE_PATH = "branding/logo.png"
LOGO_MAX_DIMENSION = 512
LOGO_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})


def default_branding() -> BrandingSettings:
    """Branding built from environment settings, skipping any value that is invalid."""
    settings = get_settings()
    candidates = {
        "app_name": settings.app_name,
        "organization_name": settings.organization_name,
        "primary_color": settings.brand_primary_color,
        "default_language": settings.default_language,
        "date_locale": settings.resolved_date_locale,
        "timezone": settings.timezone,
    }
    valid: dict[str, object] = {}
    for key, value in candidates.items():
        try:
            BrandingSettings.model_validate({**valid, key: value})
        except ValidationError:
            logger.warning("Ignoring invalid %s from the environment: %r", key.upper(), value)
            continue
        valid[key] = value
    return BrandingSettings.model_validate(valid)


def _stored_value(db: Session) -> dict:
    setting = db.get(SystemSetting, BRANDING_KEY)
    return dict(setting.value or {}) if setting is not None else {}


def _write_value(db: Session, value: dict) -> None:
    setting = db.get(SystemSetting, BRANDING_KEY)
    if setting is None:
        db.add(SystemSetting(key=BRANDING_KEY, value=value))
    else:
        setting.value = value
    db.commit()


def load_branding(db: Session) -> BrandingSettings:
    defaults = default_branding().model_dump()
    overrides = _stored_value(db).get("settings") or {}
    merged = {**defaults, **{key: value for key, value in overrides.items() if key in defaults and key != "display"}}
    merged["display"] = {**defaults["display"], **(overrides.get("display") or {})}
    try:
        return BrandingSettings.model_validate(merged)
    except ValidationError:
        logger.warning("Stored branding is invalid; using the defaults", exc_info=True)
        return default_branding()


def save_branding(db: Session, branding: BrandingSettings) -> None:
    value = _stored_value(db)
    value["settings"] = branding.model_dump()
    _write_value(db, value)


def reset_branding(db: Session) -> None:
    """Forget every override so the environment defaults apply again (the logo is kept)."""
    value = _stored_value(db)
    value.pop("settings", None)
    _write_value(db, value)


def logo_version(db: Session) -> str | None:
    return _stored_value(db).get("logo_version")


def set_logo_version(db: Session, version: str | None) -> None:
    value = _stored_value(db)
    if version:
        value["logo_version"] = version
    else:
        value.pop("logo_version", None)
    _write_value(db, value)


def new_logo_version() -> str:
    return uuid.uuid4().hex[:12]


def branding_response(db: Session) -> BrandingResponse:
    branding = load_branding(db)
    version = logo_version(db)
    # The version query string changes on every upload, so browsers never show a stale logo.
    logo_url = f"/api/v1/public/branding/logo?v={version}" if version else None
    return BrandingResponse(**branding.model_dump(), logo_url=logo_url)


def prepare_logo(data: bytes) -> bytes:
    """Normalize an uploaded logo to a PNG no larger than LOGO_MAX_DIMENSION, keeping transparency."""
    with Image.open(io.BytesIO(data)) as raw:
        raw.seek(0)  # first frame of animated images
        image = ImageOps.exif_transpose(raw).convert("RGBA")
    image.thumbnail((LOGO_MAX_DIMENSION, LOGO_MAX_DIMENSION), Image.LANCZOS)
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()
