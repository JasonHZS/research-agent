"""
Research Agent Main Entry Point

This module provides the main entry point for running the research agent
with MCP tools integration.

Multi-turn Conversation Support:
- Uses MemorySaver to persist conversation state across turns
- Uses InMemoryStore for persistent file storage via /memories/ path
- Each session gets a unique thread_id for conversation tracking

Deep Research Mode (Supervisor-Researcher Architecture):
- Enable with --deep-research flag
- Implements supervisor-researcher multi-agent architecture
- Supervisor plans and delegates, researchers execute in parallel
- Configurable max iterations and concurrency
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

from src.agent.research_agent import (
    create_research_agent,
    run_research_async,
    run_research_stream,
)
from src.deep_research import build_deep_research_graph, run_deep_research
from src.config.deep_research_config import (
    get_max_iterations,
    get_max_concurrent_researchers,
    get_max_tool_calls,
    get_allow_clarification,
)
from src.config.llm_config import get_model_settings
from src.config.mcp_config import get_single_server_config
from src.utils.stream_display import StreamDisplay


@dataclass
class MCPToolsContext:
    """Container for MCP clients and their tools."""

    hn_client: Optional[MultiServerMCPClient] = None
    hn_tools: list = None

    def __post_init__(self):
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
        # print(f"✓ Loaded {len(tools)} tools from {server_name} MCP server")
        # for tool in tools:
        #     desc = tool.description[:50] if tool.description else "No description"
        #     print(f"  - {tool.name}: {desc}...")
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

    # Load Hacker News MCP tools
    ctx.hn_client, ctx.hn_tools = await _load_mcp_server_tools("hackernews")

    total_tools = len(ctx.hn_tools)
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
    enable_thinking: bool = False,
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
        enable_thinking: Enable thinking mode for supported models.

    Returns:
        Configured agent instance.
    """
    return create_research_agent(
        hn_mcp_tools=mcp_ctx.hn_tools,
        model_provider=model_provider,
        model_name=model_name,
        checkpointer=checkpointer,
        store=store,
        debug=debug,
        enable_thinking=enable_thinking,
    )


async def main_deep_research(
    query: str,
    mcp_ctx: MCPToolsContext,
    model_provider: str,
    model_name: Optional[str],
    max_iterations: int,
    max_concurrent: int,
    max_tool_calls: int,
    allow_clarification: bool,
    verbose: bool = False,
) -> None:
    """
    Run deep research mode with supervisor-researcher architecture.

    This implements a multi-agent system where:
    - Supervisor plans research strategy and delegates tasks
    - Multiple researchers work in parallel on sub-topics
    - Results are compressed and aggregated for final report

    Args:
        query: Research query to execute.
        mcp_ctx: MCP tools context.
        model_provider: LLM provider.
        model_name: Model name.
        max_iterations: Maximum supervisor iterations.
        max_concurrent: Maximum concurrent researchers.
        max_tool_calls: Maximum tool calls per researcher.
        allow_clarification: Whether to allow user clarification.
        verbose: Enable verbose output.
    """
    print("\n🔬 Deep Research Mode (Supervisor-Researcher Architecture)")
    print(f"Max iterations: {max_iterations} | Max concurrent: {max_concurrent}")
    print("-" * 60)

    # Build the deep research graph
    graph = build_deep_research_graph(
        hn_mcp_tools=mcp_ctx.hn_tools,
        model_provider=model_provider,
        model_name=model_name,
    )

    # Configuration
    config = {
        "max_concurrency": max_concurrent,
        "configurable": {
            "thread_id": f"deep_research_{uuid.uuid4().hex[:8]}",
            "max_concurrent_researchers": max_concurrent,
            "max_researcher_iterations": max_iterations,
            "max_review_iterations": max_iterations,  # review 节点使用此配置
            "max_tool_calls_per_researcher": max_tool_calls,
            "allow_clarification": allow_clarification,
            "model_provider": model_provider,
            "model_name": model_name,
            "verbose": verbose,
        }
    }

    # Define clarification callback
    async def on_clarify_question(question: str) -> str:
        """Handle clarification questions from the graph."""
        print(f"\n💬 {question}")
        print("   (输入 '直接开始' 或 'skip' 跳过澄清)")

        try:
            user_answer = input("\n📝 Your answer: ").strip()
        except (KeyboardInterrupt, EOFError):
            return "直接开始"

        # Check if user wants to skip clarification
        skip_phrases = ["直接开始", "跳过", "skip", "start", "开始研究", "不用问了"]
        if any(phrase in user_answer.lower() for phrase in skip_phrases):
            return "请直接开始研究，不需要更多澄清。"
        return user_answer

    # Run deep research
    try:
        final_report = await run_deep_research(
            query=query,
            graph=graph,
            config=config,
            on_clarify_question=on_clarify_question if allow_clarification else None,
        )

        if final_report:
            print("\n" + "=" * 60)
            print("📊 DEEP RESEARCH REPORT")
            print("=" * 60 + "\n")
            print(final_report)
            print("\n" + "=" * 60)
        else:
            print("\n⚠ No report generated. Please try again with a different query.")

    except Exception as e:
        print(f"\n❌ Error during research: {e}")
        if verbose:
            import traceback
            traceback.print_exc()


