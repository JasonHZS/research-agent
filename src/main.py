"""
Research Agent Main Entry Point

This module provides the main entry point for running the research agent
with MCP tools integration.

Multi-turn Conversation Support:
- Uses MemorySaver to persist conversation state across turns
- Uses InMemoryStore for persistent file storage via /memories/ path
- Each session gets a unique thread_id for conversation tracking
"""

import asyncio
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from src.agent.research_agent import create_research_agent, run_research_async
from src.config.mcp_config import get_single_server_config


@dataclass
class MCPToolsContext:
    """Container for MCP clients and their tools."""

    arxiv_client: Optional[MultiServerMCPClient] = None
    arxiv_tools: list = None
    hn_client: Optional[MultiServerMCPClient] = None
    hn_tools: list = None

    def __post_init__(self):
        if self.arxiv_tools is None:
            self.arxiv_tools = []
        if self.hn_tools is None:
            self.hn_tools = []

    async def cleanup(self):
        """Clean up all MCP clients."""
        # As of langchain-mcp-adapters 0.1.0, clients don't need explicit cleanup
        # when not used as context managers
        pass


async def _load_mcp_server_tools(
    server_name: str,
) -> tuple[Optional[MultiServerMCPClient], list]:
    """
    Load tools from a single MCP server.

    As of langchain-mcp-adapters 0.1.0, MultiServerMCPClient no longer supports
    context manager usage. Instead, directly create client and call get_tools().

    Args:
        server_name: Name of the MCP server to load.

    Returns:
        Tuple of (MCP client instance, list of loaded tools).
    """
    try:
        config = get_single_server_config(server_name)
        client = MultiServerMCPClient({server_name: config})
        # In langchain-mcp-adapters 0.1.0+, get_tools() handles connection internally
        tools = await client.get_tools()
        print(f"✓ Loaded {len(tools)} tools from {server_name} MCP server")
        for tool in tools:
            desc = tool.description[:50] if tool.description else "No description"
            print(f"  - {tool.name}: {desc}...")
        return client, tools
    except Exception as e:
        print(f"⚠ Warning: Could not load {server_name} MCP tools: {e}")
        return None, []


async def initialize_mcp_tools() -> MCPToolsContext:
    """
    Initialize MCP clients and load tools from configured servers.

    Returns:
        MCPToolsContext containing clients and tools for each server.
    """
    ctx = MCPToolsContext()

    # Load ArXiv MCP tools
    ctx.arxiv_client, ctx.arxiv_tools = await _load_mcp_server_tools("arxiv")

    # Load Hacker News MCP tools
    ctx.hn_client, ctx.hn_tools = await _load_mcp_server_tools("hackernews")

    total_tools = len(ctx.arxiv_tools) + len(ctx.hn_tools)
    if total_tools == 0:
        print("  Continuing with built-in tools only...")

    return ctx


def _create_session_agent(
    mcp_ctx: MCPToolsContext,
    model_provider: str,
    model_name: Optional[str],
    checkpointer: MemorySaver,
    store: InMemoryStore,
    debug: bool = False,
) -> Any:
    """
    Create a research agent configured for multi-turn conversation.

    Args:
        mcp_ctx: MCP tools context.
        model_provider: LLM provider.
        model_name: Model name.
        checkpointer: MemorySaver for conversation state.
        store: InMemoryStore for file persistence.
        debug: Enable debug mode for detailed execution logs.

    Returns:
        Configured agent instance.
    """
    return create_research_agent(
        arxiv_mcp_tools=mcp_ctx.arxiv_tools,
        hn_mcp_tools=mcp_ctx.hn_tools,
        model_provider=model_provider,
        model_name=model_name,
        checkpointer=checkpointer,
        store=store,
        debug=debug,
    )


