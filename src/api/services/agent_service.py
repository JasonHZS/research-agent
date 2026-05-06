"""Agent service - Bridge between API and research agent."""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

import httpcore
import httpx
from langchain_core.messages import AIMessage
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
from src.config.llm_factory import (
    ALIYUN_MODELS,
    OPENROUTER_MODELS,
)
from src.config.settings import resolve_runtime_settings
from src.deep_research.graph import build_deep_research_graph
from src.deep_research.state import ClarificationStatus, Section
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class StreamingSnapshot:
    request_id: str
    _content_parts: list[str] = field(default_factory=list)
    _thinking_parts: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    segments: list[dict[str, Any]] = field(default_factory=list)
    progress_node: Optional[str] = None
    is_clarification: bool = False
    is_running: bool = True
    error: Optional[str] = None
    state_degraded: bool = False

    @property
    def content(self) -> str:
        return "".join(self._content_parts)

    @content.setter
    def content(self, value: str) -> None:
        self._content_parts = [value]

    def append_content(self, chunk: str) -> None:
        self._content_parts.append(chunk)

    @property
    def thinking_content(self) -> str:
        return "".join(self._thinking_parts)

    @thinking_content.setter
    def thinking_content(self, value: str) -> None:
        self._thinking_parts = [value]

    def append_thinking(self, chunk: str) -> None:
        self._thinking_parts.append(chunk)


@dataclass
class BackgroundRun:
    conversation_id: str
    request_id: str
    is_deep_research: bool
    task: Optional[asyncio.Task]
    snapshot: StreamingSnapshot
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    terminal_event: Optional[StreamEvent] = None
    completed_at: Optional[float] = None


