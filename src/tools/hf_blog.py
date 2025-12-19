"""
Hugging Face Blog Tool

This module provides functionality to fetch Hugging Face blog post listings
and extract title, published date, upvotes, and URL for each post.
"""

from __future__ import annotations

import html as htmllib
import json
import re
import time
from typing import Any, Optional
from urllib.parse import urljoin

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

HF_BASE_URL = "https://huggingface.co"
HF_BLOG_URL = urljoin(HF_BASE_URL, "/blog")


def _extract_blog_props(html_content: str) -> dict[str, Any]:
    """
    Extract the JSON payload embedded in the /blog page.

    The blog page contains an HTML attribute like:
      data-props="...escaped json..."
    We locate the one that includes allBlogs/numTotalItems to ensure we're parsing
    the listing payload rather than unrelated components.
    """
    for raw in re.findall(r'data-props="([^"]*)"', html_content):
        unescaped = htmllib.unescape(raw)
        if '"allBlogs"' in unescaped and '"numTotalItems"' in unescaped:
            return json.loads(unescaped)
    raise ValueError("Could not locate embedded blog listing data (data-props).")


def _normalize_blog_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        title = (item.get("title") or "").strip()
        published_at = (item.get("publishedAt") or "").strip()
        url_path = (item.get("url") or "").strip()
        if not title or not published_at or not url_path:
            continue
        normalized.append(
            {
                "title": title,
                "published_at": published_at,
                "date": published_at[:10],
                "upvotes": int(item.get("upvotes", 0) or 0),
                "upvotes_7d": int(item.get("upvotes7d", 0) or 0),
                "url": urljoin(HF_BASE_URL, url_path),
            }
        )
    return normalized


def fetch_huggingface_blog_posts(
    *,
    page_start: int = 0,
    max_pages: int = 1,
    limit: Optional[int] = 20,
    include_community: bool = False,
    use_upvotes_7d: bool = False,
    sleep_seconds: float = 0.25,
    timeout_seconds: int = 30,
) -> list[dict[str, Any]]:
    """
    Fetch Hugging Face blog post listings from https://huggingface.co/blog.

    Notes:
    - The /blog HTML embeds the listing as escaped JSON in a data-props attribute.
    - Pagination uses the query parameter `p` (0-based page index).

    Args:
        page_start: Starting page index (0-based).
        max_pages: Maximum number of pages to fetch (>=1).
        limit: Maximum number of posts to return (None for unlimited within max_pages).
        include_community: If True, include `communityBlogPosts` items in addition to `allBlogs`.
        use_upvotes_7d: If True, report 7-day upvotes (upvotes7d) as the main `upvotes` value.
        sleep_seconds: Sleep between page fetches to reduce the chance of 429 rate limiting.
        timeout_seconds: HTTP request timeout in seconds.

    Returns:
        List of dictionaries with keys: title, date, published_at, upvotes, url.
    """
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")
    if page_start < 0:
        raise ValueError("page_start must be >= 0")
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0 or None")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
    )

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    def _append(items: list[dict[str, Any]]) -> None:
        nonlocal results
        for entry in _normalize_blog_items(items):
            if entry["url"] in seen_urls:
                continue
            seen_urls.add(entry["url"])
            if use_upvotes_7d:
                entry["upvotes"] = entry.pop("upvotes_7d", entry["upvotes"])
            else:
                entry.pop("upvotes_7d", None)
            results.append(entry)

    for page_index in range(page_start, page_start + max_pages):
        response = session.get(HF_BLOG_URL, params={"p": page_index}, timeout=timeout_seconds)
        response.raise_for_status()

        props = _extract_blog_props(response.text)
        _append(props.get("allBlogs", []))
        if include_community:
            _append(props.get("communityBlogPosts", []))

        if limit is not None and len(results) >= limit:
            return results[:limit]

        if page_index < page_start + max_pages - 1:
            time.sleep(max(0.0, sleep_seconds))

    return results


class HuggingFaceBlogInput(BaseModel):
    """Input schema for Hugging Face blog posts listing."""

    limit: Optional[int] = Field(
        default=20,
        ge=1,
        description="Maximum number of posts to return. Use None to return all posts within fetched pages.",
    )
    page_start: int = Field(
        default=0,
        ge=0,
        description="Starting page index (0-based)",
    )
    max_pages: int = Field(
        default=1,
        ge=1,
        description="Maximum number of pages to fetch (each page is ~14 items)",
    )
    include_community: bool = Field(
        default=False,
        description="Also include community blog posts listed on /blog",
    )
    use_upvotes_7d: bool = Field(
        default=False,
        description="Use 7-day upvotes instead of total upvotes",
    )


@tool(args_schema=HuggingFaceBlogInput)
def get_huggingface_blog_posts_tool(
    limit: Optional[int] = 20,
    page_start: int = 0,
    max_pages: int = 1,
    include_community: bool = False,
    use_upvotes_7d: bool = False,
) -> str:
    """
    Get Hugging Face blog post listings with title/date/upvotes/url.

    Use this tool when you need a list of Hugging Face blog posts and their
    basic metadata (title, publish date, upvotes, URL).
    """
    try:
        posts = fetch_huggingface_blog_posts(
            page_start=page_start,
            max_pages=max_pages,
            limit=limit,
            include_community=include_community,
            use_upvotes_7d=use_upvotes_7d,
        )

        if not posts:
            return "No blog posts found."

        upvote_label = "Upvotes (7d)" if use_upvotes_7d else "Upvotes"
        result_parts = ["## Hugging Face Blog Posts\n"]
        result_parts.append(f"**Returned:** {len(posts)} posts")
        result_parts.append(
            f"**Pages:** {page_start} .. {page_start + max_pages - 1} | **Per page:** ~14"
        )
        if include_community:
            result_parts.append("**Includes:** official + community")
        else:
            result_parts.append("**Includes:** official")

        for i, post in enumerate(posts, 1):
            result_parts.append(f"\n### {i}. {post['title']}")
            result_parts.append(f"**Date:** {post.get('date', '')}")
            result_parts.append(f"**{upvote_label}:** {post.get('upvotes', 0)}")
            result_parts.append(f"**URL:** {post.get('url', '')}")

        return "\n".join(result_parts)

    except ValueError as e:
        return f"Error: {str(e)}"
    except requests.RequestException as e:
        return f"Error fetching Hugging Face blog posts: Network error - {str(e)}"
    except json.JSONDecodeError as e:
        return f"Error parsing Hugging Face blog listing data: {str(e)}"
    except Exception as e:
        return f"Error fetching Hugging Face blog posts: Unexpected error - {str(e)}"
