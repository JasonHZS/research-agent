"""
Research Agent Implementation

This module implements a deep research agent using DeepAgents library.
The agent can perform comprehensive research using ArXiv, Hacker News,
and Hugging Face daily papers with built-in planning and file management.

Architecture:
- Main Agent (Coordinator): Handles discovery and planning with search tools
- Content Reader Agent: Handles deep reading and summarization of content

This separation protects the main agent's context window by delegating
heavy content consumption to the sub-agent.

Multi-turn Conversation Support:
- Use checkpointer (e.g., MemorySaver) to persist conversation state
- Use store (e.g., InMemoryStore) with CompositeBackend for file persistence
- Pass thread_id in config to maintain conversation context across turns
"""

import os
from collections.abc import AsyncGenerator
from datetime import date
from typing import Any, Optional

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from src.agent.subagents import (
    create_content_reader_subagent,
    get_main_agent_tools,
)
from src.config.llm_config import get_model_settings
from src.config.reader_config import get_reader_type
from src.prompts import load_prompt
from src.tools.arxiv_api import get_arxiv_paper_tool, search_arxiv_papers_tool
from src.tools.hf_blog import get_huggingface_blog_posts_tool
from src.tools.hf_daily_papers import get_huggingface_papers_tool
from src.tools.zyte_reader import get_zyte_article_list_tool
from src.tools.bocha_search import bocha_web_search_tool
from src.tools.github_search import github_search_tool

# Available models on Aliyun DashScope
ALIYUN_MODELS = {
    "qwen-max": "qwen-max",
    "kimi-k2-thinking": "kimi-k2-thinking",
    "deepseek-v3.2": "deepseek-v3.2",
}

DEFAULT_ALIYUN_MODEL = "qwen-max"


