"""Small process-local request limiter for the public demo deployment."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request


_requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = Lock()
_WINDOW_SECONDS = 60.0


def _client_key(request: Request) -> str:
    """Use the proxy-forwarded client address when available, otherwise ASGI peer."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for.strip():
        # Proxies append the connecting address at the right-hand end.
        return forwarded_for.split(",")[-1].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, bucket: str, limit_env: str) -> None:
    """Allow at most the configured number of requests per IP and minute."""
    try:
        limit = max(1, int(os.getenv(limit_env, "10")))
    except ValueError:
        limit = 10

    now = time.monotonic()
    key = (_client_key(request), bucket)
    with _lock:
        # Prune old timestamps and stale keys to keep this in-memory map bounded.
        for old_key in list(_requests):
            history = _requests[old_key]
            while history and now - history[0] >= _WINDOW_SECONDS:
                history.popleft()
            if not history:
                del _requests[old_key]

        history = _requests[key]
        if len(history) >= limit:
            raise HTTPException(
                status_code=429,
                detail="请求太频繁，请一分钟后再试。",
                headers={"Retry-After": "60"},
            )
        history.append(now)
