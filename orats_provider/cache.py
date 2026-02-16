from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple


class TTLCache:
    """
    Simple in-memory TTL cache.
    """

    def __init__(self, ttl_seconds: int = 900) -> None:
        self.ttl_seconds = int(ttl_seconds)
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if not item:
            return None

        created_at, value = item
        if time.time() - created_at > self.ttl_seconds:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()
