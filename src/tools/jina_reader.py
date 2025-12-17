"""
Jina AI Reader Tool

This module provides functionality to fetch URL content as markdown
using the Jina AI Reader API.
"""

import os
from typing import Optional

import requests
from langchain_core.tools import tool


def fetch_url_as_markdown(url: str, api_key: Optional[str] = None) -> str:
    """
    Fetch URL content using Jina AI Reader API and return as markdown.

    Args:
        url: The URL to fetch content from.
        api_key: Jina AI API key. If not provided, will try to get from environment.

    Returns:
        The URL content in markdown format.

    Raises:
        ValueError: If API key is not provided.
        requests.RequestException: If the API request fails.
    """
    # Get API key from parameter or environment
    jina_api_key = api_key or os.getenv("JINA_API_KEY")
    if not jina_api_key:
        raise ValueError(
            "JINA_API_KEY is required. Set it in .env file or pass as parameter."
        )

    jina_url = "https://r.jina.ai/"
    headers = {
        "Authorization": f"Bearer {jina_api_key}",
        "Content-Type": "application/json",
    }
    data = {"url": url}

    response = requests.post(jina_url, headers=headers, json=data, timeout=60)
    response.raise_for_status()

    return response.text


@tool
def get_jina_reader_tool(url: str) -> str:
    """
    Fetch content from a URL and return it as markdown text.

    Use this tool to extract the main content from any web page in a clean,
    readable markdown format. This is useful for reading articles, blog posts,
    documentation, or any web content.

    Args:
        url: The URL of the web page to fetch content from.

    Returns:
        The web page content formatted as markdown text.
    """
    try:
        content = fetch_url_as_markdown(url)
        return content

    except ValueError as e:
        return f"Error: {str(e)}"
    except requests.RequestException as e:
        return f"Error fetching URL content: Network error - {str(e)}"
    except Exception as e:
        return f"Error fetching URL content: Unexpected error - {str(e)}"


# For direct testing
if __name__ == "__main__":
    result = get_jina_reader_tool.invoke({"url": "https://example.com"})
    print(result)
