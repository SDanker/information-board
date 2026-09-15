"""Audit trail of administrative actions.

Never raises: failing to write an audit entry must not break the real operation
being audited.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import AuditLog, User

logger = logging.getLogger("audit")


def record(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    try:
        db.add(
            AuditLog(
                user_id=user.id if user else None,
                username=user.username if user else "anonymous",
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=detail or {},
                ip=ip,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Could not write audit entry: %s %s %s", action, entity_type, entity_id, exc_info=True)
