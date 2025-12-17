"""
ArXiv MCP Adapter

This module provides tools to access ArXiv MCP server features,
including fetching analysis prompts for deep paper analysis.
"""

from typing import Any, Callable, Optional

from langchain_core.tools import StructuredTool


# MCP Prompt names from arxiv-mcp-server
ARXIV_PROMPTS = {
    "deep-paper-analysis": {
        "description": "Detailed analysis of a specific paper",
        "required_args": ["paper_id"],
    },
    "research-discovery": {
        "description": "Discover relevant research on a topic",
        "required_args": ["topic"],
    },
    "literature-synthesis": {
        "description": "Synthesize findings from multiple papers",
        "required_args": ["paper_ids"],
    },
    "research-question": {
        "description": "Formulate research questions based on literature",
        "required_args": ["paper_ids", "topic"],
    },
}


async def fetch_arxiv_prompt(
    client: Any,
    prompt_name: str,
    arguments: dict[str, str],
) -> str:
    """
    Fetch a prompt from the ArXiv MCP server.

    Args:
        client: The MCP client instance (MultiServerMCPClient).
        prompt_name: Name of the prompt to fetch.
        arguments: Arguments to pass to the prompt.

    Returns:
        The prompt content as a string.
    """
    if prompt_name not in ARXIV_PROMPTS:
        available = ", ".join(ARXIV_PROMPTS.keys())
        return f"Error: Unknown prompt '{prompt_name}'. Available: {available}"

    try:
        # Access the underlying session to call get_prompt
        # MultiServerMCPClient stores sessions by server name
        session = client.sessions.get("arxiv")
        if not session:
            return "Error: ArXiv MCP session not available."

        # Call the MCP prompts/get method
        result = await session.get_prompt(prompt_name, arguments=arguments)

        # Extract the content from the prompt messages
        if hasattr(result, "messages") and result.messages:
            # Combine all message contents
            contents = []
            for msg in result.messages:
                if hasattr(msg, "content"):
                    if isinstance(msg.content, str):
                        contents.append(msg.content)
                    elif hasattr(msg.content, "text"):
                        contents.append(msg.content.text)
            return "\n\n".join(contents)

        return str(result)

    except Exception as e:
        return f"Error fetching prompt from ArXiv MCP: {str(e)}"


def create_arxiv_analysis_prompt_tool(
    client: Optional[Any] = None,
) -> Optional[StructuredTool]:
    """
    Create a tool for fetching ArXiv paper analysis guidelines.

    This tool allows the agent to dynamically fetch the 'deep-paper-analysis'
    prompt from the ArXiv MCP server when it encounters an ArXiv paper.

    Args:
        client: The MCP client instance. If None, returns None.

    Returns:
        A LangChain StructuredTool, or None if client is not available.
    """
    if client is None:
        return None

    async def get_arxiv_analysis_prompt(paper_id: str) -> str:
        """
        Get analysis guidelines for an ArXiv paper.

        Call this tool when you need to analyze an ArXiv paper.
        It returns detailed instructions on how to perform a comprehensive
        paper analysis, including methodology review, results interpretation,
        and broader impact assessment.

        Args:
            paper_id: The ArXiv paper ID (e.g., '2401.12345').

        Returns:
            Detailed analysis guidelines and framework for the paper.
        """
        return await fetch_arxiv_prompt(
            client=client,
            prompt_name="deep-paper-analysis",
            arguments={"paper_id": paper_id},
        )

    return StructuredTool.from_function(
        coroutine=get_arxiv_analysis_prompt,
        name="get_arxiv_analysis_prompt",
        description=(
            "Get analysis guidelines for an ArXiv paper. "
            "Use this when you need to analyze an ArXiv paper to get "
            "detailed instructions on how to perform comprehensive analysis. "
            "Input: ArXiv paper ID (e.g., '2401.12345'). "
            "Output: Analysis framework and guidelines."
        ),
    )


def create_research_discovery_prompt_tool(
    client: Optional[Any] = None,
) -> Optional[StructuredTool]:
    """
    Create a tool for fetching research discovery guidelines.

    Args:
        client: The MCP client instance. If None, returns None.

    Returns:
        A LangChain StructuredTool, or None if client is not available.
    """
    if client is None:
        return None

    async def get_research_discovery_prompt(topic: str) -> str:
        """
        Get guidelines for discovering research on a topic.

        Args:
            topic: The research topic to explore.

        Returns:
            Guidelines for discovering relevant research.
        """
        return await fetch_arxiv_prompt(
            client=client,
            prompt_name="research-discovery",
            arguments={"topic": topic},
        )

    return StructuredTool.from_function(
        coroutine=get_research_discovery_prompt,
        name="get_research_discovery_prompt",
        description=(
            "Get guidelines for discovering research on a specific topic. "
            "Use this when exploring a new research area. "
            "Input: Research topic. "
            "Output: Discovery framework and guidelines."
        ),
    )
