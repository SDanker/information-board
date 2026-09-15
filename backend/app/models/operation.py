from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from .screens_users import utc_now


class SystemSetting(Base):
    """Key/value store for global state such as the active emergency broadcast and the
    branding overrides edited from the admin panel."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


ACTIVE_EMERGENCY_KEY = "active_emergency"