def _get_model_config(
    model_provider: str = "aliyun",
    model_name: Optional[str] = None,
    enable_thinking: bool = False,
) -> dict[str, Any]:
    """
    Get model configuration for the specified provider.

    Args:
        model_provider: One of 'aliyun', 'anthropic', or 'openai'.
        model_name: Specific model name.
        enable_thinking: Whether to enable thinking mode (only supported by some models
                        like qwen-max,DeepSeek-v3.2, kimi-k2-thinking via DashScope).

    Returns:
        Dictionary with model configuration for deepagents.
        For providers with custom endpoints (aliyun), returns a ChatOpenAI instance
        in the 'model' key. For standard providers, returns just the model name.
    """
    if model_provider == "aliyun":
        base_url = os.getenv(
            "ALIYUN_API_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        api_key = os.getenv("ALIYUN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")

        if not api_key:
            raise ValueError(
                "ALIYUN_API_KEY or DASHSCOPE_API_KEY environment variable not set"
            )

        resolved_model = model_name
        if model_name in ALIYUN_MODELS:
            resolved_model = ALIYUN_MODELS[model_name]
        elif model_name is None:
            resolved_model = ALIYUN_MODELS[DEFAULT_ALIYUN_MODEL]

        # Build extra_body for enable_thinking support
        extra_body = {"enable_thinking": True} if enable_thinking else None

        # Create ChatOpenAI instance for custom API endpoints
        # deepagents' create_deep_agent accepts BaseChatModel directly
        # streaming=True ensures the underlying API call uses stream=True
        # which is required for token-level streaming output
        llm = ChatOpenAI(
            model=resolved_model,
            api_key=api_key,
            base_url=base_url,
            extra_body=extra_body,
            streaming=True,
        )
        return {"model": llm}
    elif model_provider == "anthropic":
        return {
            "model": model_name or "claude-sonnet-4-20250514",
        }
    elif model_provider == "openai":
        return {
            "model": model_name or "gpt-4o",
        }
    else:
        raise ValueError(f"Unknown model provider: {model_provider}")


def create_research_agent(
    hn_mcp_tools: Optional[list] = None,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
    prompt_template: str = "research_agent",
    checkpointer: Optional[BaseCheckpointSaver] = None,
    store: Optional[BaseStore] = None,
    debug: bool = False,
    enable_thinking: bool = False,
) -> Any:
    """
    Create a deep research agent with planning and subagent capabilities.

    Architecture:
    - Main Agent: Coordinator with search/discovery tools
        - Tools: HF papers list, ArXiv search/paper (native), HN stories
    - Content Reader Sub-agent: Deep reading and summarization
        - Tools: Configurable reader (default Zyte, switchable via CONTENT_READER_TYPE)

    This separation ensures:
    1. Main agent's context stays clean (only summaries, not raw content)
    2. Clear separation of concerns (discovery vs consumption)
    3. Better planning capabilities for the main agent

    Multi-turn Conversation:
    - Pass checkpointer to persist conversation state across turns
    - Pass store to enable persistent file storage via FilesystemMiddleware
    - Use thread_id in config when invoking the agent

    Note on Persistence:
    - Using MemorySaver as checkpointer keeps history in RAM only (lost on exit).
    - For disk persistence (across restarts), use SqliteSaver or PostgresSaver.

    Args:
        hn_mcp_tools: Hacker News MCP tools (will be split between main/sub agent).
        model_provider: LLM provider ('anthropic', 'openai', or 'aliyun').
                        Resolved via CLI/env/defaults using llm_config when not set.
        model_name: Specific model to use. Resolved via CLI/env/defaults when not set.
        system_prompt: Custom system prompt. If provided, overrides prompt_template.
        prompt_template: Name of the prompt template to use (without .md extension).
                        Defaults to 'research_agent'. Edit the template file directly
                        at src/prompts/templates/<template_name>.md to modify prompts.
        checkpointer: Checkpointer for persisting conversation state (e.g., MemorySaver).
                     Required for multi-turn conversations.
        store: Store for persistent file storage (e.g., InMemoryStore).
              When provided, enables /memories/ path for long-term storage.
        debug: If True, enables debug mode with detailed execution logs.
              Uses DeepAgents built-in debug streaming.
        enable_thinking: If True, enables thinking mode for supported models
                        (e.g., DeepSeek-v3, kimi-k2-thinking via DashScope).
                        The model will show its reasoning process.

    Returns:
        Configured DeepAgent instance with subagents.

    Example:
        >>> from langgraph.checkpoint.memory import MemorySaver
        >>> from langgraph.store.memory import InMemoryStore
        >>>
        >>> checkpointer = MemorySaver()
        >>> store = InMemoryStore()
        >>> agent = create_research_agent(
        ...     hn_mcp_tools=hn_tools,
        ...     checkpointer=checkpointer,
        ...     store=store,
        ... )
        >>> # Invoke with thread_id for multi-turn conversation
        >>> result = agent.invoke(
        ...     {"messages": [{"role": "user", "content": "..."}]},
        ...     config={"configurable": {"thread_id": "session_123"}}
        ... )
    """
    # Create Content Reader subagent with reading tools
    content_reader = create_content_reader_subagent()
    subagents = [content_reader]

    # Build main agent tools: Discovery/Search tools + ArXiv tools
    # Main agent gets: HF papers list + ArXiv tools (native) + HN discovery tools + Blog article list
    main_tools = [
        get_huggingface_papers_tool,
        get_huggingface_blog_posts_tool,
        get_arxiv_paper_tool,
        search_arxiv_papers_tool,
        get_zyte_article_list_tool,  # Fetch article list from any blog/news site
        bocha_web_search_tool,  # General web search
        github_search_tool,  # Search GitHub repos, issues, commits (no auth)
    ]

    # Add discovery tools from HN MCP (getTopStories, getBestStories, etc.)
    hn_main_tools = get_main_agent_tools(hn_mcp_tools)
    if hn_main_tools:
        main_tools.extend(hn_main_tools)

    # Resolve model settings (CLI > env > defaults)
    try:
        model_settings = get_model_settings(
            provider_override=model_provider,
            model_name_override=model_name,
            enable_thinking_override=enable_thinking,
        )
    except ValueError as e:
        raise ValueError(f"Invalid model configuration: {e}") from e

    resolved_provider = model_settings["provider"]
    resolved_model_name = model_settings["model_name"]
    resolved_enable_thinking = model_settings["enable_thinking"]

    # Get model configuration
    model_config = _get_model_config(resolved_provider, resolved_model_name, resolved_enable_thinking)

    # Load the system prompt from template with reader type and current date
    if system_prompt is None:
        reader_type = get_reader_type()
        current_date = date.today().strftime("%Y-%m-%d")
        system_prompt = load_prompt(
            prompt_template,
            reader_type=reader_type.value,
            current_date=current_date,
        )

    # Configure backend for persistent file storage
    # When store is provided, use CompositeBackend to route /memories/ to StoreBackend
    # Note: Use 'backend' param instead of 'middleware' to avoid duplicate FilesystemMiddleware
    backend = None
    if store is not None:
        backend = lambda rt: CompositeBackend(
            default=StateBackend(rt),
            routes={"/memories/": StoreBackend(rt)}
        )

    # Create the deep agent with tools, subagents, and persistence
    agent = create_deep_agent(
        tools=main_tools,
        system_prompt=system_prompt,
        subagents=subagents,
        checkpointer=checkpointer,
        store=store,
        backend=backend,
        debug=debug,
        **model_config,
    )

    return agent


def run_research(
    query: str,
    hn_mcp_tools: Optional[list] = None,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    agent: Optional[Any] = None,
    thread_id: Optional[str] = None,
    enable_thinking: bool = False,
) -> str:
    """
    Run a research query using the deep research agent.

    This is a convenience function that creates the agent and runs a single query.
    The agent will automatically:
    1. Plan its approach using write_todos
    2. Search and discover relevant resources
    3. Delegate deep reading to Content Reader sub-agent
    4. Synthesize findings into a coherent report

    For multi-turn conversations, pass an existing agent instance and thread_id.

    Args:
        query: The research question or topic to investigate.
        hn_mcp_tools: Hacker News MCP tools for web content.
        model_provider: LLM provider to use ('anthropic', 'openai', or 'aliyun').
                        Resolved via CLI/env/defaults when not set.
        model_name: Specific model name. Resolved via CLI/env/defaults when not set.
        agent: Pre-created agent instance (for multi-turn conversations).
              If None, a new agent will be created.
        thread_id: Unique thread identifier for multi-turn conversations.
                  Required when using checkpointer for state persistence.
        enable_thinking: If True, enables thinking mode for supported models.

    Returns:
        The agent's final response as a string.
    """
    if agent is None:
        agent = create_research_agent(
            hn_mcp_tools=hn_mcp_tools,
            model_provider=model_provider,
            model_name=model_name,
            enable_thinking=enable_thinking,
        )

    # Build config with thread_id for multi-turn support
    config = {}
    if thread_id:
        config = {"configurable": {"thread_id": thread_id}}

    result = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        config=config if config else None,
    )
    # Extract the final response
    final_message = result["messages"][-1]
    if hasattr(final_message, "content"):
        return final_message.content
    return str(final_message)


