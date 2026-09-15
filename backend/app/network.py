"""Network helpers: the public address used in QR codes and links, the real client IP and
the ALLOWED_NETWORKS parser.

The public address is automatic by default. When PUBLIC_BASE_URL is empty (or "auto"), links
are built from the address the visitor used to reach the server, which nginx forwards in the
Host and X-Forwarded-Proto headers. Moving the server to another IP address or network therefore
needs no configuration change: a TV opened at http://10.0.0.8/screen/lobby shows a QR code for
http://10.0.0.8/catalog/lobby, and the same TV opened at http://board.lan shows board.lan.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
from urllib.parse import urlsplit

from starlette.requests import HTTPConnection

from app.config import get_settings

logger = logging.getLogger("network")

AUTO_KEYWORD = "auto"
# ALLOWED_NETWORKS keyword covering every private range, so the restriction keeps working when
# the local network (and its subnet) changes.
PRIVATE_KEYWORD = "private"
PRIVATE_NETWORKS = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
)

# A host name, IPv4 address or bracketed IPv6 address, with an optional port. Anything else in
# the Host header (paths, spaces, credentials) is rejected so it can never end up inside a link.
_HOST_PATTERN = re.compile(r"^(?:\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?)(?::\d{1,5})?$")
_DEFAULT_PORTS = {"http": ":80", "https": ":443"}
_WEBSOCKET_SCHEMES = {"ws": "http", "wss": "https"}


def _first_value(value: str | None) -> str:
    """First entry of a header that proxies may turn into a comma-separated list."""
    return (value or "").split(",")[0].strip()


def configured_base_url() -> str | None:
    """PUBLIC_BASE_URL when it forces a fixed address, or None in automatic mode."""
    raw = get_settings().public_base_url.strip()
    if not raw or raw.lower() == AUTO_KEYWORD:
        return None
    return raw.rstrip("/")


def public_base_url(connection: HTTPConnection) -> str:
    """Base address (scheme://host[:port]) for links and QR codes shown to this visitor."""
    fixed = configured_base_url()
    if fixed:
        return fixed

    scheme = _first_value(connection.headers.get("x-forwarded-proto")).lower() or connection.url.scheme
    scheme = _WEBSOCKET_SCHEMES.get(scheme, scheme)
    if scheme not in _DEFAULT_PORTS:
        scheme = "http"

    host = _first_value(connection.headers.get("x-forwarded-host")) or connection.headers.get("host", "")
    if not _HOST_PATTERN.fullmatch(host):
        host = "localhost"
    if host.endswith(_DEFAULT_PORTS[scheme]):
        host = host[: -len(_DEFAULT_PORTS[scheme])]
    return f"{scheme}://{host}"


def is_loopback_url(url: str) -> bool:
    """True when the address only works on the server itself (localhost, 127.x, ::1)."""
    hostname = (urlsplit(url).hostname or "").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def url_version(url: str) -> str:
    """Short fingerprint added to QR image URLs, so browsers fetch a new image when the address changes."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]


def _is_trusted_proxy(peer: str | None) -> bool:
    """X-Real-IP is only trusted from a proxy on a private network (nginx inside Docker)."""
    if not peer:
        return True
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        # Unix sockets and the test client have no IP address: there is no public peer to distrust.
        return True
    return address.is_private or address.is_loopback


def client_ip(connection: HTTPConnection) -> str | None:
    """Address of the browser that made the request, as seen by nginx."""
    peer = connection.client.host if connection.client else None
    forwarded = _first_value(connection.headers.get("x-real-ip"))
    if forwarded and _is_trusted_proxy(peer):
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            logger.warning("Ignoring invalid X-Real-IP header: %r", forwarded[:64])
    return peer


def parse_networks(raw: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse ALLOWED_NETWORKS: comma-separated subnets and/or the keyword "private"."""
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.lower() == PRIVATE_KEYWORD:
            networks.extend(ipaddress.ip_network(network) for network in PRIVATE_NETWORKS)
            continue
        try:
            networks.append(ipaddress.ip_network(chunk, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid ALLOWED_NETWORKS entry: %r", chunk)
    return networks
