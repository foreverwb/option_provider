"""
Thread-safe in-memory TTL cache for ORATS API responses.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional


class TTLCache:
    """Simple thread-safe TTL cache backed by a dictionary."""

    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        self._store: Dict[str, tuple] = {}   # key → (value, expire_at)
        self._lock = threading.Lock()
        self._default_ttl = default_ttl
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expire_at = entry
            if time.time() > expire_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        expire_at = time.time() + ttl
        with self._lock:
            # Evict if over capacity
            if len(self._store) >= self._max_size and key not in self._store:
                self._evict_expired()
                if len(self._store) >= self._max_size:
                    oldest_key = next(iter(self._store))
                    del self._store[oldest_key]
            self._store[key] = (value, expire_at)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _evict_expired(self) -> None:
        """Remove all expired entries (caller must hold lock)."""
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def make_key(self, *parts: str) -> str:
        """Build a cache key from parts."""
        return ":".join(str(p) for p in parts)