async def run_research_async(
    query: str,
    hn_mcp_tools: Optional[list] = None,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    agent: Optional[Any] = None,
    thread_id: Optional[str] = None,
    enable_thinking: bool = False,
) -> str:
    """
    Run a research query asynchronously using the deep research agent.

    For multi-turn conversations, pass an existing agent instance and thread_id.

    Args:
        query: The research question or topic to investigate.
        hn_mcp_tools: Hacker News MCP tools for web content.
        model_provider: LLM provider to use ('anthropic', 'openai', or 'aliyun').
                        Resolved via CLI/env/defaults when not set.
        model_name: Specific model name. Resolved via CLI/env/defaults when not set.
        agent: Pre-created agent instance (for multi-turn conversations).
              If None, a new agent will be created.
        thread_id: Unique thread identifier for multi-turn conversations.
                  Required when using checkpointer for state persistence.
        enable_thinking: If True, enables thinking mode for supported models.

    Returns:
        The agent's final response as a string.
    """
    if agent is None:
        agent = create_research_agent(
            hn_mcp_tools=hn_mcp_tools,
            model_provider=model_provider,
            model_name=model_name,
            enable_thinking=enable_thinking,
        )

    # Build config with thread_id for multi-turn support
    config = {}
    if thread_id:
        config = {"configurable": {"thread_id": thread_id}}

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": query}]},
        config=config if config else None,
    )
    final_message = result["messages"][-1]
    if hasattr(final_message, "content"):
        return final_message.content
    return str(final_message)


async def run_research_stream(
    query: str,
    agent: Any,
    thread_id: Optional[str] = None,
) -> AsyncGenerator[tuple[str, Any], None]:
    """
    Stream research query execution with token-level streaming.

    This function uses LangGraph's streaming API with mixed mode to yield:
    - "updates": Node completion events (tool calls, tool results)
    - "messages": Token-level LLM output chunks for real-time display

    Args:
        query: The research question or topic to investigate.
        agent: Pre-created agent instance (required).
        thread_id: Unique thread identifier for multi-turn conversations.

    Yields:
        Tuple of (mode, chunk) where:
        - mode: "updates" or "messages"
        - chunk: For "updates", dict with {node_name: {messages: [...]}}
                 For "messages", tuple of (message_chunk, metadata)

    Example:
        >>> async for mode, chunk in run_research_stream(query, agent, thread_id):
        ...     if mode == "updates":
        ...         # Handle node updates (tool calls, results)
        ...         pass
        ...     elif mode == "messages":
        ...         # Handle token-level streaming
        ...         message_chunk, metadata = chunk
        ...         print(message_chunk.content, end="", flush=True)
    """
    # Build config with thread_id for multi-turn support
    config = {}
    if thread_id:
        config = {"configurable": {"thread_id": thread_id}}

    # Use mixed mode: "updates" for tool calls, "messages" for token streaming
    async for mode, chunk in agent.astream(
        {"messages": [{"role": "user", "content": query}]},
        config=config if config else None,
        stream_mode=["updates", "messages"],
    ):
        yield (mode, chunk)
