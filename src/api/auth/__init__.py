"""Clerk-based authentication for the Research Agent API."""

from src.api.auth.clerk_auth import get_current_user

__all__ = ["get_current_user"]
