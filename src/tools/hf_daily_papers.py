"""
Hugging Face Daily Papers Tool

This module provides functionality to fetch daily papers from Hugging Face,
extracting titles, upvotes, and comments for each paper.
"""

import json
import re
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool


def fetch_huggingface_daily_papers(
    target_date: Optional[str] = None, limit: Optional[int] = 5
) -> list[dict]:
    """
    Fetch daily papers from Hugging Face for a specified date.

    Args:
        target_date: Date string in 'YYYY-MM-DD' format. Defaults to today's date.
        limit: Optional maximum number of papers to return, sorted by upvotes.

    Returns:
        List of dictionaries containing paper information with keys:
        - title: Paper title
        - arxiv_id: ArXiv paper ID (if available)
        - url: URL to the paper on Hugging Face
        - upvotes: Number of upvotes
        - num_comments: Number of comments

    Raises:
        requests.RequestException: If the HTTP request fails.
        ValueError: If the date format is invalid.
    """
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")
    else:
        # Validate date format
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format. Use 'YYYY-MM-DD'. Error: {e}") from e

    url = f"https://huggingface.co/papers?date={target_date}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    papers = _parse_papers_page(response.text, target_date)

    # Sort by upvotes descending
    papers.sort(key=lambda x: x.get("upvotes", 0), reverse=True)

    if limit and limit > 0:
        papers = papers[:limit]

    return papers


def _parse_papers_page(html_content: str, target_date: str) -> list[dict]:
    """
    Parse the Hugging Face papers page HTML to extract paper information.
    
    This function primarily attempts to parse the embedded JSON data in the page,
    which is much more reliable than scraping DOM elements.

    Args:
        html_content: Raw HTML content from the papers page.
        target_date: The date being queried (for URL construction).

    Returns:
        List of paper dictionaries with title, arxiv_id, url, upvotes, and comments.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    papers = []

    # Method 1: Try to parse embedded JSON data (most reliable)
    try:
        div = soup.find("div", attrs={"data-target": "DailyPapers"})
        if div and div.has_attr("data-props"):
            props = json.loads(div["data-props"])
            if "dailyPapers" in props:
                for entry in props["dailyPapers"]:
                    # The structure might be nested under 'paper' key or flat depending on the API version
                    paper_data = entry.get("paper", entry)
                    
                    arxiv_id = paper_data.get("id")
                    title = paper_data.get("title")
                    
                    if arxiv_id and title:
                        papers.append({
                            "title": title,
                            "arxiv_id": arxiv_id,
                            "url": f"https://huggingface.co/papers/{arxiv_id}",
                            "upvotes": paper_data.get("upvotes", 0),
                            "num_comments": entry.get("numComments", 0),  # numComments is often on the top level entry
                        })
    except (json.JSONDecodeError, AttributeError):
        pass

    if papers:
        return papers

    # Method 2: Fallback to DOM scraping (legacy support)
    return _extract_papers_fallback(soup, target_date)


def _extract_papers_fallback(soup: BeautifulSoup, target_date: str) -> list[dict]:
    """
    Fallback method to extract papers using DOM scraping.
    
    Note: This method might not extract upvotes/comments correctly as the DOM structure varies.

    Args:
        soup: BeautifulSoup object of the entire page.
        target_date: Date string for reference.

    Returns:
        List of paper dictionaries.
    """
    papers = []
    seen_ids = set()

    # Find all links that might be paper links
    all_links = soup.find_all("a", href=re.compile(r"/papers?/\d+\.\d+"))

    for link in all_links:
        href = link.get("href", "")
        match = re.search(r"/papers?/(\d+\.\d+)", href)
        if not match:
            continue

        arxiv_id = match.group(1)
        if arxiv_id in seen_ids:
            continue
        seen_ids.add(arxiv_id)

        # Get title from link text or nearby heading
        title = link.get_text(strip=True)
        if not title or len(title) < 5:
            parent = link.find_parent(["article", "div", "section"])
            if parent:
                heading = parent.find(["h1", "h2", "h3", "h4"])
                if heading:
                    title = heading.get_text(strip=True)

        if not title or len(title) < 5:
            continue

        papers.append({
            "title": title,
            "arxiv_id": arxiv_id,
            "url": f"https://huggingface.co/papers/{arxiv_id}",
            "upvotes": 0,      # Cannot reliably extract from DOM fallback
            "num_comments": 0, # Cannot reliably extract from DOM fallback
        })

    return papers


@tool
def get_huggingface_papers_tool(
    target_date: Optional[str] = None, limit: Optional[int] = None
) -> str:
    """
    Get daily papers from Hugging Face with their titles, upvotes, and comments.

    Use this tool to fetch the latest AI/ML research papers featured on
    Hugging Face's daily papers page. Each paper includes title, ArXiv ID,
    upvotes count, and comments count.

    Args:
        target_date: Date in 'YYYY-MM-DD' format. Defaults to today's date
                    if not specified.
        limit: Optional number of top-voted papers to return. If not provided,
               returns all papers.

    Returns:
        Formatted string containing papers with their titles, upvotes, and comments.
    """
    try:
        papers = fetch_huggingface_daily_papers(target_date, limit=limit)

        if not papers:
            return f"No papers found for {target_date or 'today'}."

        result_parts = [f"## Hugging Face Daily Papers ({target_date or date.today().isoformat()})\n"]
        result_parts.append(f"Found {len(papers)} papers:\n")

        for i, paper in enumerate(papers, 1):
            result_parts.append(f"\n### {i}. {paper['title']}")
            if paper.get("arxiv_id"):
                result_parts.append(f"\n**ArXiv ID:** {paper['arxiv_id']}")
            if paper.get("url"):
                result_parts.append(f"\n**URL:** {paper['url']}")
            
            # Add upvotes and comments
            upvotes = paper.get("upvotes", 0)
            comments = paper.get("num_comments", 0)
            result_parts.append(f"\n**Upvotes:** {upvotes} | **Comments:** {comments}")
            
            result_parts.append("\n") # Add extra newline separator

        return "\n".join(result_parts)

    except requests.RequestException as e:
        return f"Error fetching papers: Network error - {str(e)}"
    except ValueError as e:
        return f"Error fetching papers: {str(e)}"
    except Exception as e:
        return f"Error fetching papers: Unexpected error - {str(e)}"
