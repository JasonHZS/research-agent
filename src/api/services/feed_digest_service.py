"""Feed Digest Service — lazy-load + in-memory cache + TTL.

Fetches the latest article from every RSS feed in parallel, caches the
result in process memory, and serves subsequent requests instantly until
the TTL expires.

Uses asyncio.Lock with double-checked locking to prevent thundering-herd
when multiple requests hit an expired cache simultaneously.
"""

import asyncio
import logging
import re
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from concurrent.futures import (
    TimeoutError as FuturesTimeoutError,
)
from datetime import datetime, timezone

from src.api.schemas.feeds import FeedDigestItem, FeedDigestResponse
from src.tools.rss_feeds import _fetch_single_feed, _parse_opml

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_summary(raw: str, max_len: int = 200) -> str | None:
    """Strip HTML tags and truncate to *max_len* characters."""
    text = _HTML_TAG_RE.sub("", raw).strip()
    if not text:
        return None
    return text[:max_len] + ("…" if len(text) > max_len else "")


def _translate_summaries_sync(items: list[FeedDigestItem]) -> None:
    """Batch-translate titles and summaries to Chinese using qwen3.5-plus.

    Mutates items in-place, setting ``latest_title_zh`` and ``latest_summary_zh``.
    Best-effort: on any failure the items are left untouched.
    """
    # Collect texts to translate: (item_idx, field, text)
    entries: list[tuple[int, str, str]] = []
    for idx, item in enumerate(items):
        if item.latest_title:
            entries.append((idx, "title", item.latest_title))
        if item.latest_summary:
            entries.append((idx, "summary", item.latest_summary))

    if not entries:
        return

    # Build a numbered list for the LLM
    lines = [f"{i+1}. {text}" for i, (_, _, text) in enumerate(entries)]
    prompt = (
        "将以下编号的英文文本逐条翻译为简洁的中文，保持编号格式不变。"
        "只输出翻译结果，不要添加任何解释。\n\n"
        + "\n".join(lines)
    )

    try:
        from src.config.llm_factory import create_llm

        llm = create_llm(model_provider="aliyun", model_name="qwen3.5-plus")
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
    except Exception:
        logger.warning("Feed digest translation failed", exc_info=True)
        return

    # Parse numbered lines from response
    translations: dict[int, str] = {}
    for line in str(content).strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Match patterns like "1. 翻译内容" or "1、翻译内容"
        m = re.match(r"^(\d+)[.、．]\s*(.+)$", line)
        if m:
            num = int(m.group(1))
            translations[num] = m.group(2).strip()

    # Assign translations back to items
    for seq, (item_idx, field, _) in enumerate(entries):
        zh = translations.get(seq + 1)
        if zh:
            key = "latest_title_zh" if field == "title" else "latest_summary_zh"
            items[item_idx] = items[item_idx].model_copy(
                update={key: zh}
            )

# ---------------------------------------------------------------------------
# Cache state (module-level, process-scoped)
# ---------------------------------------------------------------------------
_cache: FeedDigestResponse | None = None
_cache_timestamp: float = 0.0
# Lazy-initialized to avoid binding to the wrong event loop on Python 3.11
# (asyncio.Lock created before the loop starts can cause RuntimeError)
_cache_lock: asyncio.Lock | None = None

# 3 hours default TTL
_DEFAULT_TTL: int = 10800


def _get_lock() -> asyncio.Lock:
    """Return the cache lock, creating it lazily on first use."""
    global _cache_lock  # noqa: PLW0603
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()
    return _cache_lock


def _is_cache_valid() -> bool:
    """Check whether the cached digest is still within TTL."""
    if _cache is None:
        return False
    return (time.monotonic() - _cache_timestamp) < _DEFAULT_TTL


def _build_digest_sync() -> FeedDigestResponse:
    """Synchronous: parse OPML, fetch 1 article per feed in parallel."""
    feeds = _parse_opml()
    items: list[FeedDigestItem] = []
    failed: list[str] = []

    executor = ThreadPoolExecutor(max_workers=10)
    future_to_feed = {
        executor.submit(_fetch_single_feed, feed, 1): feed for feed in feeds
    }
    pending_futures = set(future_to_feed)
    try:
        try:
            for future in as_completed(future_to_feed, timeout=45):
                pending_futures.discard(future)
                feed = future_to_feed[future]
                try:
                    articles = future.result(timeout=15)
                    latest = articles[0] if articles else None
                    items.append(
                        FeedDigestItem(
                            feed_name=feed.name,
                            category=feed.category,
                            latest_title=latest.title if latest else None,
                            latest_url=latest.url if latest else None,
                            latest_date=latest.published if latest else None,
                            latest_summary=_clean_summary(latest.summary) if latest and latest.summary else None,
                            new_count=1 if latest else 0,
                        )
                    )
                except Exception:
                    failed.append(feed.name)
                    items.append(
                        FeedDigestItem(
                            feed_name=feed.name,
                            category=feed.category,
                        )
                    )
        except FuturesTimeoutError:
            logger.warning(
                "Feed digest refresh timed out; %d feed task(s) pending",
                len(pending_futures),
            )
    finally:
        for future in pending_futures:
            future.cancel()
            feed = future_to_feed[future]
            failed.append(feed.name)
            items.append(
                FeedDigestItem(
                    feed_name=feed.name,
                    category=feed.category,
                )
            )
        executor.shutdown(wait=True, cancel_futures=True)

    if failed:
        logger.debug("Feed digest: %d feed(s) failed: %s", len(failed), failed)

    # Best-effort batch translation
    _translate_summaries_sync(items)

    feeds_with_updates = sum(1 for it in items if it.latest_title)

    return FeedDigestResponse(
        items=items,
        total_feeds=len(items),
        feeds_with_updates=feeds_with_updates,
        fetched_at=datetime.now(timezone.utc),
        cached=False,
        ttl_seconds=_DEFAULT_TTL,
    )


async def get_feed_digest(
    force_refresh: bool = False,
) -> FeedDigestResponse:
    """Return the feed digest, using cache when valid.

    Fast path: return cached response immediately.
    Slow path: acquire lock, double-check, then fetch in a thread.
    """
    global _cache, _cache_timestamp  # noqa: PLW0603

    # Fast path — no lock needed
    if not force_refresh and _is_cache_valid():
        assert _cache is not None  # mypy: guarded by _is_cache_valid
        return _cache.model_copy(update={"cached": True})

    # Slow path — serialize concurrent refreshes
    async with _get_lock():
        # Double-check after acquiring lock
        if not force_refresh and _is_cache_valid():
            assert _cache is not None
            return _cache.model_copy(update={"cached": True})

        logger.info("Building feed digest (force=%s)", force_refresh)
        digest = await asyncio.to_thread(_build_digest_sync)
        _cache = digest
        _cache_timestamp = time.monotonic()
        return digest


def reset_cache() -> None:
    """Reset the module-level cache (for testing)."""
    global _cache, _cache_timestamp, _cache_lock  # noqa: PLW0603
    _cache = None
    _cache_timestamp = 0.0
    _cache_lock = None
