"""
RSS Feeds Tool

Provides tools to list available RSS feeds from a curated OPML file
and fetch recent articles from those feeds.
"""

import difflib
import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import feedparser
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# 全局文章数上限，防止撑爆 Agent 上下文窗口
_MAX_ARTICLES = 100


@dataclass
class FeedInfo:
    """Metadata for a single RSS feed."""

    name: str
    xml_url: str
    html_url: str
    category: str = "Blogs"


@dataclass
class FeedArticle:
    """A single article from an RSS feed."""

    title: str
    url: str
    published: Optional[str] = None
    summary: str = ""
    feed_name: str = ""


# Module-level cache for parsed feeds，以解析路径为 key，避免不同路径互相污染
_feeds_cache: dict[Path, list[FeedInfo]] = {}

_OPML_PATH = Path(__file__).parent.parent / "config" / "hn-popular-blogs-2025.opml"


def _parse_opml(path: Path | None = None) -> list[FeedInfo]:
    """Parse an OPML file and return a list of FeedInfo objects.

    Supports both nested (categorized) and flat OPML structures.
    Results are cached per path after first call.
    """
    opml_path = path or _OPML_PATH
    if opml_path in _feeds_cache:
        return _feeds_cache[opml_path]

    if not opml_path.exists():
        raise FileNotFoundError(f"OPML file not found: {opml_path}")

    tree = ET.parse(opml_path)  # noqa: S314
    root = tree.getroot()
    body = root.find("body")
    if body is None:
        return []

    feeds: list[FeedInfo] = []
    _walk_outlines(body, "Blogs", feeds)
    _feeds_cache[opml_path] = feeds
    return feeds


def _walk_outlines(element: ET.Element, category: str, feeds: list[FeedInfo]) -> None:
    """Recursively walk OPML outlines, collecting feed entries."""
    for outline in element.findall("outline"):
        xml_url = outline.get("xmlUrl")
        if xml_url:
            feeds.append(
                FeedInfo(
                    name=outline.get("text", outline.get("title", "")),
                    xml_url=xml_url,
                    html_url=outline.get("htmlUrl", ""),
                    category=category,
                )
            )
        else:
            # This is a category node — recurse with its title
            sub_category = outline.get("text", outline.get("title", category))
            _walk_outlines(outline, sub_category, feeds)


def _match_feed(query: str, feeds: list[FeedInfo]) -> list[FeedInfo]:
    """Find feeds matching a query string via substring or fuzzy match."""
    query_lower = query.lower()

    # Exact substring match first
    exact = [f for f in feeds if query_lower in f.name.lower()]
    if exact:
        return exact

    # Fuzzy match
    names = [f.name.lower() for f in feeds]
    close = difflib.get_close_matches(query_lower, names, n=5, cutoff=0.4)
    return [f for f in feeds if f.name.lower() in close]


def _fetch_single_feed(feed: FeedInfo, limit: int) -> list[FeedArticle]:
    """Fetch articles from a single RSS feed with timeout."""
    try:
        parsed = feedparser.parse(feed.xml_url, request_headers={"User-Agent": "ResearchAgent/1.0"})
        if parsed.bozo and not parsed.entries:
            return []

        articles: list[FeedArticle] = []
        for entry in parsed.entries[:limit]:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M")
                except (TypeError, ValueError):
                    pass
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                try:
                    published = datetime(*entry.updated_parsed[:6]).strftime("%Y-%m-%d %H:%M")
                except (TypeError, ValueError):
                    pass

            summary = entry.get("summary", "")
            if len(summary) > 300:
                summary = summary[:300] + "..."

            articles.append(
                FeedArticle(
                    title=entry.get("title", "Untitled"),
                    url=entry.get("link", ""),
                    published=published,
                    summary=summary,
                    feed_name=feed.name,
                )
            )
        return articles
    except Exception as exc:
        logger.debug("Failed to fetch feed %s: %s", feed.xml_url, exc)
        return []


@tool
def list_rss_feeds_tool(category: Optional[str] = None) -> str:
    """List all available RSS feeds from the curated HN popular blogs collection.

    Returns feed names grouped by category with their website URLs.
    Use this to discover which blogs/feeds are available before fetching articles.

    Args:
        category: Optional category name to filter feeds. If not provided, lists all feeds.

    Returns:
        Formatted string listing all available feeds grouped by category.
    """
    try:
        feeds = _parse_opml()
    except FileNotFoundError as e:
        return f"Error: {e}"

    if not feeds:
        return "No feeds found in the OPML file."

    if category:
        cat_lower = category.lower()
        feeds = [f for f in feeds if cat_lower in f.category.lower()]
        if not feeds:
            all_cats = sorted({f.category for f in _parse_opml()})
            return (
                f"No feeds found in category '{category}'. "
                f"Available categories: {', '.join(all_cats)}"
            )

    # Group by category
    grouped: dict[str, list[FeedInfo]] = {}
    for f in feeds:
        grouped.setdefault(f.category, []).append(f)

    parts = [f"## Available RSS Feeds ({len(feeds)} total)\n"]
    for cat, cat_feeds in sorted(grouped.items()):
        parts.append(f"\n### {cat} ({len(cat_feeds)} feeds)\n")
        for f in sorted(cat_feeds, key=lambda x: x.name.lower()):
            parts.append(f"- **{f.name}** — {f.html_url}")

    return "\n".join(parts)


