"""
Universal Content Reader Subagent

This subagent is responsible for:
1. Reading web content using configurable reader tools (Jina Reader or Zyte API)

This agent receives URLs from the main agent and returns
concise summaries, protecting the main agent's context window.

The reader tool is configured via CONTENT_READER_TYPE environment variable:
- "jina" (default): Jina Reader
- "zyte": Zyte API
"""

from typing import Any

from src.config.reader_config import ReaderType, get_reader_type
from src.prompts import load_prompt
from src.tools.jina_reader import get_jina_reader_tool
from src.tools.zyte_reader import get_zyte_reader_tool


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
    Get MCP tools for the Content Reader agent (reading/consumption).

    Returns tools explicitly designated for deep content reading from MCP.
    Currently none - URL reading is handled by the built-in Jina Reader tool.
    """
    return _select_tools(mcp_tools, HN_READER_TOOL_NAMES)


def get_main_agent_tools(mcp_tools: list | None) -> list:
    """
    Get MCP tools for the Main Research agent (search/discovery).

    Returns tools explicitly designated for discovery and search:
    - Hacker News: getTopStories, getBestStories, getNewStories, etc.
    """
    return _select_tools(mcp_tools, HN_SEARCH_TOOL_NAMES)


def _get_reader_tool():
    """
    Get the configured content reader tool based on environment configuration.

    Returns:
        The configured reader tool (Jina Reader or Zyte Reader).
    """
    reader_type = get_reader_type()

    if reader_type == ReaderType.ZYTE:
        return get_zyte_reader_tool
    else:
        # Default to Jina Reader
        return get_jina_reader_tool


def create_content_reader_subagent() -> dict[str, Any]:
    """
    Create the Universal Content Reader subagent configuration.

    This subagent handles URL content reading and summarization tasks
    using the configured reader tool (Jina Reader or Zyte API).

    The reader tool is selected based on CONTENT_READER_TYPE environment variable.

    Returns:
        Subagent configuration dictionary compatible with deepagents.
    """
    # Load templates
    summary_format = load_prompt("summary")

    # Render system prompt from template
    system_prompt = load_prompt(
        "content_reader",
        summary_format=summary_format,
    )

    # Build tools list: use configured reader tool
    reader_tool = _get_reader_tool()
    tools = [reader_tool]

    # HN reader tools: none bound explicitly (empty set)

    return {
        "name": "content-reader-agent",
        "description": (
            "URL 内容阅读与总结专家。"
            "当需要深度阅读网页文章、博客、技术文档等 URL 内容时使用此 agent。"
            "传入 URL，返回结构化的内容总结。"
            "适用于：阅读技术博客、阅读新闻文章、提取文档要点。"
        ),
        "system_prompt": system_prompt,
        "tools": tools,
    }
