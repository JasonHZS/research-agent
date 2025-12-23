"""
ArXiv API Tools

This module provides tools for searching and fetching papers from ArXiv
using the official ArXiv API (http://export.arxiv.org/api/query).

API Documentation: https://info.arxiv.org/help/api/user-manual.html
"""

import re
import xml.etree.ElementTree as ET
from typing import Literal, Optional

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

ARXIV_API_BASE_URL = "http://export.arxiv.org/api/query"

# XML namespaces used by ArXiv API (Atom 1.0 format)
NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _parse_arxiv_entry(entry: ET.Element) -> dict:
    """
    Parse a single ArXiv entry from the API response.

    Args:
        entry: XML Element representing an ArXiv paper entry.

    Returns:
        Dictionary with paper metadata.
    """
    # Extract arxiv_id from the id URL
    id_elem = entry.find("atom:id", NAMESPACES)
    arxiv_id = ""
    if id_elem is not None and id_elem.text:
        # Format: http://arxiv.org/abs/2402.02716v1
        match = re.search(r"arxiv\.org/abs/(.+?)(?:v\d+)?$", id_elem.text)
        if match:
            arxiv_id = match.group(1)

    # Title
    title_elem = entry.find("atom:title", NAMESPACES)
    title = (
        title_elem.text.strip().replace("\n", " ")
        if title_elem is not None and title_elem.text
        else ""
    )

    # Authors
    authors = []
    for author in entry.findall("atom:author", NAMESPACES):
        name_elem = author.find("atom:name", NAMESPACES)
        if name_elem is not None and name_elem.text:
            authors.append(name_elem.text.strip())

    # Summary (abstract)
    summary_elem = entry.find("atom:summary", NAMESPACES)
    summary = (
        summary_elem.text.strip()
        if summary_elem is not None and summary_elem.text
        else ""
    )

    # Published and Updated dates
    published_elem = entry.find("atom:published", NAMESPACES)
    published = (
        published_elem.text[:10]
        if published_elem is not None and published_elem.text
        else ""
    )

    updated_elem = entry.find("atom:updated", NAMESPACES)
    updated = (
        updated_elem.text[:10] if updated_elem is not None and updated_elem.text else ""
    )

    # Primary category
    primary_cat_elem = entry.find("arxiv:primary_category", NAMESPACES)
    primary_category = (
        primary_cat_elem.get("term", "") if primary_cat_elem is not None else ""
    )

    # All categories
    categories = []
    for cat in entry.findall("atom:category", NAMESPACES):
        term = cat.get("term")
        if term:
            categories.append(term)

    # PDF link
    pdf_url = ""
    for link in entry.findall("atom:link", NAMESPACES):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
            break

    # Comment (optional)
    comment_elem = entry.find("arxiv:comment", NAMESPACES)
    comment = (
        comment_elem.text.strip()
        if comment_elem is not None and comment_elem.text
        else ""
    )

    # Journal reference (optional)
    journal_ref_elem = entry.find("arxiv:journal_ref", NAMESPACES)
    journal_ref = (
        journal_ref_elem.text.strip()
        if journal_ref_elem is not None and journal_ref_elem.text
        else ""
    )

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": authors,
        "summary": summary,
        "published": published,
        "updated": updated,
        "primary_category": primary_category,
        "categories": categories,
        "pdf_url": pdf_url,
        "comment": comment,
        "journal_ref": journal_ref,
    }


def _format_paper_markdown(paper: dict, include_summary: bool = True) -> str:
    """
    Format a paper dictionary as markdown.

    Args:
        paper: Dictionary with paper metadata.
        include_summary: Whether to include the full abstract.

    Returns:
        Formatted markdown string.
    """
    lines = [f"### {paper['title']}"]
    lines.append(f"**ArXiv ID:** {paper['arxiv_id']}")

    # Format authors (truncate if too many)
    if paper["authors"]:
        author_str = ", ".join(paper["authors"][:5])
        if len(paper["authors"]) > 5:
            author_str += " et al."
        lines.append(f"**Authors:** {author_str}")

    lines.append(f"**Published:** {paper['published']}")

    if paper["updated"] and paper["updated"] != paper["published"]:
        lines.append(f"**Updated:** {paper['updated']}")

    if paper["primary_category"]:
        lines.append(f"**Category:** {paper['primary_category']}")

    if paper["pdf_url"]:
        lines.append(f"**PDF:** {paper['pdf_url']}")

    if paper["comment"]:
        lines.append(f"**Comment:** {paper['comment']}")

    if paper["journal_ref"]:
        lines.append(f"**Journal:** {paper['journal_ref']}")

    if include_summary and paper["summary"]:
        lines.append(f"\n**Abstract:**\n{paper['summary']}")

    return "\n".join(lines)


def fetch_arxiv_paper(arxiv_id: str) -> dict:
    """
    Fetch a single paper's metadata from ArXiv API.

    Args:
        arxiv_id: ArXiv paper ID (e.g., "2402.02716" or "2402.02716v1").

    Returns:
        Dictionary with paper metadata.

    Raises:
        requests.RequestException: If the API request fails.
        ValueError: If paper not found or invalid response.
    """
    # Clean the arxiv_id (remove version suffix if present for query)
    clean_id = re.sub(r"v\d+$", "", arxiv_id.strip())

    url = f"{ARXIV_API_BASE_URL}?id_list={clean_id}"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    entries = root.findall("atom:entry", NAMESPACES)
    if not entries:
        raise ValueError(f"Paper not found: {arxiv_id}")

    paper = _parse_arxiv_entry(entries[0])

    # Check if the entry is actually an error response
    if not paper["arxiv_id"]:
        raise ValueError(f"Paper not found: {arxiv_id}")

    return paper


