"""Clerk JWT verification as a FastAPI dependency.

Uses the official ``clerk-backend-api`` SDK to validate session tokens
issued by Clerk.  The dependency extracts the ``Authorization: Bearer``
header, converts the incoming FastAPI request into an ``httpx.Request``
(required by the SDK), and calls ``authenticate_request()``.

Usage::

    from src.api.auth import get_current_user

    @router.get("/protected")
    async def protected_route(user: dict = Depends(get_current_user)):
        ...
"""

from __future__ import annotations

import os

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security import AuthenticateRequestOptions
from fastapi import HTTPException, Request, status

from src.config.settings import resolve_clerk_settings


async def get_current_user(request: Request) -> dict:
    """FastAPI dependency: verify Clerk session token.

    Returns the decoded JWT payload on success, or raises 401.
    """
    secret_key = os.getenv("CLERK_SECRET_KEY", "")
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_SECRET_KEY is not configured",
        )

    clerk = Clerk(bearer_auth=secret_key)

    # The SDK expects an httpx.Request for header inspection
    httpx_request = httpx.Request(
        method=request.method,
        url=str(request.url),
        headers=dict(request.headers),
    )

    request_state = clerk.authenticate_request(
        httpx_request,
        AuthenticateRequestOptions(
            authorized_parties=_get_authorized_parties(),
        ),
    )

    if not request_state.is_signed_in:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return request_state.payload  # type: ignore[return-value]


def _get_authorized_parties() -> list[str]:
    """Build the list of authorized parties (frontend origins).

    Reads ``CLERK_AUTHORIZED_PARTIES`` (comma-separated) from env,
    falling back to local frontend dev origins.
    """
    return resolve_clerk_settings().authorized_parties
