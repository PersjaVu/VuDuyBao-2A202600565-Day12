"""Unit tests — rate limiter (sliding window)."""
import pytest
from app.rate_limiter import check_rate_limit, _rate_windows
from fastapi import HTTPException


def _flush(user_id: str):
    _rate_windows.pop(user_id, None)


def test_within_limit_passes():
    _flush("rl-user-1")
    for _ in range(5):
        check_rate_limit("rl-user-1")  # should not raise


def test_exceeds_limit_raises_429():
    _flush("rl-user-2")
    from app.config import settings
    limit = settings.rate_limit_per_minute

    for _ in range(limit):
        check_rate_limit("rl-user-2")

    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit("rl-user-2")
    assert exc_info.value.status_code == 429


def test_different_users_independent():
    _flush("rl-user-a")
    _flush("rl-user-b")
    from app.config import settings
    limit = settings.rate_limit_per_minute

    for _ in range(limit):
        check_rate_limit("rl-user-a")

    # rl-user-b should still pass even though rl-user-a is blocked
    check_rate_limit("rl-user-b")
