import logging
import threading
import time
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)


class TTLCache:
    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: str, loader: Callable[[], Any]) -> Any:
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry and (now - entry[0]) < self.ttl:
                log.debug("cache HIT %s", key)
                return entry[1]
        value = loader()
        with self._lock:
            self._store[key] = (time.time(), value)
        return value

    def invalidate_all(self):
        with self._lock:
            self._store.clear()
            log.info("cache cleared")
