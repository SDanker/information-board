"""Optional restriction of administrative access by subnet (ALLOWED_NETWORKS).

Empty (the default) means no restriction. When configured, administrative API routes are only
reachable from those subnets; the keyword "private" allows every private network, so the rule
keeps working when the local network changes. /api/v1/public/*, /api/v1/health and /ws/* stay
open because screens and phones scanning a QR code use them from anywhere on the network.
"""

from __future__ import annotations

import ipaddress

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings
from app.i18n import _
from app.network import client_ip, parse_networks

_ALWAYS_OPEN_PREFIXES = ("/api/v1/public/", "/api/v1/health", "/ws/")


class NetworkRestrictionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        raw = get_settings().allowed_networks
        path = request.url.path
        if not raw or not raw.strip() or not path.startswith("/api/v1") or path.startswith(_ALWAYS_OPEN_PREFIXES):
            return await call_next(request)

        networks = parse_networks(raw)
        if not networks:
            return await call_next(request)

        address_text = client_ip(request)
        try:
            address = ipaddress.ip_address(address_text) if address_text else None
        except ValueError:
            address = None
        if address is not None and any(address in network for network in networks):
            return await call_next(request)

        return JSONResponse(status_code=403, content={"detail": _("Administrative access is not allowed from this network")})
