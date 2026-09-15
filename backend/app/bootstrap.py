"""First-run data: the initial administrator and the first screens.

Both are created only while the database is still empty, so later changes to
``INITIAL_ADMIN_*`` or ``INITIAL_SCREENS`` never recreate accounts or screens that an
administrator deliberately removed. To recover access use the CLI instead::

    docker compose exec backend python -m app.cli reset-password --username admin
"""

import logging

from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Screen, User
from app.schemas.auth_screens import SLUG_PATTERN
from app.security import hash_password

logger = logging.getLogger("bootstrap")

DEFAULT_SCREENS = {
    "en": [("Main screen", "main", "Main information board")],
    "es": [("Pantalla principal", "principal", "Cartelera principal")],
}


def parse_initial_screens(raw: str) -> list[tuple[str, str, str]]:
    """Parse ``INITIAL_SCREENS`` ("slug:Name,slug2:Name 2") into (name, slug, description) tuples."""
    screens: list[tuple[str, str, str]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        slug, separator, name = chunk.partition(":")
        slug = slug.strip().lower()
        if not SLUG_PATTERN.fullmatch(slug):
            logger.warning("Ignoring invalid INITIAL_SCREENS entry: %r", chunk)
            continue
        screens.append(((name.strip() if separator else "") or slug, slug, ""))
    return screens


def ensure_initial_data() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        if not db.scalar(select(func.count()).select_from(User)):
            db.add(
                User(
                    username=settings.initial_admin_username,
                    password_hash=hash_password(settings.initial_admin_password),
                    role="ADMIN",
                )
            )
        if not db.scalar(select(func.count()).select_from(Screen)):
            seeds = parse_initial_screens(settings.initial_screens) or DEFAULT_SCREENS[settings.default_language]
            for name, slug, description in seeds:
                db.add(Screen(name=name[:120], slug=slug, description=description))
        db.commit()
