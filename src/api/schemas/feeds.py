"""Pydantic models for feed digest API responses."""

from datetime import datetime

from pydantic import BaseModel


class FeedDigestItem(BaseModel):
    """A single feed's latest article summary."""

    feed_name: str
    category: str
    latest_title: str | None = None
    latest_title_zh: str | None = None
    latest_url: str | None = None
    latest_date: str | None = None  # ISO 8601, e.g. "2025-06-15T10:00:00Z"
    latest_summary: str | None = None  # plain-text, ≤200 chars
    latest_summary_zh: str | None = None  # Chinese translation of summary
    new_count: int = 0


class FeedDigestResponse(BaseModel):
    """Aggregated digest of all RSS feeds."""

    items: list[FeedDigestItem]
    total_feeds: int
    feeds_with_updates: int  # latest_title 非空的数量
    fetched_at: datetime
    cached: bool  # True=缓存命中, False=刚抓取
    ttl_seconds: int
