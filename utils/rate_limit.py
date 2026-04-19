import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    def __init__(self):
        self._buckets: dict[str, Deque[float]] = defaultdict(deque)

    def limit(self, *, key: str, max_requests: int, window_seconds: int):
        async def dependency(request: Request):
            # best-effort identifier
            ident = request.client.host if request.client else "unknown"
            bucket_key = f"{key}:{ident}"

            now = time.time()
            window_start = now - window_seconds
            q = self._buckets[bucket_key]
            while q and q[0] < window_start:
                q.popleft()
            if len(q) >= max_requests:
                raise HTTPException(status_code=429, detail="Too many requests, please try again later.")
            q.append(now)

        return dependency


rate_limiter = InMemoryRateLimiter()

