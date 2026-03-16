"""Native Hacker News API tools using httpx.

Replaces the MCP-based HN tools with direct Firebase API calls.
No Node.js dependency, better proxy support, simpler architecture.
"""

import asyncio
from typing import Any

import httpx
from langchain_core.tools import ToolException, tool

# HN Firebase API base URL
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"

# HTTP client configuration
TIMEOUT = httpx.Timeout(connect=10.0, read=15.0, write=5.0, pool=10.0)
DEFAULT_LIMIT = 10
MAX_LIMIT = 30


class HNToolError(ToolException):
    """Recoverable Hacker News tool error surfaced to ToolNode."""

    def __repr__(self) -> str:
        return str(self)


def _raise_hn_tool_error(action: str, exc: Exception) -> None:
    """Convert transport/parsing failures into a recoverable tool error."""
    raise HNToolError(f"Hacker News API request failed while {action}: {exc}") from exc


async def _fetch_json(client: httpx.AsyncClient, path: str, action: str) -> Any:
    """Fetch and decode JSON from the HN Firebase API."""
    try:
        response = await client.get(f"{HN_API_BASE}/{path}.json")
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        _raise_hn_tool_error(action, exc)


async def _fetch_item(client: httpx.AsyncClient, item_id: int) -> dict[str, Any] | None:
    """Fetch a single HN item by ID."""
    item = await _fetch_json(client, f"item/{item_id}", f"fetching item {item_id}")
    if item is None:
        return None
    if not isinstance(item, dict):
        raise HNToolError(
            f"Unexpected Hacker News API response while fetching item {item_id}."
        )
    return item


async def _fetch_items_batch(item_ids: list[int], limit: int) -> list[dict[str, Any]]:
    """Fetch multiple HN items concurrently."""
    capped = min(limit, MAX_LIMIT)
    ids = item_ids[:capped]
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        tasks = [_fetch_item(client, item_id) for item_id in ids]
        results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


async def _fetch_story_ids(endpoint: str) -> list[int]:
    """Fetch story IDs from an HN endpoint."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        story_ids = await _fetch_json(client, endpoint, f"fetching {endpoint}")
    if not isinstance(story_ids, list):
        raise HNToolError(
            f"Unexpected Hacker News API response while fetching {endpoint}."
        )
    return story_ids


def _format_story(item: dict[str, Any]) -> str:
    """Format a single story item for display."""
    title = item.get("title", "No title")
    url = item.get("url", "")
    score = item.get("score", 0)
    by = item.get("by", "unknown")
    item_id = item.get("id", "")
    descendants = item.get("descendants", 0)
    url_line = f"\n  URL: {url}" if url else ""
    return (
        f"- [{title}](https://news.ycombinator.com/item?id={item_id}){url_line}\n"
        f"  Score: {score} | By: {by} | Comments: {descendants}"
    )


def _format_stories(items: list[dict[str, Any]], category: str) -> str:
    """Format a list of stories."""
    if not items:
        return f"No {category} stories found."
    stories = "\n".join(_format_story(item) for item in items)
    return f"## {category} ({len(items)} stories)\n\n{stories}"


async def _get_stories(endpoint: str, category: str, limit: int) -> str:
    """Generic story fetcher."""
    capped = min(max(1, limit), MAX_LIMIT)
    ids = await _fetch_story_ids(endpoint)
    items = await _fetch_items_batch(ids, capped)
    return _format_stories(items, category)


@tool
async def get_hn_top_stories(limit: int = DEFAULT_LIMIT) -> str:
    """Get top stories from Hacker News.

    Args:
        limit: Number of stories to return (1-30, default 10).
    """
    return await _get_stories("topstories", "Top Stories", limit)


@tool
async def get_hn_best_stories(limit: int = DEFAULT_LIMIT) -> str:
    """Get best stories from Hacker News (highest-voted recent stories).

    Args:
        limit: Number of stories to return (1-30, default 10).
    """
    return await _get_stories("beststories", "Best Stories", limit)


@tool
async def get_hn_new_stories(limit: int = DEFAULT_LIMIT) -> str:
    """Get newest stories from Hacker News.

    Args:
        limit: Number of stories to return (1-30, default 10).
    """
    return await _get_stories("newstories", "New Stories", limit)


@tool
async def get_hn_ask_stories(limit: int = DEFAULT_LIMIT) -> str:
    """Get Ask HN stories (community questions and discussions).

    Args:
        limit: Number of stories to return (1-30, default 10).
    """
    return await _get_stories("askstories", "Ask HN", limit)


@tool
async def get_hn_show_stories(limit: int = DEFAULT_LIMIT) -> str:
    """Get Show HN stories (community project showcases).

    Args:
        limit: Number of stories to return (1-30, default 10).
    """
    return await _get_stories("showstories", "Show HN", limit)


@tool
async def get_hn_job_stories(limit: int = DEFAULT_LIMIT) -> str:
    """Get job postings from Hacker News (YC-backed companies hiring).

    Useful for understanding real hiring demand in the US tech market,
    what roles companies actually need, and which technologies are in demand.

    Args:
        limit: Number of job posts to return (1-30, default 10).
    """
    return await _get_stories("jobstories", "Job Stories", limit)


@tool
async def get_hn_user(username: str) -> str:
    """Get a Hacker News user profile.

    Args:
        username: The HN username (case-sensitive).
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        user = await _fetch_json(client, f"user/{username}", f"fetching user {username}")

    if not user:
        return f"User '{username}' not found."
    if not isinstance(user, dict):
        raise HNToolError(
            f"Unexpected Hacker News API response while fetching user {username}."
        )

    uid = user.get("id", username)
    created = user.get("created", "")
    karma = user.get("karma", 0)
    about = user.get("about", "")
    submitted = user.get("submitted", [])

    parts = [
        f"## HN User: {uid}",
        f"Karma: {karma}",
        f"Created: {created}",
    ]
    if about:
        parts.append(f"About: {about}")
    parts.append(f"Submissions: {len(submitted)}")
    return "\n".join(parts)


