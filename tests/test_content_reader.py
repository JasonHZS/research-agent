#!/usr/bin/env python3
"""
Test Content Reader Subagent

This script allows you to test the content reader subagent independently
without running the full research agent. It can read web pages using Jina Reader
and ArXiv papers using MCP tools.

Usage:
    # Test reading a web page
    uv run python tests/test_content_reader.py --url "https://lilianweng.github.io/posts/2023-06-23-agent/"

    # Test reading an ArXiv paper (requires ArXiv MCP)
    uv run python tests/test_content_reader.py --arxiv-id "2402.02716"

    # Test with custom query
    uv run python tests/test_content_reader.py --query "Summarize the main ideas from https://example.com"

    # Use verbose mode to see tool calls
    uv run python tests/test_content_reader.py --url "https://example.com" -v
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from deepagents import create_deep_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from src.agent.subagents import create_content_reader_subagent
from src.config.mcp_config import get_single_server_config


async def load_mcp_tools(server_name: str) -> tuple[Optional[MultiServerMCPClient], list]:
    """
    Load tools from a single MCP server.

    Args:
        server_name: Name of the MCP server ('arxiv' or 'hackernews').

    Returns:
        Tuple of (MCP client, list of tools).
    """
    try:
        config = get_single_server_config(server_name)
        client = MultiServerMCPClient({server_name: config})
        tools = await client.get_tools()
        print(f"✓ Loaded {len(tools)} tools from {server_name} MCP server")
        return client, tools
    except Exception as e:
        print(f"⚠ Warning: Could not load {server_name} MCP tools: {e}")
        return None, []


async def test_content_reader(
    query: str,
    model_provider: str = "aliyun",
    model_name: Optional[str] = None,
    enable_arxiv: bool = True,
    enable_hn: bool = False,
    verbose: bool = False,
) -> None:
    """
    Test the content reader subagent with a given query.

    Args:
        query: The query to send to the content reader.
        model_provider: LLM provider ('aliyun', 'anthropic', or 'openai').
        model_name: Specific model name.
        enable_arxiv: Whether to load ArXiv MCP tools.
        enable_hn: Whether to load Hacker News MCP tools.
        verbose: Enable verbose output with tool calls.
    """
    print("=" * 60)
    print("Content Reader Subagent Test")
    print("=" * 60)
    print(f"Provider: {model_provider} | Model: {model_name or 'default'}")
    print(f"Query: {query}")
    print("=" * 60)

    # Load MCP tools
    arxiv_tools = []
    hn_tools = []

    if enable_arxiv:
        print("\nLoading ArXiv MCP tools...")
        _, arxiv_tools = await load_mcp_tools("arxiv")

    if enable_hn:
        print("\nLoading Hacker News MCP tools...")
        _, hn_tools = await load_mcp_tools("hackernews")

    # Create the content reader subagent configuration
    print("\nCreating Content Reader subagent...")
    subagent_config = create_content_reader_subagent(
        arxiv_mcp_tools=arxiv_tools,
        hn_mcp_tools=hn_tools,
    )

    print(f"✓ Subagent configured with {len(subagent_config['tools'])} tools:")
    for tool in subagent_config['tools']:
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        print(f"  - {tool_name}")

    # Get model configuration
    from src.agent.research_agent import _get_model_config
    model_config = _get_model_config(model_provider, model_name)

    # Create the agent using DeepAgents
    # Note: We use the subagent config directly to create a standalone agent
    print(f"\nCreating agent with model: {model_config.get('model', 'default')}")
    agent = create_deep_agent(
        tools=subagent_config["tools"],
        system_prompt=subagent_config["system_prompt"],
        debug=verbose,
        **model_config,
    )

    # Run the query
    print("\n" + "-" * 60)
    print("Running query...")
    print("-" * 60 + "\n")

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": query}]}
        )

        # Extract the final response
        final_message = result["messages"][-1]
        if hasattr(final_message, "content"):
            response = final_message.content
        else:
            response = str(final_message)

        print("\n" + "=" * 60)
        print("RESULT:")
        print("=" * 60)
        print(response)
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error running query: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Test the content reader subagent independently",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Query options (mutually exclusive)
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument(
        "--url",
        type=str,
        help="URL to read and summarize",
    )
    query_group.add_argument(
        "--arxiv-id",
        type=str,
        help="ArXiv paper ID to read (e.g., '2401.12345')",
    )
    query_group.add_argument(
        "--query",
        type=str,
        help="Custom query to send to the content reader",
    )

    # Model configuration
    parser.add_argument(
        "-p", "--model-provider",
        type=str,
        default="aliyun",
        choices=["aliyun", "anthropic", "openai"],
        help="LLM provider to use (default: aliyun)",
    )
    parser.add_argument(
        "-m", "--model-name",
        type=str,
        default=None,
        help="Model name (e.g., 'qwen-max', 'kimi-k2-thinking')",
    )

    # MCP tools
    parser.add_argument(
        "--no-arxiv",
        action="store_true",
        help="Disable ArXiv MCP tools",
    )
    parser.add_argument(
        "--enable-hn",
        action="store_true",
        help="Enable Hacker News MCP tools (disabled by default)",
    )

    # Output options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose mode (shows tool calls and agent steps)",
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Build query based on input
    if args.url:
        query = f"Please read and summarize the content from this URL: {args.url}"
    elif args.arxiv_id:
        query = f"Please read and summarize the ArXiv paper with ID: {args.arxiv_id}"
    else:
        query = args.query

    # Run the test
    try:
        asyncio.run(
            test_content_reader(
                query=query,
                model_provider=args.model_provider,
                model_name=args.model_name,
                enable_arxiv=not args.no_arxiv,
                enable_hn=args.enable_hn,
                verbose=args.verbose,
            )
        )
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
