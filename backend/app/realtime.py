"""Real-time event channel: server to screens and server to the admin panel.

Synchronous HTTP endpoints publish events on a Redis Pub/Sub channel. A single async
listener per backend process forwards each event to the matching local WebSockets.
Using Redis (instead of in-memory fan-out only) keeps events flowing when several
backend replicas serve different screens.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from starlette.websockets import WebSocket

from app.config import get_settings

logger = logging.getLogger("realtime")
CHANNEL = "information-board:events"


def publish_event(event: dict[str, Any]) -> None:
    """Publish an event from a synchronous HTTP endpoint.

    Never raises: if Redis is down, the operation that produced the event (e.g. saving a
    playlist) has already completed; losing the live notification only delays the update
    until the client's next poll.
    """
    settings = get_settings()
    if settings.testing:
        return
    try:
        Redis.from_url(settings.redis_url, socket_timeout=2).publish(CHANNEL, json.dumps(event))
    except Exception:
        logger.warning("Could not publish real-time event", exc_info=True)


class ConnectionManager:
    def __init__(self) -> None:
        self._screen_sockets: dict[str, set[WebSocket]] = {}
        self._admin_sockets: set[WebSocket] = set()
        self._pubsub_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._pubsub_task is None:
            self._pubsub_task = asyncio.create_task(self._listen_forever())

    async def stop(self) -> None:
        if self._pubsub_task is not None:
            self._pubsub_task.cancel()
            self._pubsub_task = None

    async def _listen_forever(self) -> None:
        settings = get_settings()
        while True:
            try:
                client = AsyncRedis.from_url(settings.redis_url)
                pubsub = client.pubsub()
                await pubsub.subscribe(CHANNEL)
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    try:
                        event = json.loads(message["data"])
                    except (TypeError, ValueError):
                        continue
                    await self._dispatch(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Real-time event connection lost, retrying in 3s", exc_info=True)
                await asyncio.sleep(3)

    async def _dispatch(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event)
        target = event.get("target")
        if target in ("admin", None):
            for ws in list(self._admin_sockets):
                await self._safe_send(ws, payload, self._admin_sockets)
        if target == "screen" and event.get("slug"):
            for ws in list(self._screen_sockets.get(event["slug"], ())):
                await self._safe_send(ws, payload, self._screen_sockets[event["slug"]])
        elif target == "all_screens":
            for slug, sockets in list(self._screen_sockets.items()):
                for ws in list(sockets):
                    await self._safe_send(ws, payload, self._screen_sockets[slug])

    @staticmethod
    async def _safe_send(ws: WebSocket, payload: str, bucket: set[WebSocket]) -> None:
        try:
            await ws.send_text(payload)
        except Exception:
            bucket.discard(ws)

    def register_screen(self, slug: str, ws: WebSocket) -> None:
        self._screen_sockets.setdefault(slug, set()).add(ws)

    def unregister_screen(self, slug: str, ws: WebSocket) -> None:
        self._screen_sockets.get(slug, set()).discard(ws)

    def register_admin(self, ws: WebSocket) -> None:
        self._admin_sockets.add(ws)

    def unregister_admin(self, ws: WebSocket) -> None:
        self._admin_sockets.discard(ws)


manager = ConnectionManager()