@tool
async def get_hn_max_item_id() -> str:
    """Get the current largest item ID on Hacker News.

    Useful for polling: any item with an ID greater than this is new.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        max_id = await _fetch_json(client, "maxitem", "fetching max item ID")
    return f"Current max HN item ID: {max_id}"


@tool
async def get_hn_updates() -> str:
    """Get recently changed items and profiles on Hacker News.

    Returns the latest updated item IDs and user profiles,
    useful for tracking real-time activity.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        data = await _fetch_json(client, "updates", "fetching recent updates")
    if not isinstance(data, dict):
        raise HNToolError(
            "Unexpected Hacker News API response while fetching recent updates."
        )

    items = data.get("items", [])
    profiles = data.get("profiles", [])

    parts = [
        "## HN Recent Updates",
        f"Changed items ({len(items)}): {items[:20]}",
        f"Changed profiles ({len(profiles)}): {profiles[:20]}",
    ]
    return "\n".join(parts)


@tool
async def get_hn_item(item_id: int) -> str:
    """Get details of a specific Hacker News item (story, comment, poll, etc).

    Args:
        item_id: The HN item ID.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        item = await _fetch_item(client, item_id)
    if not item:
        return f"Item {item_id} not found."

    item_type = item.get("type", "unknown")
    title = item.get("title", "")
    text = item.get("text", "")
    url = item.get("url", "")
    by = item.get("by", "unknown")
    score = item.get("score", "")
    kids = item.get("kids", [])

    parts = [f"## HN Item {item_id} ({item_type})"]
    if title:
        parts.append(f"Title: {title}")
    if url:
        parts.append(f"URL: {url}")
    parts.append(f"By: {by}")
    if score:
        parts.append(f"Score: {score}")
    if text:
        parts.append(f"\n{text}")
    if kids:
        parts.append(f"\n{len(kids)} replies")
    return "\n".join(parts)


@tool
async def get_hn_comments(item_id: int, limit: int = 10) -> str:
    """Get comments for a Hacker News item.

    Args:
        item_id: The HN item ID to get comments for.
        limit: Max number of top-level comments to fetch (1-30, default 10).
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        parent = await _fetch_item(client, item_id)
    if not parent:
        return f"Item {item_id} not found."

    kids = parent.get("kids", [])
    if not kids:
        return f"No comments on item {item_id}."

    capped = min(max(1, limit), MAX_LIMIT)
    comments = await _fetch_items_batch(kids, capped)

    parts = [f"## Comments on item {item_id} ({len(comments)}/{len(kids)} shown)\n"]
    for c in comments:
        by = c.get("by", "unknown")
        text = c.get("text", "(no text)")
        parts.append(f"**{by}**:\n{text}\n")
    return "\n".join(parts)


# All HN tools for easy import
hn_tools = [
    get_hn_top_stories,
    get_hn_best_stories,
    get_hn_new_stories,
    get_hn_ask_stories,
    get_hn_show_stories,
    get_hn_job_stories,
    get_hn_item,
    get_hn_comments,
    get_hn_user,
    get_hn_max_item_id,
    get_hn_updates,
]
