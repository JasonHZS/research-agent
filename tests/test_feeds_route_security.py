"""Security tests for feeds digest route."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.feeds import reset_force_refresh_rate_limiter, router
from src.api.schemas.feeds import FeedDigestResponse


@pytest.fixture(autouse=True)
def _reset_rate_limiter(monkeypatch: pytest.MonkeyPatch):
    reset_force_refresh_rate_limiter()
    monkeypatch.delenv("FEEDS_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("FEEDS_FORCE_REFRESH_RATE_LIMIT", raising=False)
    monkeypatch.delenv("FEEDS_FORCE_REFRESH_WINDOW_SECONDS", raising=False)
    yield
    reset_force_refresh_rate_limiter()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def _mock_digest() -> FeedDigestResponse:
    return FeedDigestResponse(
        items=[],
        total_feeds=0,
        feeds_with_updates=0,
        fetched_at=datetime.now(timezone.utc),
        cached=True,
        ttl_seconds=10800,
    )


def test_digest_without_force_refresh_does_not_require_admin_token(client: TestClient):
    with patch("src.api.routes.feeds.get_feed_digest", new=AsyncMock(return_value=_mock_digest())):
        response = client.get("/api/feeds/digest")

    assert response.status_code == 200


def test_force_refresh_rejected_when_admin_token_not_configured(client: TestClient):
    with patch("src.api.routes.feeds.get_feed_digest", new=AsyncMock(return_value=_mock_digest())):
        response = client.get("/api/feeds/digest?force_refresh=true")

    assert response.status_code == 403
    assert "disabled" in response.json()["detail"]


def test_force_refresh_rejected_with_invalid_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FEEDS_ADMIN_TOKEN", "top-secret")

    with patch("src.api.routes.feeds.get_feed_digest", new=AsyncMock(return_value=_mock_digest())):
        response = client.get(
            "/api/feeds/digest?force_refresh=true",
            headers={"X-Admin-Token": "wrong-token"},
        )

    assert response.status_code == 403
    assert "Admin token required" in response.json()["detail"]


def test_force_refresh_allowed_with_valid_admin_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FEEDS_ADMIN_TOKEN", "top-secret")
    mocked_get_digest = AsyncMock(return_value=_mock_digest())

    with patch("src.api.routes.feeds.get_feed_digest", new=mocked_get_digest):
        response = client.get(
            "/api/feeds/digest?force_refresh=true",
            headers={"X-Admin-Token": "top-secret"},
        )

    assert response.status_code == 200
    mocked_get_digest.assert_awaited_once_with(force_refresh=True)


def test_force_refresh_allowed_with_bearer_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FEEDS_ADMIN_TOKEN", "top-secret")
    mocked_get_digest = AsyncMock(return_value=_mock_digest())

    with patch("src.api.routes.feeds.get_feed_digest", new=mocked_get_digest):
        response = client.get(
            "/api/feeds/digest?force_refresh=true",
            headers={"Authorization": "Bearer top-secret"},
        )

    assert response.status_code == 200
    mocked_get_digest.assert_awaited_once_with(force_refresh=True)


def test_force_refresh_rejected_with_invalid_bearer_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FEEDS_ADMIN_TOKEN", "top-secret")

    with patch("src.api.routes.feeds.get_feed_digest", new=AsyncMock(return_value=_mock_digest())):
        response = client.get(
            "/api/feeds/digest?force_refresh=true",
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert response.status_code == 403
    assert "Admin token required" in response.json()["detail"]


def test_force_refresh_rate_limited(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FEEDS_ADMIN_TOKEN", "top-secret")
    monkeypatch.setenv("FEEDS_FORCE_REFRESH_RATE_LIMIT", "1")
    monkeypatch.setenv("FEEDS_FORCE_REFRESH_WINDOW_SECONDS", "60")

    with patch("src.api.routes.feeds.get_feed_digest", new=AsyncMock(return_value=_mock_digest())):
        first = client.get(
            "/api/feeds/digest?force_refresh=true",
            headers={"X-Admin-Token": "top-secret"},
        )
        second = client.get(
            "/api/feeds/digest?force_refresh=true",
            headers={"X-Admin-Token": "top-secret"},
        )

    assert first.status_code == 200
    assert second.status_code == 429
    assert "rate limit exceeded" in second.json()["detail"]
