"""Agent service - Bridge between API and research agent."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any, Optional

import httpcore
import httpx

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from src.agent.research_agent import (
    create_research_agent,
    run_research_async,
    run_research_stream,
)
from src.api.schemas.chat import (
    ModelInfo,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolCallStatus,
)
from src.config.llm_factory import ALIYUN_MODELS


class AgentService:
    """Service for managing research agent instances and streaming."""

    def __init__(self):
        """Initialize the agent service."""
        self._agents: dict[str, Any] = {}  # conversation_id -> agent
        self._checkpointers: dict[str, MemorySaver] = {}
        self._stores: dict[str, InMemoryStore] = {}
        self._agent_configs: dict[str, tuple[str, Optional[str]]] = {}
        self._hn_mcp_tools: Optional[list] = None

    def set_mcp_tools(self, hn_mcp_tools: Optional[list]) -> None:
        """Set MCP tools for agents."""
        self._hn_mcp_tools = hn_mcp_tools

    def _get_or_create_agent(
        self,
        conversation_id: str,
        model_provider: str = "aliyun",
        model_name: Optional[str] = None,
    ) -> Any:
        """Get existing agent or create a new one for the conversation."""
        requested_provider = model_provider or "aliyun"
        requested_model = model_name

        checkpointer = self._checkpointers.get(conversation_id)
        store = self._stores.get(conversation_id)

        if checkpointer is None:
            checkpointer = MemorySaver()
            self._checkpointers[conversation_id] = checkpointer
        if store is None:
            store = InMemoryStore()
            self._stores[conversation_id] = store

        cached_agent = self._agents.get(conversation_id)
        cached_config = self._agent_configs.get(conversation_id)

        if cached_agent and cached_config == (requested_provider, requested_model):
            print(f"Using existing agent for conversation {conversation_id}")
            return cached_agent

        if cached_agent:
            print(
                f"Recreating agent for conversation {conversation_id} due to model/provider change: "
                f"{cached_config} -> {(requested_provider, requested_model)}"
            )

        try:
            agent = create_research_agent(
                hn_mcp_tools=self._hn_mcp_tools,
                model_provider=requested_provider,
                model_name=requested_model,
                checkpointer=checkpointer,
                store=store,
                debug=False,
            )
            print(f"Agent ready for conversation {conversation_id} with provider={requested_provider}, model={requested_model}")
            self._agents[conversation_id] = agent
            self._agent_configs[conversation_id] = (requested_provider, requested_model)
            return agent
        except Exception as e:
            print(f"ERROR creating agent: {e}")
            import traceback
            print(traceback.format_exc())
            raise

    def remove_agent(self, conversation_id: str) -> None:
        """Remove agent instance for a conversation."""
        self._agents.pop(conversation_id, None)
        self._checkpointers.pop(conversation_id, None)
        self._stores.pop(conversation_id, None)
        self._agent_configs.pop(conversation_id, None)

    @staticmethod
    def _is_stream_disconnect_error(exc: Exception) -> bool:
        """Return True when upstream closes streaming response early."""
        if isinstance(exc, (httpx.RemoteProtocolError, httpcore.RemoteProtocolError)):
            return True

        message = str(exc).lower()
        if "incomplete chunked read" in message or "peer closed connection" in message:
            return True

        cause = getattr(exc, "__cause__", None)
        if cause and isinstance(cause, (httpx.RemoteProtocolError, httpcore.RemoteProtocolError)):
            return True

        return False

    async def stream_response(
        self,
        conversation_id: str,
        message: str,
        model_provider: str = "aliyun",
        model_name: Optional[str] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream agent response as events.

        Yields StreamEvent objects that can be serialized and sent to clients.
        Each request is independent - no cross-request state tracking needed.
        """
        agent = self._get_or_create_agent(conversation_id, model_provider, model_name)

        # Get existing tool call IDs from checkpoint BEFORE streaming
        # This prevents historical tool calls from being sent as new ones
        config = {"configurable": {"thread_id": conversation_id}}
        existing_tool_ids: set[str] = set()
        try:
            state = agent.get_state(config)
            if state and state.values:
                for msg in state.values.get("messages", []):
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_id = tc.get("id", "")
                            if tool_id:
                                existing_tool_ids.add(tool_id)
            if existing_tool_ids:
                print(f"Found {len(existing_tool_ids)} existing tool calls in checkpoint")
        except Exception as e:
            # Graceful fallback if state retrieval fails
            print(f"Warning: Could not retrieve checkpoint state: {e}")

        # Track tool calls for this response only
        active_tool_calls: dict[str, ToolCall] = {}
        seen_tool_ids: set[str] = existing_tool_ids.copy()  # Start with existing IDs
        tool_call_counter = 0

        try:
            async for mode, chunk in run_research_stream(
                query=message,
                agent=agent,
                thread_id=conversation_id,
            ):
                if mode == "messages":
                    # Token streaming - only forward AI messages to avoid leaking tool output
                    message_chunk, metadata = chunk
                    if not isinstance(message_chunk, AIMessage):
                        # Skip tool/system messages to prevent raw tool output from reaching UI
                        continue

                    if hasattr(message_chunk, "content") and message_chunk.content:
                        content = message_chunk.content
                        # Handle string content
                        if isinstance(content, str) and content:
                            yield StreamEvent(
                                type=StreamEventType.TOKEN,
                                data={"content": content},
                            )
                        # Handle list content (e.g., thinking blocks)
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get("type") == "thinking":
                                        yield StreamEvent(
                                            type=StreamEventType.THINKING,
                                            data={"content": item.get("thinking", "")},
                                        )
                                    elif item.get("type") == "text":
                                        yield StreamEvent(
                                            type=StreamEventType.TOKEN,
                                            data={"content": item.get("text", "")},
                                        )

                elif mode == "updates":
                    # Node updates - extract tool calls
                    for node_name, node_data in chunk.items():
                        if node_data is None:
                            continue

                        messages = node_data.get("messages", [])

                        # Handle LangGraph's Overwrite object
                        if hasattr(messages, "value"):
                            messages = messages.value

                        # Ensure messages is iterable
                        if not isinstance(messages, (list, tuple)):
                            continue

                        for msg in messages:
                            # Check for tool calls in AI messages
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    tool_id = tc.get("id", f"tc_{tool_call_counter}")
                                    
                                    # Skip duplicates within this request
                                    if tool_id in seen_tool_ids:
                                        continue
                                    
                                    seen_tool_ids.add(tool_id)
                                    tool_call_counter += 1

                                    tool_call = ToolCall(
                                        id=tool_id,
                                        name=tc.get("name", "unknown"),
                                        args=tc.get("args", {}),
                                        status=ToolCallStatus.RUNNING,
                                    )
                                    active_tool_calls[tool_id] = tool_call

                                    yield StreamEvent(
                                        type=StreamEventType.TOOL_CALL_START,
                                        data=tool_call.model_dump(),
                                    )

                            # Check for tool results
                            if hasattr(msg, "type") and msg.type == "tool":
                                tool_id = getattr(msg, "tool_call_id", None)
                                if tool_id and tool_id in active_tool_calls:
                                    tool_call = active_tool_calls[tool_id]
                                    tool_call.status = ToolCallStatus.COMPLETED
                                    tool_call.result = (
                                        msg.content[:500] if msg.content else ""
                                    )  # Truncate for display

                                    yield StreamEvent(
                                        type=StreamEventType.TOOL_CALL_END,
                                        data=tool_call.model_dump(),
                                    )

            # Signal completion
            yield StreamEvent(
                type=StreamEventType.MESSAGE_COMPLETE,
                data={
                    "tool_calls": [tc.model_dump() for tc in active_tool_calls.values()]
                },
            )

        except Exception as e:
            import traceback

            if self._is_stream_disconnect_error(e):
                print(
                    "WARNING: Streaming connection closed early; "
                    "retrying with non-streaming response."
                )
                
                # Retry with exponential backoff for transient connection errors
                max_retries = 3
                base_delay = 1.0  # seconds
                
                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            delay = base_delay * (2 ** (attempt - 1))  # 1s, 2s, 4s
                            print(f"Retry attempt {attempt + 1}/{max_retries} after {delay}s delay...")
                            await asyncio.sleep(delay)
                        
                        final_text = await run_research_async(
                            query=message,
                            agent=agent,
                            thread_id=conversation_id,
                        )
                        if final_text:
                            yield StreamEvent(
                                type=StreamEventType.TOKEN,
                                data={"content": final_text},
                            )
                        yield StreamEvent(
                            type=StreamEventType.MESSAGE_COMPLETE,
                            data={
                                "tool_calls": [
                                    tc.model_dump()
                                    for tc in active_tool_calls.values()
                                ]
                            },
                        )
                        return  # Success, exit retry loop
                        
                    except Exception as fallback_error:
                        is_retryable = self._is_stream_disconnect_error(fallback_error)
                        
                        if is_retryable and attempt < max_retries - 1:
                            print(f"Retry {attempt + 1} failed with retryable error: {fallback_error}")
                            continue  # Try again
                        
                        # Final attempt failed or non-retryable error
                        error_msg = (
                            f"{str(fallback_error)}\n{traceback.format_exc()}"
                        )
                        print(f"ERROR in non-streaming fallback (attempt {attempt + 1}): {error_msg}")
                        break  # Exit retry loop, fall through to error handling

            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"ERROR in agent stream: {error_msg}")
            yield StreamEvent(
                type=StreamEventType.ERROR,
                data={"message": str(e)},
            )

    def get_available_models(self) -> list[ModelInfo]:
        """Get list of available models."""
        models = []

        # Aliyun models
        for name in ALIYUN_MODELS.keys():
            models.append(
                ModelInfo(
                    provider="aliyun",
                    name=name,
                    display_name=f"Aliyun {name}",
                    supports_thinking=name in ["qwen-max", "qwen3-max", "kimi-k2-thinking", "deepseek-v3.2"],
                )
            )

        # OpenRouter models
        models.append(
            ModelInfo(
                provider="openrouter",
                name="anthropic/claude-sonnet-4.5",
                display_name="Claude Sonnet 4.5 (OpenRouter)",
                supports_thinking=False,
            )
        )

        return models


# Singleton instance
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """Get the agent service singleton."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
