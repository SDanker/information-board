"""Share token helpers used by the sharing router and by the public screen endpoints."""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Content, ContentVersion, ShareToken
from app.network import url_version


def get_or_create_token(db: Session, content: Content) -> ShareToken:
    token = db.scalar(select(ShareToken).where(ShareToken.content_id == content.id, ShareToken.revoked.is_(False)))
    if token is not None:
        return token
    token = ShareToken(content_id=content.id, token=secrets.token_urlsafe(24))
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def share_url_for(token: ShareToken, base_url: str) -> str:
    """Absolute share link; base_url comes from app.network.public_base_url for the current request."""
    return f"{base_url}/share/{token.token}"


def qr_url_for(token: ShareToken, share_url: str) -> str:
    # The fingerprint changes with the encoded address, so a cached image is never reused after a move.
    return f"/api/v1/public/share/{token.token}/qr.png?v={url_version(share_url)}"


def thumbnail_url_for(version: ContentVersion | None) -> str | None:
    if version is None:
        return None
    asset = next((a for a in version.assets if a.kind == "THUMBNAIL"), None) or next(
        (a for a in version.assets if a.kind == "PAGE"), None
    )
    return f"/api/v1/public/assets/{asset.id}/file" if asset else None
