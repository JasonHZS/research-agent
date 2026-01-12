"""
Tavily Web Search Tool

This module provides functionality to perform web searches
using the Tavily Search API. This is a fallback search tool
that should be used when other general search tools cannot find
relevant content.

API Documentation: https://docs.tavily.com/documentation/api-reference/endpoint/search
"""

import os
from typing import Any, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel
from tavily import TavilyClient


# Type definitions
SearchDepth = Literal["basic", "advanced"]
SearchTopic = Literal["general", "news", "finance"]


class TavilySearchResult(BaseModel):
    """A single Tavily search result."""

    title: str
    url: str
    content: str
    score: float
    favicon: Optional[str] = None


class TavilySearchResponse(BaseModel):
    """Complete Tavily search response."""

    query: str
    answer: Optional[str] = None
    results: list[TavilySearchResult]
    response_time: float


def _get_tavily_client(api_key: Optional[str] = None) -> TavilyClient:
    """Get Tavily client with API key from parameter or environment."""
    tavily_api_key = api_key or os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        raise ValueError(
            "TAVILY_API_KEY is required. Set it in .env file or pass as parameter."
        )
    return TavilyClient(api_key=tavily_api_key)


def search_tavily(
    query: str,
    search_depth: SearchDepth = "basic",
    max_results: int = 5,
    topic: SearchTopic = "general",
    api_key: Optional[str] = None,
) -> TavilySearchResponse:
    """
    Perform a web search using Tavily Search API.

    Args:
        query: The search query string.
        search_depth: Controls latency vs relevance tradeoff.
            - 'basic': Balanced option for relevance and latency (1 credit)
            - 'advanced': Highest relevance with increased latency (2 credits)
        max_results: Maximum number of results to return (default: 5, max: 20).
        topic: Category of the search.
            - 'general': Broader, general-purpose searches
            - 'news': Real-time updates, politics, sports, current events
            - 'finance': Financial data, stock information, earnings reports
        api_key: Tavily API key. If not provided, will try to get from environment.

    Returns:
        TavilySearchResponse containing query, answer (if available), and results.

    Raises:
        ValueError: If API key is not provided.
    """
    client = _get_tavily_client(api_key)

    response: dict[str, Any] = client.search(
        query=query,
        search_depth=search_depth,
        max_results=max_results,
        topic=topic,
    )

    # Parse results
    results = []
    for item in response.get("results", []):
        results.append(
            TavilySearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=item.get("score", 0.0),
                favicon=item.get("favicon"),
            )
        )

    return TavilySearchResponse(
        query=response.get("query", query),
        answer=response.get("answer"),
        results=results,
        response_time=float(response.get("response_time", 0)),
    )


def format_tavily_results_as_markdown(response: TavilySearchResponse) -> str:
    """
    Format Tavily search results as markdown.

    Args:
        response: TavilySearchResponse object.

    Returns:
        Formatted markdown string.
    """
    if not response.results:
        return "No search results found."

    parts = [f"# Tavily Search Results ({len(response.results)} results)\n"]

    # Include AI-generated answer if available
    if response.answer:
        parts.append(f"## Summary\n{response.answer}\n")

    for i, result in enumerate(response.results, 1):
        result_parts = [f"## {i}. {result.title}"]

        # URL
        if result.url:
            result_parts.append(f"**URL:** {result.url}")

        # Relevance score
        if result.score:
            result_parts.append(f"**Relevance:** {result.score:.2f}")

        # Content
        if result.content:
            result_parts.append(f"\n{result.content}")

        parts.append("\n".join(result_parts))

    return "\n\n---\n\n".join(parts)


@tool
def tavily_search_tool(
    query: str,
    search_depth: SearchDepth = "basic",
    max_results: int = 5,
    topic: SearchTopic = "general",
) -> str:
    """
    Perform a web search using Tavily Search API (fallback search tool).

    IMPORTANT: This tool should be used as a FALLBACK when other general search
    tools (e.g., Bocha Search) cannot find relevant content. It provides high-quality
    search results optimized for AI research and specialized domains.

    Args:
        query: The search query string. Be specific for better results.
        search_depth: Controls search quality vs latency.
            - 'basic': Balanced option, good for most queries (default)
            - 'advanced': Higher relevance, use for complex research questions
        max_results: Number of results to return (1-20, default: 5).
        topic: Category of search, choose based on query context.
            - 'general': Default, for AI research, technology, general topics
            - 'news': Real-time updates, politics, sports, breaking news, current events
            - 'finance': Stock prices, earnings reports, financial analysis, market data

    Returns:
        Markdown-formatted list of search results with title, URL, relevance score,
        and content summary.

    Example topic selection:
        - AI/ML research, technical papers -> 'general'
        - Stock prices, company earnings, market analysis -> 'finance'
        - Breaking news, current events, sports updates -> 'news'
    """
    # Clamp max_results to valid range
    max_results = max(1, min(max_results, 20))

    try:
        response = search_tavily(
            query,
            search_depth=search_depth,
            max_results=max_results,
            topic=topic,
        )
        return format_tavily_results_as_markdown(response)

    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        error_msg = str(e).lower()
        if "invalid api key" in error_msg or "unauthorized" in error_msg:
            return "Error: Invalid TAVILY_API_KEY. Please check your API key."
        elif "rate limit" in error_msg:
            return "Error: Rate limit exceeded. Please try again later."
        return f"Error performing Tavily search: {str(e)}"


# For direct testing
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    # Test general search
    print("=== Testing General Search ===")
    result = tavily_search_tool.invoke({
        "query": "LangChain AI agent framework",
        "topic": "general",
        "max_results": 3,
    })
    print(result)

    print("\n\n=== Testing Finance Search ===")
    result = tavily_search_tool.invoke({
        "query": "NVIDIA stock earnings Q4 2025",
        "topic": "finance",
        "max_results": 3,
    })
    print(result)
