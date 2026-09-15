"""Optional restriction of administrative access by subnet (ALLOWED_NETWORKS).

Empty (the default) means no restriction. When configured, administrative API routes
are only reachable from those subnets. /api/v1/public/*, /api/v1/health and /ws/* stay
open because screens and phones scanning a QR code use them from anywhere on the network.
"""

from __future__ import annotations

import ipaddress
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings
from app.i18n import _

logger = logging.getLogger("network_restriction")

_ALWAYS_OPEN_PREFIXES = ("/api/v1/public/", "/api/v1/health", "/ws/")


def _parse_networks(raw: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            networks.append(ipaddress.ip_network(chunk, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid ALLOWED_NETWORKS entry: %r", chunk)
    return networks


class NetworkRestrictionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        raw = get_settings().allowed_networks
        path = request.url.path
        if not raw or not raw.strip() or not path.startswith("/api/v1") or path.startswith(_ALWAYS_OPEN_PREFIXES):
            return await call_next(request)

        networks = _parse_networks(raw)
        if not networks:
            return await call_next(request)

        # nginx sets X-Real-IP; without it the direct peer address is used.
        client_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else None)
        try:
            address = ipaddress.ip_address(client_ip) if client_ip else None
        except ValueError:
            address = None
        if address is not None and any(address in network for network in networks):
            return await call_next(request)

        return JSONResponse(status_code=403, content={"detail": _("Administrative access is not allowed from this network")})
