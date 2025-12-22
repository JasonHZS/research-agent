"""
Zyte API Reader Tool

This module provides functionality to fetch article content from URLs
using the Zyte Web Data Extraction API.

API Documentation: https://docs.zyte.com/zyte-api/usage/reference.html
"""

import os
from typing import Optional

import requests
from langchain_core.tools import tool


def _get_zyte_api_key(api_key: Optional[str] = None) -> str:
    """Get Zyte API key from parameter or environment."""
    zyte_api_key = api_key or os.getenv("ZYTE_API_KEY")
    if not zyte_api_key:
        raise ValueError(
            "ZYTE_API_KEY is required. Set it in .env file or pass as parameter."
        )
    return zyte_api_key


def fetch_article_content(url: str, api_key: Optional[str] = None) -> dict:
    """
    Fetch article content from a URL using Zyte API.

    Args:
        url: The URL to fetch content from.
        api_key: Zyte API key. If not provided, will try to get from environment.

    Returns:
        A dictionary containing the extracted article data.

    Raises:
        ValueError: If API key is not provided.
        requests.RequestException: If the API request fails.
    """
    zyte_api_key = _get_zyte_api_key(api_key)

    response = requests.post(
        "https://api.zyte.com/v1/extract",
        auth=(zyte_api_key, ""),
        json={
            "url": url,
            "article": True,
            "articleOptions": {"extractFrom": "httpResponseBody"},
            "followRedirect": True,
        },
        timeout=120,
    )
    response.raise_for_status()

    return response.json()


def fetch_article_list(url: str, api_key: Optional[str] = None) -> dict:
    """
    Fetch article list from a website using Zyte API.

    Args:
        url: The URL of the website to fetch article list from (e.g., blog homepage).
        api_key: Zyte API key. If not provided, will try to get from environment.

    Returns:
        A dictionary containing the extracted article list data.

    Raises:
        ValueError: If API key is not provided.
        requests.RequestException: If the API request fails.
    """
    zyte_api_key = _get_zyte_api_key(api_key)

    response = requests.post(
        "https://api.zyte.com/v1/extract",
        auth=(zyte_api_key, ""),
        json={
            "url": url,
            "articleList": True,
            "articleListOptions": {"extractFrom": "httpResponseBody"},
            "followRedirect": True,
        },
        timeout=120,
    )
    response.raise_for_status()

    return response.json()


def _sort_articles_by_date(articles: list) -> list:
    """
    Sort articles by datePublished in descending order (newest first).
    
    Args:
        articles: List of article dictionaries.
        
    Returns:
        Sorted list of articles.
    """
    def get_date_key(article):
        if not isinstance(article, dict):
            return ""
        # Try datePublished first, fallback to datePublishedRaw
        return article.get("datePublished") or article.get("datePublishedRaw") or ""
    
    return sorted(articles, key=get_date_key, reverse=True)


def format_article_list_as_markdown(articles: list) -> str:
    """
    Format extracted article list data as markdown.

    Args:
        articles: The article list from Zyte API.

    Returns:
        Formatted markdown string with articles sorted by date (newest first).
    """
    if not articles:
        return "No articles found."

    # Ensure we have a list and sort by date (newest first)
    articles = _sort_articles_by_date(list(articles))

    parts = [f"# Article List ({len(articles)} articles)\n"]

    for i, article in enumerate(articles, 1):
        # Skip non-dict items
        if not isinstance(article, dict):
            parts.append(f"## {i}. {str(article)}")
            continue

        article_parts = [f"## {i}. {article.get('headline', 'Untitled')}"]

        # URL
        if article_url := article.get("url"):
            article_parts.append(f"**URL:** {article_url}")

        # Date published
        if date_published := article.get("datePublished"):
            article_parts.append(f"**Published:** {date_published}")
        elif date_raw := article.get("datePublishedRaw"):
            article_parts.append(f"**Date:** {date_raw}")

        # Language
        if language := article.get("inLanguage"):
            article_parts.append(f"**Language:** {language}")

        # Article body / description
        if article_body := article.get("articleBody"):
            # Truncate long content for list view
            preview = article_body[:300] + "..." if len(article_body) > 300 else article_body
            article_parts.append(f"\n{preview}")

        parts.append("\n".join(article_parts))

    return "\n\n---\n\n".join(parts)


