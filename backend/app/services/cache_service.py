import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from app.core.config import settings


@dataclass
class CacheEntry:
    value: Any
    expires_at: float | None


@dataclass
class LockToken:
    key: str
    backend: str = "memory"


class InMemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, CacheEntry] = {}
        self._locks: set[str] = set()
        self._mutex = Lock()

    def get(self, key: str) -> Any | None:
        with self._mutex:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.expires_at is not None and time.monotonic() > entry.expires_at:
                del self._data[key]
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expires_at = time.monotonic() + ttl_seconds if ttl_seconds is not None else None
        with self._mutex:
            self._data[key] = CacheEntry(value=value, expires_at=expires_at)

    def acquire_lock(self, key: str, ttl_seconds: int = 60) -> LockToken | None:
        with self._mutex:
            if key in self._locks:
                return None
            self._locks.add(key)
            return LockToken(key=key)

    def release_lock(self, token: LockToken) -> None:
        with self._mutex:
            self._locks.discard(token.key)

    def clear(self) -> None:
        with self._mutex:
            self._data.clear()
            self._locks.clear()

    def is_connected(self) -> bool:
        return False


class RedisCache:
    def __init__(self, url: str, fallback: InMemoryCache) -> None:
        self.fallback = fallback
        self._strict = settings.require_redis_for_ready
        try:
            import redis

            self.client = redis.Redis.from_url(url, decode_responses=False)
            self.client.ping()
        except Exception as exc:
            if self._strict:
                raise RuntimeError(
                    "Redis connection failed and REQUIRE_REDIS_FOR_READY=true. "
                    "Cannot fall back to in-memory cache in production."
                ) from exc
            self.client = None

    def get(self, key: str) -> Any | None:
        if self.client is None:
            return self.fallback.get(key)
        import json

        raw = self.client.get(key)
        return json.loads(raw) if raw else None

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        if self.client is None:
            return self.fallback.set(key, value, ttl_seconds)
        import json

        self.client.set(key, json.dumps(value), ex=ttl_seconds)

    def acquire_lock(self, key: str, ttl_seconds: int = 60) -> LockToken | None:
        if self.client is None:
            return self.fallback.acquire_lock(key, ttl_seconds)
        ok = self.client.set(key, "1", nx=True, ex=ttl_seconds)
        return LockToken(key=key, backend="redis") if ok else None

    def release_lock(self, token: LockToken) -> None:
        if self.client is None or token.backend == "memory":
            return self.fallback.release_lock(token)
        self.client.delete(token.key)

    def clear(self) -> None:
        if self.client is None:
            return self.fallback.clear()

    def is_connected(self) -> bool:
        if self.client is None:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            return False


cache = RedisCache(settings.redis_url, InMemoryCache()) if settings.redis_url else InMemoryCache()
