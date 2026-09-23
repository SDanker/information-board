"""Branding and display preferences editable from Settings > Branding."""

import re
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.calendar_feed import normalize_feed_url
from app.i18n import _

# Navigation pages whose visible name can be customized.
PAGE_KEYS = ("dashboard", "screens", "content", "playlists", "library", "schedule", "users", "audit", "settings")
DEFAULT_PRIMARY_COLOR = "#2563eb"
MAX_PAGE_LABEL_LENGTH = 40
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class DisplaySettings(BaseModel):
    """How the TV screens render and rotate content."""

    model_config = ConfigDict(extra="ignore")

    default_item_seconds: int = Field(default=15, ge=3, le=3600)
    min_page_seconds: int = Field(default=4, ge=2, le=120)
    emergency_pane_seconds: int = Field(default=7, ge=3, le=120)
    spreadsheet_rows_per_page: int = Field(default=14, ge=5, le=40)
    show_clock: bool = True
    clock_24h: bool = True
    show_qr: bool = True
    qr_position: Literal["bottom-right", "bottom-left", "top-right", "top-left"] = "bottom-right"
    qr_message: str = Field(default="", max_length=80)
    show_emergency_map: bool = True
    # Length of the default publication period of new content, in days; 0 = no end date.
    default_publication_days: int = Field(default=7, ge=0, le=3650)


class BrandingSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app_name: str = Field(default="Information Board", min_length=1, max_length=60)
    organization_name: str = Field(default="", max_length=120)
    primary_color: str = DEFAULT_PRIMARY_COLOR
    default_language: Literal["en", "es"] = "en"
    date_locale: str = Field(default="en-US", max_length=35, pattern=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    timezone: str = Field(default="UTC", max_length=64)
    page_labels: dict[str, str] = Field(default_factory=dict)
    login_headline: str = Field(default="", max_length=120)
    login_message: str = Field(default="", max_length=300)
    board_footer_text: str = Field(default="", max_length=120)
    public_library_enabled: bool = True
    # Suggested calendar for new Calendar publications; empty = type it every time.
    default_calendar_ics_url: str = Field(default="", max_length=1000)
    display: DisplaySettings = Field(default_factory=DisplaySettings)

    @field_validator("app_name")
    @classmethod
    def valid_app_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(_("The application name cannot be empty"))
        return value

    @field_validator("organization_name", "login_headline", "login_message", "board_footer_text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("primary_color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        if not _HEX_COLOR.fullmatch(value):
            raise ValueError(_("Enter a color in #RRGGBB format"))
        return value.lower()

    @field_validator("default_calendar_ics_url")
    @classmethod
    def valid_calendar_url(cls, value: str) -> str:
        value = value.strip()
        return normalize_feed_url(value) if value else ""

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception:
            raise ValueError(_("Unknown time zone: {timezone}", timezone=value))
        return value

    @field_validator("page_labels")
    @classmethod
    def valid_page_labels(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned: dict[str, str] = {}
        for key, label in value.items():
            if key not in PAGE_KEYS:
                raise ValueError(_("Unknown page: {page}", page=key))
            label = str(label).strip()
            if len(label) > MAX_PAGE_LABEL_LENGTH:
                raise ValueError(_("Page names can have at most {limit} characters", limit=MAX_PAGE_LABEL_LENGTH))
            if label:
                cleaned[key] = label
        return cleaned


class BrandingResponse(BrandingSettings):
    logo_url: str | None = None
