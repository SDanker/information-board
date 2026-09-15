import sys
import time

from redis import Redis

from app.config import get_settings

value = Redis.from_url(get_settings().redis_url, socket_timeout=2).get("information-board:worker:heartbeat")
if value is None or time.time() - float(value) > 20:
    sys.exit(1)