class AgentService:
    """Service for managing research agent instances and streaming."""

    DEEP_RESEARCH_HEARTBEAT_INTERVAL_SECONDS = 15.0
    DEEP_RESEARCH_HEARTBEAT_FALLBACK_NODE = "working"
    COMPLETED_RUN_TTL_SECONDS = 30 * 60  # 30 minutes

    def __init__(self):
        """Initialize the agent service."""
        self._agents: dict[str, Any] = {}  # conversation_id -> agent
        self._checkpointers: dict[tuple[str, bool], MemorySaver] = {}
        self._stores: dict[tuple[str, bool], InMemoryStore] = {}
        self._agent_configs: dict[str, tuple[str, Optional[str], bool]] = {}
        self._background_runs: dict[str, BackgroundRun] = {}

    def _get_or_create_agent(
        self,
        conversation_id: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
    ) -> Any:
        """Get existing agent or create a new one for the conversation."""
        runtime_settings = resolve_runtime_settings(
            provider_override=model_provider,
            model_name_override=model_name,
        )
        requested_provider = runtime_settings.llm.provider
        requested_model = runtime_settings.llm.model_name

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
            logger.debug(
                "Reusing existing agent",
                conversation_id=conversation_id,
            )
            return cached_agent

        if cached_agent:
            logger.info(
                "Recreating agent due to config change",
                conversation_id=conversation_id,
                old_config=str(cached_config),
                new_config=str((requested_provider, requested_model, is_deep_research)),
            )

        try:
            if is_deep_research:
                logger.info(
                    "Creating Deep Research agent",
                    conversation_id=conversation_id,
                    provider=requested_provider,
                    model=requested_model,
                )
                agent = build_deep_research_graph(
                    model_provider=requested_provider,
                    model_name=requested_model,
                    checkpointer=checkpointer,
                    store=store,
                )
            else:
                logger.info(
                    "Creating Research agent",
                    conversation_id=conversation_id,
                    provider=requested_provider,
                    model=requested_model,
                )
                agent = create_research_agent(
                    model_provider=requested_provider,
                    model_name=requested_model,
                    checkpointer=checkpointer,
                    store=store,
                    debug=False,
                )

            logger.info(
                "Agent ready",
                conversation_id=conversation_id,
                provider=requested_provider,
                model=requested_model,
                is_deep_research=is_deep_research,
            )
            self._agents[conversation_id] = agent
            self._agent_configs[conversation_id] = (requested_provider, requested_model, is_deep_research)
            return agent
        except Exception as e:
            logger.exception(
                "Failed to create agent",
                conversation_id=conversation_id,
                error=str(e),
            )
            raise

    def remove_agent(self, conversation_id: str) -> None:
        """Remove agent instance for a conversation."""
        background_run = self._background_runs.pop(conversation_id, None)
        if background_run is not None and background_run.task is not None:
            background_run.task.cancel()

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
    def _is_error_result(result: str) -> bool:
        """Check if a tool result indicates an error."""
        if not result:
            return False
        result_lower = result.lower()
        # Common error indicators in tool results
        error_indicators = [
            "error",
            "failed",
            "exception",
            "timeout",
            "connection refused",
            "not found",
            "unauthorized",
            "forbidden",
            "rate limit",
        ]
        return any(indicator in result_lower for indicator in error_indicators)

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
    def _sanitize_tool_args(args: Any) -> Any:
        """
        Filter sensitive information from tool arguments before logging.

        Args:
            args: Tool arguments (dict, string, or other)

        Returns:
            Sanitized arguments with sensitive values redacted
        """
        if not args:
            return args

        sensitive_keys = ["key", "token", "secret", "password", "credential", "auth"]

        # Handle dict args directly
        if isinstance(args, dict):
            sanitized = {}
            for k, v in args.items():
                if any(s in k.lower() for s in sensitive_keys):
                    sanitized[k] = "***REDACTED***"
                else:
                    sanitized[k] = v
            return sanitized

        # Handle string args (may be JSON)
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
                if isinstance(parsed, dict):
                    sanitized = {}
                    for k, v in parsed.items():
                        if any(s in k.lower() for s in sensitive_keys):
                            sanitized[k] = "***REDACTED***"
                        else:
                            sanitized[k] = v
                    return json.dumps(sanitized)
            except (json.JSONDecodeError, TypeError):
                pass

        return args


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

    @staticmethod
    def _append_text_segment(
        segments: list[dict[str, Any]],
        content: str,
    ) -> list[dict[str, Any]]:
        if not content:
            return segments

        updated_segments = [dict(segment) for segment in segments]
        if not updated_segments or updated_segments[-1].get("type") == "tool_calls":
            updated_segments.append({"type": "text", "content": content})
            return updated_segments

        last_segment = dict(updated_segments[-1])
        last_segment["content"] = f"{last_segment.get('content', '')}{content}"
        updated_segments[-1] = last_segment
        return updated_segments

    @staticmethod
    def _set_text_segment(
        segments: list[dict[str, Any]],
        content: str,
    ) -> list[dict[str, Any]]:
        updated_segments = [dict(segment) for segment in segments]
        if not updated_segments:
            return [{"type": "text", "content": content}]

        last_segment = updated_segments[-1]
        if last_segment.get("type") == "text":
            updated_segments[-1] = {"type": "text", "content": content}
        else:
            updated_segments.append({"type": "text", "content": content})
        return updated_segments

    @staticmethod
    def _append_tool_call_segment(
        segments: list[dict[str, Any]],
        tool_call: dict[str, Any],
    ) -> list[dict[str, Any]]:
        updated_segments = [dict(segment) for segment in segments]
        if updated_segments and updated_segments[-1].get("type") == "tool_calls":
            last_segment = dict(updated_segments[-1])
            existing_tool_calls = [
                dict(existing_tool_call)
                for existing_tool_call in last_segment.get("toolCalls", [])
            ]
            if all(tc.get("status") == "running" for tc in existing_tool_calls):
                existing_tool_calls.append(dict(tool_call))
                last_segment["toolCalls"] = existing_tool_calls
                updated_segments[-1] = last_segment
                return updated_segments

        updated_segments.append({"type": "tool_calls", "toolCalls": [dict(tool_call)]})
        return updated_segments

    @staticmethod
    def _replace_tool_call(
        tool_calls: list[dict[str, Any]],
        tool_call: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            dict(tool_call) if existing_tool_call.get("id") == tool_call.get("id")
            else dict(existing_tool_call)
            for existing_tool_call in tool_calls
        ]

    @classmethod
    def _replace_tool_call_in_segments(
        cls,
        segments: list[dict[str, Any]],
        tool_call: dict[str, Any],
    ) -> list[dict[str, Any]]:
        updated_segments: list[dict[str, Any]] = []
        for segment in segments:
            updated_segment = dict(segment)
            if updated_segment.get("type") == "tool_calls":
                updated_segment["toolCalls"] = cls._replace_tool_call(
                    updated_segment.get("toolCalls", []),
                    tool_call,
                )
            updated_segments.append(updated_segment)
        return updated_segments

    @classmethod
    def _apply_event_to_snapshot(
        cls,
        snapshot: StreamingSnapshot,
        event: StreamEvent,
    ) -> None:
        if event.type == StreamEventType.TOKEN:
            content = str(event.data.get("content", ""))
            snapshot.append_content(content)
            snapshot.segments = cls._append_text_segment(snapshot.segments, content)
        elif event.type == StreamEventType.THINKING:
            snapshot.append_thinking(str(event.data.get("content", "")))
        elif event.type == StreamEventType.TOOL_CALL_START:
            tool_call = dict(event.data)
            snapshot.tool_calls.append(tool_call)
            snapshot.segments = cls._append_tool_call_segment(snapshot.segments, tool_call)
        elif event.type == StreamEventType.TOOL_CALL_END:
            tool_call = dict(event.data)
            snapshot.tool_calls = cls._replace_tool_call(snapshot.tool_calls, tool_call)
            snapshot.segments = cls._replace_tool_call_in_segments(snapshot.segments, tool_call)
        elif event.type == StreamEventType.CLARIFICATION:
            question = str(event.data.get("question", ""))
            snapshot.content = question
            snapshot.segments = cls._set_text_segment(snapshot.segments, question)
            snapshot.is_clarification = True
        elif event.type == StreamEventType.BRIEF:
            sections = event.data.get("sections", [])
            sections_text = "\n\n".join(
                f"### {index + 1}. {section.get('title', '')}\n\n{section.get('description', '')}"
                for index, section in enumerate(sections)
            )
            brief_content = f"## 研究大纲\n\n{sections_text}" if sections_text else "## 研究大纲"
            if snapshot.content:
                snapshot.content = f"{snapshot.content}\n\n{brief_content}"
            else:
                snapshot.content = brief_content
            snapshot.segments = cls._append_text_segment(snapshot.segments, f"\n\n{brief_content}" if snapshot.segments else brief_content)
        elif event.type == StreamEventType.PROGRESS:
            node = event.data.get("node")
            snapshot.progress_node = str(node) if node else None
        elif event.type == StreamEventType.MESSAGE_COMPLETE:
            snapshot.is_running = False
            snapshot.is_clarification = bool(
                event.data.get("is_clarification", snapshot.is_clarification)
            )
        elif event.type == StreamEventType.ERROR:
            snapshot.is_running = False
            snapshot.error = str(event.data.get("message", "Unknown error"))

    def _build_snapshot_from_state(
        self,
        conversation_id: str,
        run: BackgroundRun,
    ) -> dict[str, Any]:
        snapshot = StreamingSnapshot(
            request_id=run.snapshot.request_id,
            tool_calls=[dict(tool_call) for tool_call in run.snapshot.tool_calls],
            segments=[dict(segment) for segment in run.snapshot.segments],
            progress_node=run.snapshot.progress_node,
            is_clarification=run.snapshot.is_clarification,
            is_running=run.snapshot.is_running,
            error=run.snapshot.error,
        )
        snapshot.content = run.snapshot.content
        snapshot.thinking_content = run.snapshot.thinking_content

        agent = self._agents.get(conversation_id)
        if agent is not None:
            try:
                state = agent.get_state({"configurable": {"thread_id": conversation_id}})
                if state and state.values:
                    values = state.values
                    final_report = values.get("final_report", "")
                    clarification_status = values.get("clarification_status")
                    research_brief = values.get("research_brief")
                    sections = values.get("sections")

                    if hasattr(clarification_status, "value"):
                        clarification_status = clarification_status.value
                    if hasattr(research_brief, "value"):
                        research_brief = research_brief.value
                    if hasattr(sections, "value"):
                        sections = sections.value

                    if final_report and not snapshot.content:
                        snapshot.content = str(final_report)
                        snapshot.segments = [{"type": "text", "content": snapshot.content}]

                    if isinstance(clarification_status, ClarificationStatus):
                        snapshot.is_clarification = clarification_status.need_clarification
                        if clarification_status.question:
                            snapshot.content = clarification_status.question
                            snapshot.segments = [{"type": "text", "content": snapshot.content}]
                    elif isinstance(clarification_status, dict):
                        snapshot.is_clarification = bool(
                            clarification_status.get("need_clarification", snapshot.is_clarification)
                        )
                        question = clarification_status.get("question", "")
                        if question:
                            snapshot.content = question
                            snapshot.segments = [{"type": "text", "content": snapshot.content}]

                    if research_brief and sections and "## 研究大纲" not in snapshot.content:
                        sections_text = "\n\n".join(
                            f"### {index + 1}. {section.title if isinstance(section, Section) else section.get('title', '')}\n\n"
                            f"{section.description if isinstance(section, Section) else section.get('description', '')}"
                            for index, section in enumerate(sections)
                        )
                        brief_content = f"## 研究大纲\n\n{sections_text}" if sections_text else "## 研究大纲"
                        snapshot.content = (
                            f"{snapshot.content}\n\n{brief_content}"
                            if snapshot.content
                            else brief_content
                        )
                        snapshot.segments = [{"type": "text", "content": snapshot.content}]
            except Exception as state_error:
                logger.warning(
                    "Could not build snapshot from graph state",
                    conversation_id=conversation_id,
                    error=str(state_error),
                )
                snapshot.state_degraded = True

        return {
            "request_id": snapshot.request_id,
            "content": snapshot.content,
            "thinking_content": snapshot.thinking_content,
            "tool_calls": snapshot.tool_calls,
            "segments": snapshot.segments,
            "progress_node": snapshot.progress_node,
            "is_clarification": snapshot.is_clarification,
            "is_running": snapshot.is_running,
            "error": snapshot.error,
            "state_degraded": snapshot.state_degraded,
        }

    async def _broadcast_to_subscribers(
        self,
        run: BackgroundRun,
        event: Optional[StreamEvent],
    ) -> None:
        stale_subscribers: list[asyncio.Queue] = []
        for subscriber in run.subscribers:
            try:
                subscriber.put_nowait(event)
            except asyncio.QueueFull:
                stale_subscribers.append(subscriber)

        for stale_subscriber in stale_subscribers:
            run.subscribers.discard(stale_subscriber)

    async def _run_in_background(
        self,
        run: BackgroundRun,
        message: str,
        model_provider: Optional[str],
        model_name: Optional[str],
    ) -> None:
        try:
            async for event in self._stream_agent_events(
                conversation_id=run.conversation_id,
                message=message,
                model_provider=model_provider,
                model_name=model_name,
                is_deep_research=run.is_deep_research,
            ):
                self._apply_event_to_snapshot(run.snapshot, event)
                if event.type in {StreamEventType.MESSAGE_COMPLETE, StreamEventType.ERROR}:
                    run.terminal_event = event
                await self._broadcast_to_subscribers(run, event)
        except asyncio.CancelledError:
            run.snapshot.error = "Run was cancelled"
            raise
        except Exception as run_error:
            logger.exception(
                "Background run failed unexpectedly",
                conversation_id=run.conversation_id,
                error=str(run_error),
            )
            error_event = StreamEvent(
                type=StreamEventType.ERROR,
                data={"message": str(run_error)},
            )
            self._apply_event_to_snapshot(run.snapshot, error_event)
            run.terminal_event = error_event
            await self._broadcast_to_subscribers(run, error_event)
        finally:
            run.snapshot.is_running = False
            run.completed_at = time.monotonic()
            await self._broadcast_to_subscribers(run, None)

    def _purge_stale_runs(self) -> None:
        """Remove completed BackgroundRun objects older than TTL."""
        now = time.monotonic()
        stale_ids = [
            cid
            for cid, run in self._background_runs.items()
            if run.completed_at is not None
            and (now - run.completed_at) > self.COMPLETED_RUN_TTL_SECONDS
        ]
        for cid in stale_ids:
            self._background_runs.pop(cid, None)

    def _get_background_run(self, conversation_id: str) -> Optional[BackgroundRun]:
        """Return the current run after enforcing TTL for completed entries."""
        self._purge_stale_runs()
        return self._background_runs.get(conversation_id)

    def start_background_run(
        self,
        conversation_id: str,
        message: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
        request_id: Optional[str] = None,
    ) -> BackgroundRun:
        existing_run = self._get_background_run(conversation_id)
        if existing_run is not None and existing_run.task is not None and not existing_run.task.done():
            raise ValueError(f"Conversation {conversation_id} already has an active run")

        resolved_request_id = request_id or uuid4().hex
        snapshot = StreamingSnapshot(request_id=resolved_request_id)
        run = BackgroundRun(
            conversation_id=conversation_id,
            request_id=resolved_request_id,
            is_deep_research=is_deep_research,
            task=None,
            snapshot=snapshot,
        )
        run.task = asyncio.create_task(
            self._run_in_background(
                run=run,
                message=message,
                model_provider=model_provider,
                model_name=model_name,
            )
        )
        self._background_runs[conversation_id] = run
        return run

    async def subscribe_to_run(
        self,
        conversation_id: str,
    ) -> AsyncGenerator[StreamEvent, None]:
        run = self._get_background_run(conversation_id)
        if run is None:
            raise ValueError(f"No background run found for conversation {conversation_id}")

        queue: asyncio.Queue = asyncio.Queue()
        if run.snapshot.is_running:
            run.subscribers.add(queue)

        try:
            yield StreamEvent(
                type=StreamEventType.SNAPSHOT,
                data=self._build_snapshot_from_state(conversation_id, run),
            )

            if not run.snapshot.is_running:
                if run.terminal_event is not None:
                    yield run.terminal_event
                return

            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            run.subscribers.discard(queue)

    def has_background_run(self, conversation_id: str) -> bool:
        return self._get_background_run(conversation_id) is not None

    async def stream_response(
        self,
        conversation_id: str,
        message: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Backward-compatible direct event stream for tests and non-background use."""
        async for event in self._stream_agent_events(
            conversation_id=conversation_id,
            message=message,
            model_provider=model_provider,
            model_name=model_name,
            is_deep_research=is_deep_research,
        ):
            yield event

    async def _stream_agent_events(
        self,
        conversation_id: str,
        message: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream agent response as events.

        Yields StreamEvent objects that can be serialized and sent to clients.
        Each request is independent - no cross-request state tracking needed.
        """
        runtime_settings = resolve_runtime_settings(
            provider_override=model_provider,
            model_name_override=model_name,
        )

        agent = self._get_or_create_agent(
            conversation_id,
            runtime_settings.llm.provider,
            runtime_settings.llm.model_name,
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
                logger.debug(
                    "Found existing tool calls in checkpoint",
                    conversation_id=conversation_id,
                    count=len(existing_tool_ids),
                )
        except Exception as e:
            # Graceful fallback if state retrieval fails
            logger.warning(
                "Could not retrieve checkpoint state",
                conversation_id=conversation_id,
                error=str(e),
            )

        # Track tool calls for this response only
        active_tool_calls: dict[str, ToolCall] = {}
        tool_call_start_times: dict[str, float] = {}  # Track start times for duration calc
        seen_tool_ids: set[str] = existing_tool_ids.copy()  # Start with existing IDs
        tool_call_counter = 0

        # For Deep Research: track clarification status and brief from state updates
        clarification_sent = False
        brief_sent = False
        _last_progress_node = ""  # Track the latest known graph node for heartbeat payloads
        _last_heartbeat_time = 0.0  # Track when the last progress event was emitted

        extra_config = None
        max_concurrency = None
        completed_tool_ids: set[str] = set()
        stream = None
        stream_iter = None
        pending_chunk_task: asyncio.Task | None = None

        def emit_progress_if_changed(node_name: str) -> StreamEvent | None:
            nonlocal _last_progress_node, _last_heartbeat_time
            if not node_name or node_name == _last_progress_node:
                return None

            _last_progress_node = node_name
            _last_heartbeat_time = time.monotonic()
            return StreamEvent(
                type=StreamEventType.PROGRESS,
                data={"node": node_name},
            )

        try:
            # For Deep Research: enable verbose mode to print tool calls in backend
            if is_deep_research:
                extra_config = {
                    "verbose": True,
                    "model_provider": runtime_settings.llm.provider,
                    "model_name": runtime_settings.llm.model_name,
                    "max_iterations": runtime_settings.deep_research.max_iterations,
                    "max_tool_calls": runtime_settings.deep_research.max_tool_calls,
                }
                max_concurrency = runtime_settings.deep_research.max_concurrent

            stream = run_research_stream(
                query=message,
                agent=agent,
                thread_id=conversation_id,
                extra_config=extra_config,
                max_concurrency=max_concurrency,
            )
            stream_iter = stream.__aiter__()
            pending_chunk_task = asyncio.create_task(anext(stream_iter))

            while True:
                if is_deep_research:
                    # Keep the upstream iterator alive while we inject keepalive
                    # events. wait_for() would cancel the pending __anext__ call
                    # on every timeout, which breaks long-running stages.
                    done, _ = await asyncio.wait(
                        {pending_chunk_task},
                        timeout=self.DEEP_RESEARCH_HEARTBEAT_INTERVAL_SECONDS,
                    )
                    if not done:
                        _last_heartbeat_time = time.monotonic()
                        yield StreamEvent(
                            type=StreamEventType.PROGRESS,
                            data={
                                "node": (
                                    _last_progress_node
                                    or self.DEEP_RESEARCH_HEARTBEAT_FALLBACK_NODE
                                )
                            },
                        )
                        continue

                try:
                    mode, chunk = await pending_chunk_task
                except StopAsyncIteration:
                    pending_chunk_task = None
                    break

                pending_chunk_task = asyncio.create_task(anext(stream_iter))

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
                        progress_event = emit_progress_if_changed(current_node)
                        if progress_event is not None:
                            yield progress_event
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
                        if is_deep_research:
                            progress_event = emit_progress_if_changed(node_name)
                            if progress_event is not None:
                                yield progress_event
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

                                    # Sanitize args to prevent sensitive data leakage to clients
                                    sanitized_args = self._sanitize_tool_args(tc.get("args", {}))
                                    tool_call = ToolCall(
                                        id=tool_id,
                                        name=tc.get("name", "unknown"),
                                        args=sanitized_args,
                                        status=ToolCallStatus.RUNNING,
                                    )
                                    active_tool_calls[tool_id] = tool_call
                                    tool_call_start_times[tool_id] = time.time()

                                    # Always log tool calls for debugging and auditing
                                    logger.info(
                                        "Tool call started",
                                        tool_id=tool_id,
                                        tool_name=tool_call.name,
                                        tool_args=sanitized_args,
                                        conversation_id=conversation_id,
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
                                    tool_call.result = self._format_tool_result(
                                        getattr(msg, "content", None)
                                    )

                                    # Detect errors in tool result
                                    is_error = self._is_error_result(tool_call.result)
                                    tool_call.status = (
                                        ToolCallStatus.FAILED if is_error
                                        else ToolCallStatus.COMPLETED
                                    )

                                    completed_tool_ids.add(tool_id)
                                    # Calculate duration
                                    start_time = tool_call_start_times.get(tool_id)
                                    duration_ms = round((time.time() - start_time) * 1000, 2) if start_time else None

                                    # Log at different levels based on success/failure
                                    result_preview = str(tool_call.result)[:200] if tool_call.result else None
                                    if is_error:
                                        logger.warning(
                                            "Tool call failed",
                                            tool_id=tool_id,
                                            tool_name=tool_call.name,
                                            duration_ms=duration_ms,
                                            error_preview=result_preview,
                                            conversation_id=conversation_id,
                                        )
                                    else:
                                        logger.info(
                                            "Tool call completed",
                                            tool_id=tool_id,
                                            tool_name=tool_call.name,
                                            duration_ms=duration_ms,
                                            result_preview=result_preview,
                                            conversation_id=conversation_id,
                                        )

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
            if self._is_stream_disconnect_error(e):
                logger.warning(
                    "Streaming connection closed early, retrying with non-streaming",
                    conversation_id=conversation_id,
                )

                # Retry with exponential backoff for transient connection errors
                max_retries = 5
                base_delay = 1.0  # seconds

                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            delay = base_delay * (2 ** (attempt - 1))  # 1s, 2s, 4s, 8s
                            logger.info(
                                "Retry attempt",
                                attempt=attempt + 1,
                                max_retries=max_retries,
                                delay_seconds=delay,
                                conversation_id=conversation_id,
                            )
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

                                            # Sanitize args to prevent sensitive data leakage to clients
                                            sanitized_args = self._sanitize_tool_args(tc.get("args", {}))
                                            tool_call = ToolCall(
                                                id=tool_id,
                                                name=tc.get("name", "unknown"),
                                                args=sanitized_args,
                                                status=ToolCallStatus.RUNNING,
                                            )
                                            active_tool_calls[tool_id] = tool_call
                                            tool_call_start_times[tool_id] = time.time()
                                            # Always log tool calls (fallback path)
                                            logger.info(
                                                "Tool call started (fallback)",
                                                tool_id=tool_id,
                                                tool_name=tool_call.name,
                                                tool_args=sanitized_args,
                                                conversation_id=conversation_id,
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
                                            tool_call.result = self._format_tool_result(
                                                getattr(msg, "content", None)
                                            )

                                            # Detect errors in tool result
                                            is_error = self._is_error_result(tool_call.result)
                                            tool_call.status = (
                                                ToolCallStatus.FAILED if is_error
                                                else ToolCallStatus.COMPLETED
                                            )

                                            completed_tool_ids.add(tool_id)
                                            # Calculate duration (may not be accurate in fallback path)
                                            start_time = tool_call_start_times.get(tool_id)
                                            duration_ms = round((time.time() - start_time) * 1000, 2) if start_time else None

                                            # Log at different levels based on success/failure (fallback path)
                                            result_preview = str(tool_call.result)[:200] if tool_call.result else None
                                            if is_error:
                                                logger.warning(
                                                    "Tool call failed (fallback)",
                                                    tool_id=tool_id,
                                                    tool_name=tool_call.name,
                                                    duration_ms=duration_ms,
                                                    error_preview=result_preview,
                                                    conversation_id=conversation_id,
                                                )
                                            else:
                                                logger.info(
                                                    "Tool call completed (fallback)",
                                                    tool_id=tool_id,
                                                    tool_name=tool_call.name,
                                                    duration_ms=duration_ms,
                                                    result_preview=result_preview,
                                                    conversation_id=conversation_id,
                                                )
                                            yield StreamEvent(
                                                type=StreamEventType.TOOL_CALL_END,
                                                data=tool_call.model_dump(),
                                            )
                        except Exception as fallback_state_error:
                            logger.warning(
                                "Could not emit tool calls from fallback state",
                                conversation_id=conversation_id,
                                error=str(fallback_state_error),
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
                                logger.warning(
                                    "Could not read clarification status from state",
                                    conversation_id=conversation_id,
                                    error=str(state_error),
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
                            logger.warning(
                                "Retry failed with retryable error",
                                attempt=attempt + 1,
                                conversation_id=conversation_id,
                                error=str(fallback_error),
                            )
                            continue  # Try again

                        # Final attempt failed or non-retryable error
                        logger.error(
                            "Non-streaming fallback failed",
                            attempt=attempt + 1,
                            conversation_id=conversation_id,
                            error=str(fallback_error),
                            exc_info=True,
                        )
                        break  # Exit retry loop, fall through to error handling

            logger.exception(
                "Agent stream failed",
                conversation_id=conversation_id,
                error=str(e),
            )
            yield StreamEvent(
                type=StreamEventType.ERROR,
                data={"message": str(e)},
            )
        finally:
            if pending_chunk_task is not None and not pending_chunk_task.done():
                pending_chunk_task.cancel()
                with suppress(asyncio.CancelledError):
                    await pending_chunk_task
            if stream is not None and hasattr(stream, "aclose"):
                with suppress(Exception):
                    await stream.aclose()

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
                    supports_thinking=name
                    in [
                        "qwen3.6-plus",
                        "kimi-k2.6",
                        "glm-5.1",
                        "deepseek-v4-pro",
                        "deepseek-v4-flash",
                    ],
                )
            )

        # OpenRouter models
        for _alias, full_name in OPENROUTER_MODELS.items():
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
