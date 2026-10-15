"""In-memory token bucket.

Good for a single API process. With several replicas each would keep its own
buckets, so move this to Redis before scaling out (see HLD section 9).
"""

import time
from collections.abc import Callable
from threading import Lock

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import ApiError


class TokenBucket:
    def __init__(self, capacity: int, per_seconds: float):
        self.capacity = capacity
        self.rate = capacity / per_seconds
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            if tokens < 1:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1, now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


auth_bucket = TokenBucket(capacity=10, per_seconds=60)
upload_bucket = TokenBucket(capacity=20, per_seconds=60)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limit_by_ip(bucket: TokenBucket) -> Callable:
    async def dependency(request: Request) -> None:
        if get_settings().rate_limit_enabled and not bucket.allow(
            f"{request.url.path}:{client_ip(request)}"
        ):
            raise ApiError(429, "Too many attempts. Wait a minute and try again.")

    return dependency
