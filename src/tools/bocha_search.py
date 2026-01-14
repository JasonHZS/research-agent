"""
Bocha Web Search Tool

This module provides functionality to perform web searches
using the Bocha AI Web Search API.

API Documentation: https://open.bocha.cn
"""

import os
from typing import Optional

import requests
from langchain_core.tools import tool
from pydantic import BaseModel


class SearchResult(BaseModel):
    """A single web search result."""

    name: str
    url: str
    summary: str
    date_published: Optional[str] = None


def _get_bocha_api_key(api_key: Optional[str] = None) -> str:
    """Get Bocha API key from parameter or environment."""
    bocha_api_key = api_key or os.getenv("BOCHA_API_KEY")
    if not bocha_api_key:
        raise ValueError(
            "BOCHA_API_KEY is required. Set it in .env file or pass as parameter."
        )
    return bocha_api_key


def search_web(
    query: str,
    count: int = 10,
    summary: bool = True,
    api_key: Optional[str] = None,
) -> list[SearchResult]:
    """
    Perform a web search using Bocha AI Web Search API.

    Args:
        query: The search query string.
        count: Number of results to return (default: 10).
        summary: Whether to include AI summary (default: True).
        api_key: Bocha API key. If not provided, will try to get from environment.

    Returns:
        A list of SearchResult objects.

    Raises:
        ValueError: If API key is not provided.
        requests.RequestException: If the API request fails.
    """
    bocha_api_key = _get_bocha_api_key(api_key)

    url = "https://api.bocha.cn/v1/web-search"
    headers = {
        "Authorization": f"Bearer {bocha_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "count": count,
        "summary": summary,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    data = response.json()

    # Check for API errors
    if data.get("code") != 200:
        raise ValueError(f"Bocha API error: {data.get('msg', 'Unknown error')}")

    # Extract web pages from response
    web_pages = data.get("data", {}).get("webPages", {}).get("value", [])

    results = []
    for page in web_pages:
        results.append(
            SearchResult(
                name=page.get("name", ""),
                url=page.get("displayUrl", page.get("url", "")),
                summary=page.get("summary", page.get("snippet", "")),
                date_published=page.get("datePublished", page.get("dateLastCrawled")),
            )
        )

    return results


def format_search_results_as_markdown(results: list[SearchResult]) -> str:
    """
    Format search results as markdown.

    Args:
        results: List of SearchResult objects.

    Returns:
        Formatted markdown string.
    """
    if not results:
        return "No search results found."

    parts = [f"# Web Search Results ({len(results)} results)\n"]

    for i, result in enumerate(results, 1):
        result_parts = [f"## {i}. {result.name}"]

        # URL
        if result.url:
            result_parts.append(f"**URL:** {result.url}")

        # Date published
        if result.date_published:
            # Format: 2024-07-22T00:00:00Z -> 2024-07-22
            date_str = result.date_published.split("T")[0] if "T" in result.date_published else result.date_published
            result_parts.append(f"**Date:** {date_str}")

        # Summary
        if result.summary:
            result_parts.append(f"\n{result.summary}")

        parts.append("\n".join(result_parts))

    return "\n\n---\n\n".join(parts)


def _handle_request_error(e: requests.RequestException, query: str) -> str:
    """Handle request exceptions and return user-friendly error messages."""
    if hasattr(e, "response") and e.response is not None:
        status_code = e.response.status_code
        if status_code == 401:
            return "Error: Invalid BOCHA_API_KEY. Please check your API key."
        elif status_code == 403:
            return "Error: Access forbidden. Your API key may not have access to this feature."
        elif status_code == 429:
            return "Error: Rate limit exceeded. Please try again later."
        return f"Error searching for '{query}': HTTP {status_code} - {e.response.text}"
    return f"Error searching for '{query}': Network error - {str(e)}"


@tool
def bocha_web_search_tool(query: str, count: int = 10) -> str:
    """
    Perform a general web search using the Bocha Search API.

    This tool searches the web and returns relevant results including titles, URLs,
    publication dates, and content summaries.

    Args:
        query: The search query string. Be specific for better results.
        count: Number of results to return (1-20, default: 5).

    Returns:
        Markdown-formatted list of search results with title, URL, date, and summary.
    """
    # Clamp count to valid range
    count = max(1, min(count, 20))

    try:
        results = search_web(query, count=count)
        return format_search_results_as_markdown(results)

    except ValueError as e:
        return f"Error: {str(e)}"
    except requests.RequestException as e:
        return _handle_request_error(e, query)
    except Exception as e:
        return f"Error performing web search: Unexpected error - {str(e)}"


# For direct testing
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    result = bocha_web_search_tool.invoke({"query": "LangChain AI agent", "count": 5})
    print(result)

