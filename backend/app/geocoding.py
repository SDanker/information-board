"""Address to coordinates geocoding for emergencies, using a Nominatim-compatible API.

OpenStreetMap's public Nominatim is free and needs no API key, but the server must have
Internet access, which an isolated LAN installation may not have. Every network error is
therefore swallowed and ``None`` is returned: the emergency form keeps working and the
operator can set the location manually. GEOCODE_URL can point to a self-hosted instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float
    longitude: float
    display_name: str
    provider: str = "nominatim"


def geocode_address(address: str) -> GeocodeResult | None:
    address = address.strip()
    if not address or not get_settings().geocoding_enabled:
        return None
    return _geocode_cached(address)


@lru_cache(maxsize=256)
def _geocode_cached(address: str) -> GeocodeResult | None:
    settings = get_settings()
    # Nominatim's usage policy requires an identifying User-Agent.
    user_agent = settings.geocode_user_agent.strip() or f"{settings.app_name}/1.0 (information-board)"
    params: dict[str, str | int] = {"q": address, "format": "jsonv2", "limit": 1}
    # Restricting countries avoids ambiguous addresses ("100 Main Street") resolving abroad.
    if settings.geocode_country_codes.strip():
        params["countrycodes"] = settings.geocode_country_codes.strip()
    try:
        response = httpx.get(settings.geocode_url, params=params, headers={"User-Agent": user_agent}, timeout=6)
        response.raise_for_status()
        results = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not results:
        return None
    first = results[0]
    try:
        return GeocodeResult(latitude=float(first["lat"]), longitude=float(first["lon"]), display_name=first.get("display_name", address))
    except (KeyError, TypeError, ValueError):
        return None
