"""Simple per-key attempt limiter backed by Redis.

Redis keeps the counters across backend restarts and stays correct with several
Uvicorn workers. If Redis is unavailable the request is allowed: degrading without a
limit is better than locking everyone out of the login because of a Redis problem.
"""

from __future__ import annotations

import logging

from redis import Redis

from app.config import get_settings

logger = logging.getLogger("rate_limit")
_KEY_PREFIX = "information-board:rate:"


def too_many_attempts(key: str, *, limit: int, window_seconds: int) -> bool:
    settings = get_settings()
    if settings.testing:
        return False
    try:
        client = Redis.from_url(settings.redis_url, socket_timeout=1)
        count = client.incr(f"{_KEY_PREFIX}{key}")
        if count == 1:
            client.expire(f"{_KEY_PREFIX}{key}", window_seconds)
        return count > limit
    except Exception:
        logger.warning("Redis unavailable for rate limiting; allowing the request", exc_info=True)
        return False


def reset(key: str) -> None:
    settings = get_settings()
    if settings.testing:
        return
    try:
        Redis.from_url(settings.redis_url, socket_timeout=1).delete(f"{_KEY_PREFIX}{key}")
    except Exception:
        pass
