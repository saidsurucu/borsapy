"""TTL-based in-memory cache for borsapy."""

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """A single cache entry with value and expiration time."""

    value: T
    expires_at: float


@dataclass
class Cache:
    """Thread-safe TTL-based in-memory cache."""

    _store: dict[str, CacheEntry] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def get(self, key: str) -> Any | None:
        """Get a value from cache if it exists and hasn't expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() > entry.expires_at:
                del self._store[key]
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Set a value in cache with TTL in seconds."""
        with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=time.time() + ttl_seconds)

    def delete(self, key: str) -> bool:
        """Delete a key from cache. Returns True if key existed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self._store.clear()

    def cleanup(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        with self._lock:
            now = time.time()
            expired_keys = [k for k, v in self._store.items() if now > v.expires_at]
            for key in expired_keys:
                del self._store[key]
            return len(expired_keys)


# TTL values in seconds
class TTL:
    """Standard TTL values for different data types."""

    REALTIME_PRICE = 60  # 1 minute
    OHLCV_HISTORY = 3600  # 1 hour
    COMPANY_INFO = 3600  # 1 hour
    FINANCIAL_STATEMENTS = 86400  # 24 hours
    FX_RATES = 300  # 5 minutes
    COMPANY_LIST = 86400  # 24 hours
    FUND_DATA = 3600  # 1 hour
    INFLATION_DATA = 86400  # 24 hours


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache
