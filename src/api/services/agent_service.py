"""Agent service - Bridge between API and research agent."""

import asyncio
import json
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
from src.deep_research.graph import build_deep_research_graph
from src.deep_research.state import ClarificationStatus, Section
from src.api.schemas.chat import (
    ModelInfo,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolCallStatus,
)
from src.config.deep_research_config import get_max_concurrent_researchers
from src.config.llm_factory import ALIYUN_MODELS, OPENROUTER_MODELS


class AgentService:
    """Service for managing research agent instances and streaming."""

    def __init__(self):
        """Initialize the agent service."""
        self._agents: dict[str, Any] = {}  # conversation_id -> agent
        self._checkpointers: dict[tuple[str, bool], MemorySaver] = {}
        self._stores: dict[tuple[str, bool], InMemoryStore] = {}
        self._agent_configs: dict[str, tuple[str, Optional[str], bool]] = {}
        self._hn_mcp_tools: Optional[list] = None

    def set_mcp_tools(self, hn_mcp_tools: Optional[list]) -> None:
        """Set MCP tools for agents."""
        self._hn_mcp_tools = hn_mcp_tools

    def _get_or_create_agent(
        self,
        conversation_id: str,
        model_provider: str = "aliyun",
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
    ) -> Any:
        """Get existing agent or create a new one for the conversation."""
        requested_provider = model_provider or "aliyun"
        requested_model = model_name
        
        state_key = (conversation_id, is_deep_research)
        checkpointer = self._checkpointers.get(state_key)
        store = self._stores.get(state_key)

        if checkpointer is None:
            checkpointer = MemorySaver()
            self._checkpointers[state_key] = checkpointer
        if store is None:
            store = InMemoryStore()
            self._stores[state_key] = store

        cached_agent = self._agents.get(conversation_id)
        cached_config = self._agent_configs.get(conversation_id)

        # Check if we can reuse existing agent
        # cached_config is now (provider, model, is_deep_research)
        if cached_agent and cached_config == (requested_provider, requested_model, is_deep_research):
            print(f"Using existing agent for conversation {conversation_id}")
            return cached_agent

        if cached_agent:
            print(
                f"Recreating agent for conversation {conversation_id} due to config change: "
                f"{cached_config} -> {(requested_provider, requested_model, is_deep_research)}"
            )

        try:
            if is_deep_research:
                print(f"Creating Deep Research agent for {conversation_id}")
                agent = build_deep_research_graph(
                    hn_mcp_tools=self._hn_mcp_tools,
                    model_provider=requested_provider,
                    model_name=requested_model,
                    checkpointer=checkpointer,
                    store=store,
                )
            else:
                agent = create_research_agent(
                    hn_mcp_tools=self._hn_mcp_tools,
                    model_provider=requested_provider,
                    model_name=requested_model,
                    checkpointer=checkpointer,
                    store=store,
                    debug=False,
                )
            
            print(f"Agent ready for conversation {conversation_id} with provider={requested_provider}, model={requested_model}, deep_research={is_deep_research}")
            self._agents[conversation_id] = agent
            self._agent_configs[conversation_id] = (requested_provider, requested_model, is_deep_research)
            return agent
        except Exception as e:
            print(f"ERROR creating agent: {e}")
            import traceback
            print(traceback.format_exc())
            raise

    def remove_agent(self, conversation_id: str) -> None:
        """Remove agent instance for a conversation."""
        self._agents.pop(conversation_id, None)
        for mode in (False, True):
            self._checkpointers.pop((conversation_id, mode), None)
            self._stores.pop((conversation_id, mode), None)
        self._agent_configs.pop(conversation_id, None)

    @staticmethod
    def _format_tool_result(content: Any, max_len: int = 500) -> str:
        """Normalize tool result to a short, display-friendly string."""
        if content is None:
            return ""
        if isinstance(content, str):
            text = content
        else:
            try:
                text = json.dumps(content, ensure_ascii=False, default=str)
            except TypeError:
                text = str(content)
        return text[:max_len] if max_len and len(text) > max_len else text

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


    @staticmethod
    def _extract_messages_recursive(data: Any, max_depth: int = 5) -> list:
        """
        Recursively extract messages from nested node data.

        This handles subgraph updates where data may be nested like:
        {"researcher": {"researcher": {"researcher_messages": [...]}}}

        Looks for these fields:
        - messages: standard LangGraph messages
        - researcher_messages: from researcher subgraph
        - tool_calls_log: from clarify node's internal tool calls

        Args:
            data: Node data (dict or nested structure)
            max_depth: Maximum recursion depth to prevent infinite loops

        Returns:
            List of message objects containing tool calls
        """
        if max_depth <= 0 or data is None:
            return []

        # Handle LangGraph's Overwrite object
        if hasattr(data, "value"):
            data = data.value

        if not isinstance(data, dict):
            return []

        all_messages = []
        message_fields = ["messages", "researcher_messages", "tool_calls_log"]

        for key, value in data.items():
            # Handle Overwrite wrapper
            if hasattr(value, "value"):
                value = value.value

            if key in message_fields:
                # Found a message field - extract messages
                if isinstance(value, (list, tuple)):
                    all_messages.extend(value)
            elif isinstance(value, dict):
                # Recurse into nested dicts (subgraph updates)
                all_messages.extend(
                    AgentService._extract_messages_recursive(value, max_depth - 1)
                )

        return all_messages

    async def stream_response(
        self,
        conversation_id: str,
        message: str,
        model_provider: str = "aliyun",
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream agent response as events.

        Yields StreamEvent objects that can be serialized and sent to clients.
        Each request is independent - no cross-request state tracking needed.
        """
        agent = self._get_or_create_agent(
            conversation_id, 
            model_provider, 
            model_name,
            is_deep_research=is_deep_research
        )

        # Get existing tool call IDs from checkpoint BEFORE streaming
        # This prevents historical tool calls from being sent as new ones
        config = {"configurable": {"thread_id": conversation_id}}
        existing_tool_ids: set[str] = set()
        try:
            state = agent.get_state(config)
            if state and state.values:
                existing_messages = self._extract_messages_recursive(state.values)
                for msg in existing_messages:
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
        
        # For Deep Research: track clarification status and brief from state updates
        clarification_sent = False
        brief_sent = False

        extra_config = None
        max_concurrency = None
        log_tool_calls = False
        completed_tool_ids: set[str] = set()

        try:
            # For Deep Research: enable verbose mode to print tool calls in backend
            if is_deep_research:
                extra_config = {
                    "verbose": True,
                    "model_provider": model_provider,
                    "model_name": model_name,
                }
                max_concurrency = get_max_concurrent_researchers()
            log_tool_calls = bool(extra_config and extra_config.get("verbose"))
            
            async for mode, chunk in run_research_stream(
                query=message,
                agent=agent,
                thread_id=conversation_id,
                extra_config=extra_config,
                max_concurrency=max_concurrency,
            ):
                if mode == "messages":
                    # Token streaming - only forward AI messages to avoid leaking tool output
                    message_chunk, metadata = chunk
                    if not isinstance(message_chunk, AIMessage):
                        # Skip tool/system messages to prevent raw tool output from reaching UI
                        continue
                    
                    # For Deep Research: only allow tokens from specific nodes
                    # Use whitelist approach - only final_report text should be displayed:
                    # - final_report: The main research report (displayed to user)
                    # All other nodes are filtered:
                    # - clarify, analyze, plan_sections, review: structured JSON output
                    # - researcher, researcher_tools, compress_output: subgraph internal reasoning
                    # - discover, discover_tools, extract_output: subgraph internal reasoning
                    # - aggregate: utility node with debug logs
                    if is_deep_research:
                        current_node = metadata.get("langgraph_node", "")
                        allowed_text_nodes = {"final_report"}
                        if current_node not in allowed_text_nodes:
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
                    # Node updates - extract tool calls and clarification status
                    for node_name, node_data in chunk.items():
                        if node_data is None:
                            continue
                        tool_calls_log = node_data.get("tool_calls_log") if isinstance(node_data, dict) else None
                        if hasattr(tool_calls_log, "value"):
                            tool_calls_log = tool_calls_log.value

                        # For Deep Research: check clarification_status field directly
                        # This is set by the clarify node via Command API
                        if is_deep_research and not clarification_sent:
                            clarification_status = node_data.get("clarification_status")
                            # Handle LangGraph's Overwrite object
                            if hasattr(clarification_status, "value"):
                                clarification_status = clarification_status.value
                            
                            if clarification_status is not None:
                                # Check if it's a ClarificationStatus instance or dict
                                need_clarification = False
                                question = ""
                                verification = ""
                                
                                if isinstance(clarification_status, ClarificationStatus):
                                    need_clarification = clarification_status.need_clarification
                                    question = clarification_status.question
                                    verification = clarification_status.verification
                                elif isinstance(clarification_status, dict):
                                    need_clarification = clarification_status.get("need_clarification", False)
                                    question = clarification_status.get("question", "")
                                    verification = clarification_status.get("verification", "")
                                
                                if need_clarification and question:
                                    # Need clarification: send clarification event
                                    yield StreamEvent(
                                        type=StreamEventType.CLARIFICATION,
                                        data={"question": question},
                                    )
                                    clarification_sent = True
                                elif not need_clarification and verification:
                                    # No clarification needed: send verification message as TOKEN
                                    yield StreamEvent(
                                        type=StreamEventType.TOKEN,
                                        data={"content": verification},
                                    )

                        # For Deep Research: check for research_brief and sections (from plan_sections node)
                        if is_deep_research and not brief_sent:
                            research_brief = node_data.get("research_brief")
                            sections = node_data.get("sections")
                            
                            # Handle LangGraph's Overwrite object
                            if hasattr(research_brief, "value"):
                                research_brief = research_brief.value
                            if hasattr(sections, "value"):
                                sections = sections.value
                            
                            if research_brief and sections:
                                # Extract section info for the brief event
                                section_list = []
                                for s in sections:
                                    if isinstance(s, Section):
                                        section_list.append({
                                            "title": s.title,
                                            "description": s.description,
                                        })
                                    elif isinstance(s, dict):
                                        section_list.append({
                                            "title": s.get("title", ""),
                                            "description": s.get("description", ""),
                                        })
                                
                                if section_list:
                                    yield StreamEvent(
                                        type=StreamEventType.BRIEF,
                                        data={
                                            "research_brief": research_brief,
                                            "sections": section_list,
                                        },
                                    )
                                    brief_sent = True

                        # Extract all possible message sources containing tool calls
                        # Recursively search for message fields in nested node data
                        # (handles subgraph updates like {"researcher": {"researcher": {...}}})
                        all_messages = self._extract_messages_recursive(node_data)
                        for msg in all_messages:
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

                                    if log_tool_calls:
                                        print(
                                            f"  [Tool Call] {tool_call.name}: {tool_call.args}"
                                        )

                                    yield StreamEvent(
                                        type=StreamEventType.TOOL_CALL_START,
                                        data=tool_call.model_dump(),
                                    )

                            # Check for tool results
                            if hasattr(msg, "type") and msg.type == "tool":
                                tool_id = getattr(msg, "tool_call_id", None)
                                if (
                                    tool_id
                                    and tool_id in active_tool_calls
                                    and tool_id not in completed_tool_ids
                                ):
                                    tool_call = active_tool_calls[tool_id]
                                    tool_call.status = ToolCallStatus.COMPLETED
                                    tool_call.result = self._format_tool_result(
                                        getattr(msg, "content", None)
                                    )

                                    completed_tool_ids.add(tool_id)
                                    if log_tool_calls:
                                        print(f"  [Tool Done] {tool_call.name} ✓")

                                    yield StreamEvent(
                                        type=StreamEventType.TOOL_CALL_END,
                                        data=tool_call.model_dump(),
                                    )

            # Signal completion
            yield StreamEvent(
                type=StreamEventType.MESSAGE_COMPLETE,
                data={
                    "tool_calls": [tc.model_dump() for tc in active_tool_calls.values()],
                    "is_clarification": clarification_sent,
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
                        # Try to emit brief from state in non-streaming fallback
                        if is_deep_research and not brief_sent:
                            try:
                                fallback_state = agent.get_state(
                                    {"configurable": {"thread_id": conversation_id}}
                                )
                                if fallback_state and fallback_state.values:
                                    research_brief = fallback_state.values.get("research_brief")
                                    sections = fallback_state.values.get("sections")
                                    if hasattr(research_brief, "value"):
                                        research_brief = research_brief.value
                                    if hasattr(sections, "value"):
                                        sections = sections.value
                                    if research_brief and sections:
                                        section_list = []
                                        for s in sections:
                                            if isinstance(s, Section):
                                                section_list.append(
                                                    {
                                                        "title": s.title,
                                                        "description": s.description,
                                                    }
                                                )
                                            elif isinstance(s, dict):
                                                section_list.append(
                                                    {
                                                        "title": s.get("title", ""),
                                                        "description": s.get("description", ""),
                                                    }
                                                )
                                        if section_list:
                                            yield StreamEvent(
                                                type=StreamEventType.BRIEF,
                                                data={
                                                    "research_brief": research_brief,
                                                    "sections": section_list,
                                                },
                                            )
                                            brief_sent = True
                            except Exception:
                                pass
                        # Try to emit tool calls from state in non-streaming fallback
                        try:
                            fallback_state = agent.get_state(
                                {"configurable": {"thread_id": conversation_id}}
                            )
                            if fallback_state and fallback_state.values:
                                fallback_messages = self._extract_messages_recursive(
                                    fallback_state.values
                                )
                                for msg in fallback_messages:
                                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                                        for tc in msg.tool_calls:
                                            tool_id = tc.get("id", f"tc_{tool_call_counter}")
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
                                            if log_tool_calls:
                                                print(
                                                    "  [Tool Call] "
                                                    f"{tool_call.name}: {tool_call.args}"
                                                )
                                            yield StreamEvent(
                                                type=StreamEventType.TOOL_CALL_START,
                                                data=tool_call.model_dump(),
                                            )

                                    if hasattr(msg, "type") and msg.type == "tool":
                                        tool_id = getattr(msg, "tool_call_id", None)
                                        if (
                                            tool_id
                                            and tool_id in active_tool_calls
                                            and tool_id not in completed_tool_ids
                                        ):
                                            tool_call = active_tool_calls[tool_id]
                                            tool_call.status = ToolCallStatus.COMPLETED
                                            tool_call.result = self._format_tool_result(
                                                getattr(msg, "content", None)
                                            )
                                            completed_tool_ids.add(tool_id)
                                            if log_tool_calls:
                                                print(f"  [Tool Done] {tool_call.name} ✓")
                                            yield StreamEvent(
                                                type=StreamEventType.TOOL_CALL_END,
                                                data=tool_call.model_dump(),
                                            )
                        except Exception as fallback_state_error:
                            print(
                                "Warning: Could not emit tool calls from fallback state: "
                                f"{fallback_state_error}"
                            )
                        is_clarification = clarification_sent
                        if is_deep_research and not is_clarification:
                            try:
                                state = agent.get_state(
                                    {"configurable": {"thread_id": conversation_id}}
                                )
                                if state and state.values:
                                    clarification_status = state.values.get(
                                        "clarification_status"
                                    )
                                    if hasattr(clarification_status, "value"):
                                        clarification_status = clarification_status.value
                                    if isinstance(
                                        clarification_status, ClarificationStatus
                                    ):
                                        is_clarification = (
                                            clarification_status.need_clarification
                                        )
                                    elif isinstance(clarification_status, dict):
                                        is_clarification = clarification_status.get(
                                            "need_clarification", False
                                        )
                            except Exception as state_error:
                                print(
                                    "Warning: Could not read clarification status "
                                    f"from state: {state_error}"
                                )
                        yield StreamEvent(
                            type=StreamEventType.MESSAGE_COMPLETE,
                            data={
                                "tool_calls": [
                                    tc.model_dump()
                                    for tc in active_tool_calls.values()
                                ],
                                "is_clarification": is_clarification,
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
        for alias, full_name in OPENROUTER_MODELS.items():
            # 从完整模型名提取显示名称，如 "openai/gpt-5" -> "GPT-5"
            model_display = full_name.split("/")[-1]
            models.append(
                ModelInfo(
                    provider="openrouter",
                    name=full_name,
                    display_name=f"{model_display} (OpenRouter)",
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
