"""Tests for feed digest service and API route."""

import asyncio
from datetime import datetime
from unittest.mock import patch

import pytest

from src.api.schemas.feeds import FeedDigestResponse
from src.api.services import feed_digest_service
from src.tools.rss_feeds import FeedArticle, FeedInfo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FAKE_FEEDS = [
    FeedInfo(name="Blog A", xml_url="http://a.com/rss", html_url="http://a.com", category="Tech"),
    FeedInfo(name="Blog B", xml_url="http://b.com/rss", html_url="http://b.com", category="AI"),
    FeedInfo(name="Blog C", xml_url="http://c.com/rss", html_url="http://c.com", category="Tech"),
]


def _fake_fetch(feed: FeedInfo, limit: int) -> list[FeedArticle]:
    """Return a deterministic article for each fake feed."""
    return [
        FeedArticle(
            title=f"Latest from {feed.name}",
            url=f"{feed.html_url}/post-1",
            published="2025-06-15T10:00:00Z",
            summary="A summary.",
            feed_name=feed.name,
        )
    ]


def _fake_fetch_empty(feed: FeedInfo, limit: int) -> list[FeedArticle]:
    return []


@pytest.fixture(autouse=True)
def _reset_digest_cache(monkeypatch: pytest.MonkeyPatch):
    """Reset module-level cache before and after each test."""
    feed_digest_service.reset_cache()
    monkeypatch.setattr(
        feed_digest_service,
        "_translate_summaries_sync",
        lambda items: None,
    )
    yield
    feed_digest_service.reset_cache()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("src.api.services.feed_digest_service._parse_opml", return_value=_FAKE_FEEDS)
@patch("src.api.services.feed_digest_service._fetch_single_feed", side_effect=_fake_fetch)
async def test_first_call_builds_digest(mock_fetch, mock_opml):
    """First call should build the digest (cached=False)."""
    resp = await feed_digest_service.get_feed_digest()

    assert isinstance(resp, FeedDigestResponse)
    assert resp.cached is False
    assert resp.total_feeds == 3
    assert resp.feeds_with_updates == 3
    assert len(resp.items) == 3
    assert resp.items[0].latest_title.startswith("Latest from ")
    mock_opml.assert_called_once()


@patch("src.api.services.feed_digest_service._parse_opml", return_value=_FAKE_FEEDS)
@patch("src.api.services.feed_digest_service._fetch_single_feed", side_effect=_fake_fetch)
async def test_second_call_hits_cache(mock_fetch, mock_opml):
    """Second call within TTL should return cached=True without re-fetching."""
    first = await feed_digest_service.get_feed_digest()
    assert first.cached is False

    second = await feed_digest_service.get_feed_digest()
    assert second.cached is True
    # _parse_opml should only be called once (during the first build)
    assert mock_opml.call_count == 1


@patch("src.api.services.feed_digest_service._parse_opml", return_value=_FAKE_FEEDS)
@patch("src.api.services.feed_digest_service._fetch_single_feed", side_effect=_fake_fetch)
async def test_force_refresh_bypasses_cache(mock_fetch, mock_opml):
    """force_refresh=True should rebuild even when cache is valid."""
    first = await feed_digest_service.get_feed_digest()
    assert first.cached is False

    refreshed = await feed_digest_service.get_feed_digest(force_refresh=True)
    assert refreshed.cached is False
    assert mock_opml.call_count == 2


@patch("src.api.services.feed_digest_service._parse_opml", return_value=_FAKE_FEEDS)
@patch("src.api.services.feed_digest_service._fetch_single_feed", side_effect=_fake_fetch_empty)
async def test_empty_feeds_still_returns_items(mock_fetch, mock_opml):
    """Feeds that return no articles should still appear with null fields."""
    resp = await feed_digest_service.get_feed_digest()

    assert resp.total_feeds == 3
    assert resp.feeds_with_updates == 0
    for item in resp.items:
        assert item.latest_title is None
        assert item.new_count == 0


@patch("src.api.services.feed_digest_service._parse_opml", return_value=_FAKE_FEEDS)
@patch("src.api.services.feed_digest_service._fetch_single_feed", side_effect=_fake_fetch)
async def test_concurrent_requests_single_fetch(mock_fetch, mock_opml):
    """Multiple concurrent requests should only trigger one build."""
    results = await asyncio.gather(
        feed_digest_service.get_feed_digest(),
        feed_digest_service.get_feed_digest(),
        feed_digest_service.get_feed_digest(),
    )

    # Only one call should have built the digest
    assert mock_opml.call_count == 1
    # All should succeed
    assert all(isinstance(r, FeedDigestResponse) for r in results)
    # At most one should be cached=False (the builder), rest cached=True
    non_cached = [r for r in results if not r.cached]
    assert len(non_cached) == 1


@patch("src.api.services.feed_digest_service._parse_opml", return_value=_FAKE_FEEDS)
@patch("src.api.services.feed_digest_service._fetch_single_feed", side_effect=_fake_fetch)
async def test_ttl_expiry_triggers_rebuild(mock_fetch, mock_opml):
    """After TTL expires, next request should rebuild."""
    await feed_digest_service.get_feed_digest()
    assert mock_opml.call_count == 1

    # Simulate TTL expiry by backdating the timestamp
    feed_digest_service._cache_timestamp = 0.0

    await feed_digest_service.get_feed_digest()
    assert mock_opml.call_count == 2


@patch("src.api.services.feed_digest_service._parse_opml", return_value=_FAKE_FEEDS)
@patch("src.api.services.feed_digest_service._fetch_single_feed", side_effect=_fake_fetch)
async def test_response_fields(mock_fetch, mock_opml):
    """Verify all response fields are populated correctly."""
    resp = await feed_digest_service.get_feed_digest()

    assert resp.ttl_seconds == feed_digest_service._DEFAULT_TTL
    assert isinstance(resp.fetched_at, datetime)
    assert resp.fetched_at.tzinfo is not None  # timezone-aware

    item = resp.items[0]
    assert item.feed_name in {"Blog A", "Blog B", "Blog C"}
    assert item.category in {"Tech", "AI"}
    assert item.latest_url is not None
    assert item.latest_date == "2025-06-15T10:00:00Z"
    assert item.new_count == 1
