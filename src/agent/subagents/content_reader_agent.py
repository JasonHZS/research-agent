"""
Universal Content Reader Subagent

This subagent is responsible for:
1. Reading web content using Jina Reader
2. Reading ArXiv papers using ArXiv MCP tools
3. Summarizing content in a structured format

This agent receives URLs or IDs from the main agent and returns
concise summaries, protecting the main agent's context window.
"""

from typing import Any

from src.prompts import load_prompt
from src.tools.jina_reader import get_jina_reader_tool


ARXIV_READER_TOOL_NAMES = {
    "read_paper",
    "download_paper",
    "list_papers",
}

ARXIV_SEARCH_TOOL_NAMES = {
    "search_papers",
}

# Hacker News: all known discovery tools loaded from the MCP server.
# We bind them explicitly to the main agent (search/discovery), none to reader.
HN_SEARCH_TOOL_NAMES = {
    "getTopStories",
    "getBestStories",
    "getNewStories",
    "getAskHNStories",
    "getShowHNStories",
    "getJobStories",
    "getItem",
    "getUser",
    "getComments",
    "getMaxItemId",
    "getUpdates",
}

HN_READER_TOOL_NAMES: set[str] = set()


def _select_tools(mcp_tools: list | None, allowed_names: set[str]) -> list:
    """Return tools whose names (case-insensitive) are in allowed_names."""
    if not mcp_tools or not allowed_names:
        return []
    allowed_lower = {name.lower() for name in allowed_names}
    return [tool for tool in mcp_tools if tool.name.lower() in allowed_lower]


def get_reader_agent_tools(mcp_tools: list | None) -> list:
    """
    Get tools for the Content Reader agent (reading/consumption).
    
    Returns tools explicitly designated for deep content reading:
    - ArXiv: read_paper, download_paper, list_papers
    - Hacker News: (none currently)
    """
    return _select_tools(mcp_tools, ARXIV_READER_TOOL_NAMES | HN_READER_TOOL_NAMES)


def get_main_agent_tools(mcp_tools: list | None) -> list:
    """
    Get tools for the Main Research agent (search/discovery).
    
    Returns tools explicitly designated for discovery and search:
    - ArXiv: search_papers
    - Hacker News: getTopStories, getBestStories, getNewStories, etc.
    """
    return _select_tools(
        mcp_tools,
        ARXIV_SEARCH_TOOL_NAMES
        | HN_SEARCH_TOOL_NAMES,
    )


def create_content_reader_subagent(
    arxiv_mcp_tools: list | None = None,
    hn_mcp_tools: list | None = None,
) -> dict[str, Any]:
    """
    Create the Universal Content Reader subagent configuration.

    This subagent handles all content reading and summarization tasks,
    regardless of content source (web pages, papers, etc.).

    Args:
        arxiv_mcp_tools: ArXiv MCP tools (only reader tools will be selected).
        hn_mcp_tools: Hacker News MCP tools (only reader tools will be selected).

    Returns:
        Subagent configuration dictionary compatible with deepagents.
    """
    # Load templates
    paper_summary_format = load_prompt("paper_summary")

    # Render system prompt from template
    system_prompt = load_prompt(
        "content_reader",
        paper_summary_format=paper_summary_format,
    )

    # Build tools list: Jina Reader + filtered ArXiv/HN reading tools
    tools = [get_jina_reader_tool]

    # Add explicit ArXiv reading tools
    arxiv_reader_tools = _select_tools(arxiv_mcp_tools, ARXIV_READER_TOOL_NAMES)
    if arxiv_reader_tools:
        tools.extend(arxiv_reader_tools)

    # HN reader tools: none bound explicitly

    return {
        "name": "content-reader-agent",
        "description": (
            "通用内容阅读与总结专家。"
            "当需要深度阅读网页文章、ArXiv 论文或其他内容时使用此 agent。"
            "传入 URL 或 ArXiv ID，返回结构化的内容总结。"
            "适用于：阅读论文全文、阅读技术博客、阅读新闻文章、提取文档要点。"
        ),
        "system_prompt": system_prompt,
        "tools": tools,
    }
