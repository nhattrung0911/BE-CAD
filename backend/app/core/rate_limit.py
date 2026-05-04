"""Lightweight rate limiter for admin/expensive endpoints.

Uses Redis sliding-window when REDIS_URL is set, falls back to in-process
counters otherwise. The in-process limiter only protects a single replica;
production deployments must run with Redis to share state across replicas.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock
from typing import Awaitable, Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class _MemoryLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    def hit(self, key: str, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            cutoff = now - window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


_memory_limiter = _MemoryLimiter()


def _redis_client():
    if not settings.redis_url:
        return None
    try:
        import redis  # type: ignore

        return redis.Redis.from_url(settings.redis_url, socket_timeout=0.5)
    except Exception as exc:
        logger.warning("rate-limit redis unavailable: %s", exc)
        return None


def _redis_hit(client, key: str, limit: int, window_seconds: float) -> bool:
    now = time.time()
    cutoff = now - window_seconds
    pipe = client.pipeline()
    pipe.zremrangebyscore(key, 0, cutoff)
    pipe.zadd(key, {f"{now}:{id(object())}": now})
    pipe.zcard(key)
    pipe.expire(key, int(window_seconds) + 1)
    try:
        _, _, count, _ = pipe.execute()
    except Exception as exc:
        logger.warning("rate-limit redis hit failed (%s): %s", key, exc)
        return _memory_limiter.hit(key, limit, window_seconds)
    return int(count) <= limit


def _client_id(request: Request) -> str:
    admin_key = request.headers.get(settings.admin_api_key_header)
    if admin_key:
        return f"admin:{admin_key[:12]}"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def rate_limit(*, name: str, limit: int, window_seconds: float) -> Callable[[Request], Awaitable[None]]:
    """FastAPI dependency factory — limit hits per (client, endpoint name)."""

    async def _dep(request: Request) -> None:
        key = f"rl:{name}:{_client_id(request)}"
        client = _redis_client()
        ok = (
            _redis_hit(client, key, limit, window_seconds)
            if client is not None
            else _memory_limiter.hit(key, limit, window_seconds)
        )
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {name}: max {limit}/{int(window_seconds)}s",
            )

    return _dep


def reset_for_testing() -> None:
    _memory_limiter._buckets.clear()
