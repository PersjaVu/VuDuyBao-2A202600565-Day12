import time
from collections import defaultdict, deque
from fastapi import HTTPException
from .config import settings

_rate_windows: dict = defaultdict(deque)


def check_rate_limit(user_id: str) -> None:
    """Sliding window rate limiter. Raises 429 if user exceeds rate_limit_per_minute."""
    now = time.time()
    window = _rate_windows[user_id]
    # Remove timestamps older than 60s
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        retry_after = int(window[0] + 60 - now) + 1
        raise HTTPException(
            status_code=429,
            detail={"error": "Rate limit exceeded", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )
    window.append(now)