async def main(
    query: Optional[str] = None,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    verbose: bool = False,
    enable_thinking: bool = False,
    deep_research: bool = False,
    max_iterations: Optional[int] = None,
    max_concurrent: Optional[int] = None,
    max_tool_calls: Optional[int] = None,
    skip_clarify: bool = False,
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
        model_provider: LLM provider ('aliyun', 'anthropic', or 'openai'). Resolved from
                       CLI > env MODEL_PROVIDER > default ('aliyun').
        model_name: Specific model name (e.g., 'qwen-max', 'kimi-k2-thinking'). Resolved
                    from CLI > env MODEL_NAME > provider defaults.
        verbose: If True, prints detailed execution logs including tool calls.
        enable_thinking: If True, enables thinking mode for supported models
                        (e.g., DeepSeek-v3, kimi-k2-thinking via DashScope).
                        Resolved from CLI > env ENABLE_THINKING > default (False).
        deep_research: If True, runs in Deep Research mode with supervisor-researcher
                      multi-agent architecture.
        max_iterations: Maximum supervisor iterations for Deep Research mode (default: 3).
        max_concurrent: Maximum concurrent researchers (default: 5).
        max_tool_calls: Maximum tool calls per researcher (default: 10).
        skip_clarify: If True, skips user clarification step.
    """
    # Load environment variables
    load_dotenv()

    # Resolve model settings with precedence CLI > env > defaults
    try:
        model_settings = get_model_settings(
            provider_override=model_provider,
            model_name_override=model_name,
            enable_thinking_override=enable_thinking,
        )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    resolved_provider = model_settings["provider"]
    resolved_model_name = model_settings["model_name"]
    resolved_enable_thinking = model_settings["enable_thinking"]

    # Check for required API keys based on provider
    if resolved_provider == "aliyun":
        if not (os.getenv("ALIYUN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")):
            print("Error: ALIYUN_API_KEY or DASHSCOPE_API_KEY environment variable not set")
            print("Please set it in your .env file or environment")
            sys.exit(1)
    elif resolved_provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it in your .env file or environment")
        sys.exit(1)
    elif resolved_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set it in your .env file or environment")
        sys.exit(1)
    elif resolved_provider == "openrouter" and not os.getenv("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY environment variable not set")
        print("Please set it in your .env file or environment")
        sys.exit(1)

    # Resolve max iterations for deep research
    resolved_max_iterations = get_max_iterations(max_iterations)
    resolved_max_concurrent = get_max_concurrent_researchers(max_concurrent)
    resolved_max_tool_calls = get_max_tool_calls(max_tool_calls)
    resolved_allow_clarification = get_allow_clarification(not skip_clarify if skip_clarify else None)

    print("=" * 60)
    mode_str = "Deep Research Mode" if deep_research else "Research Agent"
    print(f"{mode_str} - Powered by {'LangGraph' if deep_research else 'DeepAgents'}")
    thinking_str = " | Thinking: ON" if resolved_enable_thinking else ""
    deep_str = f" | Max Iter: {resolved_max_iterations} | Concurrent: {resolved_max_concurrent}" if deep_research else ""
    print(f"Provider: {resolved_provider} | Model: {resolved_model_name or 'default'}{thinking_str}{deep_str}")
    print("=" * 60)

    # Initialize MCP tools (per server)
    mcp_ctx = await initialize_mcp_tools()

    # Deep Research Mode
    if deep_research:
        if not query:
            # Interactive mode for deep research - get query first
            print("\n🔬 Deep Research Mode - Enter your research query:")
            try:
                query = input("\n📚 Research Query: ").strip()
                if not query:
                    print("No query provided. Exiting.")
                    return
            except (KeyboardInterrupt, EOFError):
                print("\n\nGoodbye!")
                return

        try:
            await main_deep_research(
                query=query,
                mcp_ctx=mcp_ctx,
                model_provider=resolved_provider,
                model_name=resolved_model_name,
                max_iterations=resolved_max_iterations,
                max_concurrent=resolved_max_concurrent,
                max_tool_calls=resolved_max_tool_calls,
                allow_clarification=resolved_allow_clarification,
                verbose=verbose,
            )
        finally:
            await mcp_ctx.cleanup()
        return

    # Standard Research Agent Mode
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
        model_provider=resolved_provider,
        model_name=resolved_model_name,
        checkpointer=checkpointer,
        store=store,
        debug=verbose,
        enable_thinking=resolved_enable_thinking,
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
                enable_thinking=resolved_enable_thinking,
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

                    # Use streaming to show execution progress with token-level output
                    display = StreamDisplay(verbose=verbose)
                    final_content = ""

                    # Mixed mode streaming: updates for tool calls, messages for tokens
                    async for mode, chunk in run_research_stream(
                        query=user_input,
                        agent=agent,
                        thread_id=thread_id,
                    ):
                        result = display.process_stream_chunk(mode, chunk)
                        if result:
                            final_content = result

                    # Show final content separator (content already printed via streaming)
                    print("\n" + "-" * 60)
                    if final_content:
                        # Content was already streamed, just show separator
                        pass
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
        default=None,
        choices=["aliyun", "anthropic", "openai", "openrouter"],
        help="LLM provider to use (default: env MODEL_PROVIDER or 'aliyun')",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name to use (default: env MODEL_NAME or provider default; e.g., 'qwen-max', 'kimi-k2-thinking', 'deepseek-v3.2' for aliyun)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose mode to show detailed execution logs (tool calls, agent steps)",
    )
    parser.add_argument(
        "--enable-thinking",
        action="store_true",
        help="Enable thinking mode for supported models (CLI overrides env ENABLE_THINKING)",
    )
    parser.add_argument(
        "--deep-research",
        action="store_true",
        help="Enable Deep Research mode with supervisor-researcher multi-agent architecture",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum supervisor iterations for Deep Research mode (default: 3)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help="Maximum concurrent researchers for Deep Research mode (default: 5)",
    )
    parser.add_argument(
        "--max-tool-calls",
        type=int,
        default=None,
        help="Maximum tool calls per researcher (default: 10)",
    )
    parser.add_argument(
        "--skip-clarify",
        action="store_true",
        help="Skip user clarification step in Deep Research mode",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            query=args.query,
            model_provider=args.model_provider,
            model_name=args.model,
            verbose=args.verbose,
            enable_thinking=args.enable_thinking,
            deep_research=args.deep_research,
            max_iterations=args.max_iterations,
            max_concurrent=args.max_concurrent,
            max_tool_calls=args.max_tool_calls,
            skip_clarify=args.skip_clarify,
        )
    )


if __name__ == "__main__":
    run_cli()