def search_arxiv(
    query: str, max_results: int = 10, sort_by: str = "relevance"
) -> list[dict]:
    """
    Search ArXiv papers using the API.

    Args:
        query: Search query string. Supports ArXiv query syntax:
               - Simple: "LLM agents"
               - Field-specific: "ti:transformer" (title), "au:hinton" (author)
               - Combined: "all:LLM AND cat:cs.AI"
        max_results: Maximum number of results (1-100, default 10).
        sort_by: Sort order - "relevance", "lastUpdatedDate", or "submittedDate".

    Returns:
        List of paper dictionaries.

    Raises:
        requests.RequestException: If the API request fails.
    """
    # Clamp max_results
    max_results = max(1, min(100, max_results))

    # Map sort_by to ArXiv API parameter
    sort_map = {
        "relevance": "relevance",
        "lastUpdatedDate": "lastUpdatedDate",
        "submittedDate": "submittedDate",
        "updated": "lastUpdatedDate",
        "submitted": "submittedDate",
    }
    sort_param = sort_map.get(sort_by, "relevance")

    # Build query - if no field prefix, use "all:"
    if not any(
        prefix in query
        for prefix in ["ti:", "au:", "abs:", "co:", "jr:", "cat:", "all:"]
    ):
        search_query = f"all:{query}"
    else:
        search_query = query

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_param,
        "sortOrder": "descending",
    }

    response = requests.get(ARXIV_API_BASE_URL, params=params, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    entries = root.findall("atom:entry", NAMESPACES)
    papers = [_parse_arxiv_entry(entry) for entry in entries]

    # Filter out entries without valid arxiv_id (error entries)
    papers = [p for p in papers if p["arxiv_id"]]

    return papers


@tool
def get_arxiv_paper_tool(arxiv_id: str) -> str:
    """
    Fetch detailed metadata for a specific ArXiv paper.

    Use this tool when you need to get the full details of an ArXiv paper
    including its abstract, categories, and links.

    Args:
        arxiv_id: The ArXiv paper ID (e.g., "2402.02716" or "2402.02716v1").
                  Can also be the full ArXiv URL.

    Returns:
        Formatted markdown containing the paper's metadata and abstract.
    """
    try:
        # Extract arxiv_id from URL if provided
        if "arxiv.org" in arxiv_id:
            match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", arxiv_id)
            if match:
                arxiv_id = match.group(1)
            else:
                return f"Error: Could not extract ArXiv ID from URL: {arxiv_id}"

        paper = fetch_arxiv_paper(arxiv_id)

        result = f"## ArXiv Paper: {paper['arxiv_id']}\n\n"
        result += _format_paper_markdown(paper, include_summary=True)

        return result

    except ValueError as e:
        return f"Error: {str(e)}"
    except requests.RequestException as e:
        return f"Error fetching paper: Network error - {str(e)}"
    except ET.ParseError as e:
        return f"Error parsing ArXiv response: {str(e)}"
    except Exception as e:
        return f"Error fetching paper: Unexpected error - {str(e)}"


class SearchArxivInput(BaseModel):
    """Input schema for ArXiv paper search."""

    query: str = Field(
        description=(
            "Search query. Examples: "
            '"LLM agents" (searches all fields), '
            '"ti:transformer" (title contains "transformer"), '
            '"au:hinton" (author is "hinton"), '
            '"cat:cs.AI" (category is cs.AI), '
            '"all:LLM AND cat:cs.CL" (combined query)'
        )
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of papers to return (1-100)",
    )
    sort_by: Literal["relevance", "lastUpdatedDate", "submittedDate"] = Field(
        default="relevance",
        description="Sort order for results",
    )


@tool(args_schema=SearchArxivInput)
def search_arxiv_papers_tool(
    query: str,
    max_results: int = 10,
    sort_by: str = "relevance",
) -> str:
    """
    Search for papers on ArXiv.

    Use this tool to find research papers matching your search query.
    Supports field-specific searches (see query parameter for syntax).
    """
    try:
        papers = search_arxiv(
            query, max_results=max_results or 10, sort_by=sort_by or "relevance"
        )

        if not papers:
            return f"No papers found for query: {query}"

        result_parts = ["## ArXiv Search Results\n"]
        result_parts.append(f"**Query:** {query}")
        result_parts.append(f"**Found:** {len(papers)} papers\n")

        for i, paper in enumerate(papers, 1):
            result_parts.append("\n---\n")
            result_parts.append(
                f"**{i}.** {_format_paper_markdown(paper, include_summary=False)}"
            )
            # Add truncated summary
            if paper["summary"]:
                summary_preview = paper["summary"][:300]
                if len(paper["summary"]) > 300:
                    summary_preview += "..."
                result_parts.append(f"\n**Summary:** {summary_preview}")

        return "\n".join(result_parts)

    except requests.RequestException as e:
        return f"Error searching ArXiv: Network error - {str(e)}"
    except ET.ParseError as e:
        return f"Error parsing ArXiv response: {str(e)}"
    except Exception as e:
        return f"Error searching ArXiv: Unexpected error - {str(e)}"