@tool
def fetch_rss_articles_tool(
    feed_name: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 5,
) -> str:
    """Fetch recent articles from RSS feeds in the curated HN popular blogs collection.

    Can fetch articles from a specific feed (by name), all feeds in a category,
    or a sample from the first 20 feeds if neither is specified.

    Args:
        feed_name: Name of a specific feed to fetch (fuzzy matching supported).
                   Example: "simonwillison" will match "simonwillison.net".
        category: Fetch articles from all feeds in this category.
        limit: Maximum number of articles per feed (default 5, max 20).
               When fetching multiple feeds, total output is capped at 100 articles.

    Returns:
        Formatted string with recent articles including title, URL, date, and summary.
    """
    try:
        all_feeds = _parse_opml()
    except FileNotFoundError as e:
        return f"Error: {e}"

    if not all_feeds:
        return "No feeds found in the OPML file."

    limit = min(max(limit, 1), 20)

    # Determine which feeds to fetch
    if feed_name:
        targets = _match_feed(feed_name, all_feeds)
        if not targets:
            # Suggest closest matches
            names = [f.name for f in all_feeds]
            suggestions = difflib.get_close_matches(
                feed_name.lower(), [n.lower() for n in names], n=5, cutoff=0.3
            )
            actual = [n for n in names if n.lower() in suggestions]
            hint = f" Did you mean: {', '.join(actual)}?" if actual else ""
            return f"No feed matching '{feed_name}'.{hint}"
    elif category:
        cat_lower = category.lower()
        targets = [f for f in all_feeds if cat_lower in f.category.lower()]
        if not targets:
            return f"No feeds found in category '{category}'."
    else:
        targets = all_feeds[:20]

    # Fetch in parallel
    all_articles: list[FeedArticle] = []
    failed: list[str] = []

    # Hard global timeout: stop waiting after 30s even if background workers are still blocked.
    executor = ThreadPoolExecutor(max_workers=5)
    future_to_feed: dict[Future[list[FeedArticle]], FeedInfo] = {}
    try:
        future_to_feed = {executor.submit(_fetch_single_feed, f, limit): f for f in targets}
        try:
            for future in as_completed(future_to_feed, timeout=30):
                feed = future_to_feed[future]
                try:
                    articles = future.result(timeout=15)
                    all_articles.extend(articles)
                except Exception as exc:
                    logger.debug("Feed %s raised an error: %s", feed.name, exc)
                    failed.append(feed.name)
        except FuturesTimeoutError:
            pending = [f.name for fut, f in future_to_feed.items() if not fut.done()]
            failed.extend(pending)
            logger.debug("RSS fetch timed out; %d feed(s) did not complete: %s", len(pending), pending)
    finally:
        # Do not block here; we already enforced the deadline above.
        executor.shutdown(wait=False, cancel_futures=True)

    if not all_articles:
        return (
            f"No articles retrieved from {len(targets)} feed(s). "
            "They may be temporarily unavailable."
        )

    # Sort by date descending (entries without dates go last)
    all_articles.sort(key=lambda a: a.published or "", reverse=True)

    # 全局上限，防止撑爆 Agent 上下文窗口
    output_articles = all_articles[:_MAX_ARTICLES]

    # Format output
    parts = [f"## RSS Articles ({len(output_articles)} from {len(targets)} feed(s))\n"]

    for i, article in enumerate(output_articles, 1):
        parts.append(f"\n### {i}. {article.title}")
        parts.append(f"**Feed:** {article.feed_name}")
        if article.published:
            parts.append(f"**Date:** {article.published}")
        if article.url:
            parts.append(f"**URL:** {article.url}")
        if article.summary:
            clean = re.sub(r"<[^>]+>", "", article.summary).strip()
            if clean:
                parts.append(f"**Summary:** {clean}")
        parts.append("")

    if failed:
        parts.append(f"\n_Note: {len(failed)} feed(s) failed to load: {', '.join(failed)}_")

    return "\n".join(parts)
