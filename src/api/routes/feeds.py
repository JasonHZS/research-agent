"""Feed digest API routes."""

from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from src.api.auth import get_current_user
from src.api.schemas.feeds import FeedDigestResponse
from src.api.services.feed_digest_service import get_feed_digest
from src.config.settings import resolve_feed_digest_security_settings

router = APIRouter(prefix="/feeds", tags=["feeds"])


class _SlidingWindowLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        threshold = now - window_seconds

        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= threshold:
                bucket.popleft()

            if len(bucket) >= limit:
                return False

            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


_force_refresh_limiter = _SlidingWindowLimiter()


def reset_force_refresh_rate_limiter() -> None:
    """Reset in-memory force_refresh rate limit state (for tests)."""
    _force_refresh_limiter.reset()


def _get_client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_hop = forwarded_for.split(",", maxsplit=1)[0].strip()
        if first_hop:
            return first_hop

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def _authorize_force_refresh(
    request: Request,
    x_admin_token: str | None,
) -> None:
    security_settings = resolve_feed_digest_security_settings()
    expected_token = security_settings.admin_token

    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="force_refresh is disabled because FEEDS_ADMIN_TOKEN is not configured.",
        )

    provided_token = (x_admin_token or "").strip()
    if not provided_token or not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Admin token required for force_refresh. "
                "Use header X-Admin-Token."
            ),
        )

    client_id = _get_client_identifier(request)
    allowed = _force_refresh_limiter.allow(
        key=client_id,
        limit=security_settings.force_refresh_rate_limit,
        window_seconds=security_settings.force_refresh_window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "force_refresh rate limit exceeded. "
                "Please retry later."
            ),
        )


@router.get("/digest", response_model=FeedDigestResponse)
async def feed_digest(
    request: Request,
    force_refresh: bool = Query(False, description="Bypass cache and re-fetch all feeds"),
    x_admin_token: str | None = Header(
        default=None,
        alias="X-Admin-Token",
        description="Admin token required when force_refresh=true.",
    ),
    user: dict = Depends(get_current_user),
) -> FeedDigestResponse:
    """Get a lightweight digest of the latest article from every RSS feed.

    Returns one entry per feed with the newest article title, URL, and date.
    Results are cached in memory with a 3-hour TTL; first request may take
    10-15 seconds while subsequent requests return instantly.
    """
    if force_refresh:
        _authorize_force_refresh(
            request=request,
            x_admin_token=x_admin_token,
        )

    return await get_feed_digest(force_refresh=force_refresh)