def format_article_as_markdown(article: dict) -> str:
    """
    Format extracted article data as markdown.

    Args:
        article: The article data from Zyte API.

    Returns:
        Formatted markdown string.
    """
    parts = []

    # Title
    if headline := article.get("headline"):
        parts.append(f"# {headline}\n")

    # Metadata
    metadata_items = []
    if authors := article.get("authors"):
        author_names = [a.get("name", "") for a in authors if a.get("name")]
        if author_names:
            metadata_items.append(f"**Authors:** {', '.join(author_names)}")

    if date_published := article.get("datePublished"):
        metadata_items.append(f"**Published:** {date_published}")

    if date_modified := article.get("dateModified"):
        metadata_items.append(f"**Modified:** {date_modified}")

    if metadata_items:
        parts.append("\n".join(metadata_items) + "\n")

    # Description/Summary
    if description := article.get("description"):
        parts.append(f"> {description}\n")

    # Main content
    if article_body := article.get("articleBody"):
        parts.append(article_body)
    elif article_body_html := article.get("articleBodyHtml"):
        # Fallback to HTML if plain text not available
        parts.append(f"[HTML Content]\n{article_body_html}")

    # Source URL
    if canonical_url := article.get("canonicalUrl"):
        parts.append(f"\n---\n**Source:** {canonical_url}")
    elif url := article.get("url"):
        parts.append(f"\n---\n**Source:** {url}")

    return "\n\n".join(parts)


def _handle_request_error(e: requests.RequestException, url: str) -> str:
    """Handle request exceptions and return user-friendly error messages."""
    if hasattr(e, "response") and e.response is not None:
        status_code = e.response.status_code
        if status_code == 401:
            return "Error: Invalid ZYTE_API_KEY. Please check your API key."
        elif status_code == 403:
            return "Error: Access forbidden. Your API key may not have access to this feature."
        elif status_code == 422:
            return f"Error: Invalid request - {e.response.text}"
        elif status_code == 429:
            return "Error: Rate limit exceeded. Please try again later."
        elif status_code == 520:
            return f"Error: Failed to extract content from {url}. The website may be blocking extraction."
        return f"Error fetching URL content: HTTP {status_code} - {e.response.text}"
    return f"Error fetching URL content: Network error - {str(e)}"


@tool
def get_zyte_reader_tool(url: str) -> str:
    """
    Fetch and extract article content from a URL using Zyte API.

    Use this tool to extract clean, structured article content from web pages.
    It's particularly effective for news articles, blog posts, and other
    article-style content. Returns the content formatted as markdown.

    Args:
        url: The URL of the web page to fetch article content from.

    Returns:
        The extracted article content formatted as markdown text,
        including title, authors, publish date, and body text.
    """
    try:
        result = fetch_article_content(url)

        if "article" not in result:
            return f"Error: No article content found at {url}. The page may not contain article-style content."

        article = result["article"]
        return format_article_as_markdown(article)

    except ValueError as e:
        return f"Error: {str(e)}"
    except requests.RequestException as e:
        return _handle_request_error(e, url)
    except Exception as e:
        return f"Error fetching URL content: Unexpected error - {str(e)}"


def _extract_articles_from_response(article_list_data) -> list:
    """
    Extract articles list from Zyte API articleList response.
    
    The API may return articles in different structures:
    - Direct list of articles
    - Dict with "articles" key containing the list
    """
    if isinstance(article_list_data, list):
        return article_list_data
    elif isinstance(article_list_data, dict):
        # Try common keys that might contain the articles list
        for key in ["articles", "items", "data"]:
            if key in article_list_data and isinstance(article_list_data[key], list):
                return article_list_data[key]
        # If no known key found, return empty list
        return []
    return []


@tool
def get_zyte_article_list_tool(url: str) -> str:
    """
    Fetch recent article list from a blog or news website.

    Use this tool to discover what articles are available on a blog homepage or news site.
    It extracts article metadata (title, URL, date, preview) without fetching full content.
    Results are sorted by date (newest first).

    Ideal for:
    - Discovering recent posts from tech blogs (e.g., blog.langchain.com, openai.com/news)
    - Finding latest articles from company engineering blogs
    - Getting an overview of what's published on a news/blog site

    Note: This tool only returns article listings. To read full article content,
    use the Content Reader subagent with specific article URLs.

    Args:
        url: The URL of the blog homepage or news listing page.

    Returns:
        Markdown-formatted list of articles with headline, URL, publish date, and preview.
    """
    try:
        result = fetch_article_list(url)

        if "articleList" not in result:
            return f"Error: No article list found at {url}. The page may not contain a list of articles."

        article_list_data = result["articleList"]
        articles = _extract_articles_from_response(article_list_data)
        
        return format_article_list_as_markdown(articles)

    except ValueError as e:
        return f"Error: {str(e)}"
    except requests.RequestException as e:
        return _handle_request_error(e, url)
    except Exception as e:
        return f"Error fetching article list: Unexpected error - {str(e)}"
