"""Server-side translation of user-facing messages.

Application code always writes messages in English and wraps them in ``_()``.
The active language comes from the current request (``X-Language`` or
``Accept-Language`` headers, resolved by :class:`LanguageMiddleware`) and falls
back to ``DEFAULT_LANGUAGE`` outside of a request, for example in the worker.

English is the source language and needs no catalog. Adding a language means
adding a catalog module under ``app/locales`` and registering it in ``_CATALOGS``.
"""

from __future__ import annotations

from contextvars import ContextVar

from app.config import get_settings
from app.locales import es

SUPPORTED_LANGUAGES = ("en", "es")

_CATALOGS: dict[str, dict[str, str]] = {"es": es.MESSAGES}

_request_language: ContextVar[str | None] = ContextVar("request_language", default=None)


def normalize_language(value: str | None) -> str | None:
    """Return the preferred supported language from a header such as ``es-CL,es;q=0.9,en;q=0.8``."""
    if not value:
        return None
    candidates: list[tuple[float, int, str]] = []
    for index, part in enumerate(value.split(",")):
        piece = part.strip()
        if not piece:
            continue
        tag, _separator, params = piece.partition(";")
        quality = 1.0
        params = params.strip()
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                quality = 0.0
        candidates.append((-quality, index, tag.strip().lower()))
    for _quality, _index, tag in sorted(candidates):
        primary = tag.split("-")[0]
        if primary in SUPPORTED_LANGUAGES:
            return primary
    return None


def current_language() -> str:
    return _request_language.get() or get_settings().default_language


def translate(message: str, language: str | None = None, **params: object) -> str:
    text = _CATALOGS.get(language or current_language(), {}).get(message, message)
    return text.format(**params) if params else text


def _(message: str, **params: object) -> str:
    """Translate ``message`` into the active language and fill its ``{placeholders}``."""
    return translate(message, **params)


class LanguageMiddleware:
    """Pure ASGI middleware, so the language is visible to dependencies, validators
    and route handlers of the same request (context variables are copied into the
    tasks that serve it)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        language = normalize_language(headers.get("x-language")) or normalize_language(headers.get("accept-language"))
        token = _request_language.set(language)
        try:
            await self.app(scope, receive, send)
        finally:
            _request_language.reset(token)