async def main(
    query: Optional[str] = None,
    model_provider: str = "aliyun",
    model_name: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """
    Main function to run the research agent.

    Supports multi-turn conversations by:
    - Creating a single agent instance per session
    - Using MemorySaver to persist conversation state
    - Using InMemoryStore for file persistence
    - Generating a unique thread_id per session

    Args:
        query: Research query to execute. If None, runs in interactive mode.
        model_provider: LLM provider ('aliyun', 'anthropic', or 'openai').
        model_name: Specific model name (e.g., 'qwen-max', 'kimi-k2-thinking').
        verbose: If True, prints detailed execution logs including tool calls.
    """
    # Load environment variables
    load_dotenv()

    # Check for required API keys based on provider
    if model_provider == "aliyun":
        if not (os.getenv("ALIYUN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")):
            print("Error: ALIYUN_API_KEY or DASHSCOPE_API_KEY environment variable not set")
            print("Please set it in your .env file or environment")
            sys.exit(1)
    elif model_provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it in your .env file or environment")
        sys.exit(1)
    elif model_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set it in your .env file or environment")
        sys.exit(1)

    print("=" * 60)
    print("Research Agent - Powered by DeepAgents")
    print(f"Provider: {model_provider} | Model: {model_name or 'default'}")
    print("=" * 60)

    # Initialize MCP tools (per server)
    mcp_ctx = await initialize_mcp_tools()

    # Initialize persistence for multi-turn conversations
    checkpointer = MemorySaver()
    store = InMemoryStore()

    # Generate unique thread_id for this session
    thread_id = str(uuid.uuid4())
    print(f"Session ID: {thread_id[:8]}...")

    # Create a single agent instance for the entire session
    # Pass debug=verbose to enable DeepAgents built-in debug mode
    agent = _create_session_agent(
        mcp_ctx=mcp_ctx,
        model_provider=model_provider,
        model_name=model_name,
        checkpointer=checkpointer,
        store=store,
        debug=verbose,
    )

    try:
        if query:
            # Single query mode (still uses checkpointer for potential follow-ups)
            print(f"\nResearch Query: {query}\n")
            print("-" * 60)
            result = await run_research_async(
                query=query,
                agent=agent,
                thread_id=thread_id,
            )
            print("\n" + result)
        else:
            # Interactive mode with multi-turn conversation support
            print("\nEntering interactive mode. Type 'quit' to exit.")
            print("Conversation history is preserved across turns.")
            if verbose:
                print("Debug mode: ON - showing detailed execution logs")
            print()
            while True:
                try:
                    user_input = input("\n📚 Research Query: ").strip()
                    if user_input.lower() in ("quit", "exit", "q"):
                        print("Goodbye!")
                        break
                    if user_input.lower() == "new":
                        # Start a new conversation thread
                        thread_id = str(uuid.uuid4())
                        print(f"🔄 New session started. Session ID: {thread_id[:8]}...")
                        continue
                    if not user_input:
                        continue

                    print("\n🔍 Researching...\n")
                    result = await run_research_async(
                        query=user_input,
                        agent=agent,
                        thread_id=thread_id,
                    )
                    print("\n" + "-" * 60)
                    print(result)
                    print("-" * 60)
                except KeyboardInterrupt:
                    print("\n\nGoodbye!")
                    break
    finally:
        # Clean up MCP clients
        await mcp_ctx.cleanup()


def run_cli() -> None:
    """CLI entry point for the research agent."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Research Agent - Deep research with MCP tools integration"
    )
    parser.add_argument(
        "-q", "--query",
        type=str,
        help="Research query to execute (runs in interactive mode if not provided)",
    )
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
        help="Model name to use (e.g., 'qwen-max', 'kimi-k2-thinking' for aliyun)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose mode to show detailed execution logs (tool calls, agent steps)",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            query=args.query,
            model_provider=args.model_provider,
            model_name=args.model_name,
            verbose=args.verbose,
        )
    )


if __name__ == "__main__":
    run_cli()

