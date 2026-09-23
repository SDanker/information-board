"""Application settings loaded from environment variables (and an optional ``.env`` file).

Every setting can be overridden with an environment variable of the same name in
upper case, e.g. ``DEFAULT_LANGUAGE=es``. Branding values here are only the initial
defaults: administrators can change them later from Settings > Branding.
See ``.env.example`` for a documented list.
"""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_MARKER = "CHANGE_ME"
DEVELOPMENT_SECRET_KEY = "development-only-change-me-32-characters"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Identity and branding defaults.
    app_name: str = "Information Board"
    organization_name: str = ""
    brand_primary_color: str = "#2563eb"
    default_language: Literal["en", "es"] = "en"
    # BCP 47 locale used to format dates and times; empty = derived from the language.
    date_locale: str = ""
    timezone: str = Field(default="UTC", validation_alias=AliasChoices("TIMEZONE", "TZ"))

    # Runtime.
    app_env: str = "development"
    database_url: str = "sqlite:///./information_board.db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = DEVELOPMENT_SECRET_KEY
    # Address used in QR codes and share links. Empty or "auto" = built from the address each
    # visitor used to reach the server, so a new IP or network needs no change (app/network.py).
    public_base_url: str = ""
    # Extra comma-separated origins allowed to call the API from a browser.
    cors_extra_origins: str = ""
    access_token_minutes: int = 480
    testing: bool = False

    # First-run data, only used while the database is still empty.
    initial_admin_username: str = "admin"
    initial_admin_password: str = "CHANGE_ME_BEFORE_USE"
    # Comma-separated "slug:Name" pairs; empty = one default screen in the default language.
    initial_screens: str = ""
    # Initial default publication length of new content in days (0 = no end date).
    default_publication_days: int = 7
    # Calendar (ICS) address pre-filled when creating a Calendar publication.
    default_calendar_ics_url: str = ""

    # Security.
    allowed_networks: str = ""
    login_max_attempts: int = 10
    login_window_seconds: int = 300

    # Upload limits in megabytes.
    max_document_size_mb: int = 100
    max_image_size_mb: int = 25
    max_video_size_mb: int = 500
    max_logo_size_mb: int = 5

    # File storage: "local" (a container path, which may be a NAS share) or "s3".
    storage_backend: Literal["local", "s3"] = "local"
    storage_root: str = "/data"
    s3_bucket: str = ""
    s3_region: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_prefix: str = ""
    s3_force_path_style: bool = False
    # "proxy" streams files through the backend (works when screens have no Internet);
    # "redirect" sends browsers to a short-lived presigned URL on the bucket.
    s3_serve_mode: Literal["proxy", "redirect"] = "proxy"
    s3_presign_seconds: int = 3600

    # Emergency address geocoding (Nominatim-compatible search API).
    geocoding_enabled: bool = True
    geocode_url: str = "https://nominatim.openstreetmap.org/search"
    # Comma-separated ISO 3166-1 alpha-2 codes that restrict results, e.g. "cl" or "us,ca".
    geocode_country_codes: str = ""
    geocode_user_agent: str = ""

    @property
    def resolved_date_locale(self) -> str:
        return self.date_locale.strip() or ("es-ES" if self.default_language == "es" else "en-US")

    def insecure_production_settings(self) -> list[str]:
        """Names of settings that still hold placeholder or weak values."""
        problems = []
        if PLACEHOLDER_MARKER in self.secret_key or self.secret_key == DEVELOPMENT_SECRET_KEY or len(self.secret_key) < 32:
            problems.append("SECRET_KEY")
        if PLACEHOLDER_MARKER in self.initial_admin_password or len(self.initial_admin_password) < 8:
            problems.append("INITIAL_ADMIN_PASSWORD")
        if PLACEHOLDER_MARKER in self.database_url:
            problems.append("DATABASE_URL")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
