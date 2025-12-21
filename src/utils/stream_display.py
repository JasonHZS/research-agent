"""
Stream Display Module

Provides structured display of agent execution steps during streaming.
Parses LangGraph update events and formats them for user-friendly output.

Architecture:
- StreamDisplay: Public facade maintaining backward-compatible API
- UpdatesChunkHandler: Strategy for handling "updates" mode chunks
- MessagesChunkHandler: Strategy for handling "messages" mode chunks
- OutputRenderer: Centralized console output
- ToolCallFormatter: Text formatting utilities
- StreamingState: Immutable state container
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any


# =============================================================================
# State Container
# =============================================================================


@dataclass(frozen=True)
class StreamingState:
    """
    Immutable state container for streaming display.

    Using frozen=True ensures state transitions are explicit and trackable.
    """

    is_streaming_response: bool = False
    pending_tool_results: bool = False
    response_header_shown: bool = False
    streaming_content_parts: tuple[str, ...] = field(default_factory=tuple)

    def with_streaming_started(self) -> StreamingState:
        """Return new state with streaming started."""
        return replace(
            self,
            is_streaming_response=True,
            streaming_content_parts=(),
        )

    def with_streaming_finished(self) -> StreamingState:
        """Return new state with streaming finished."""
        return replace(
            self,
            is_streaming_response=False,
            streaming_content_parts=(),
            response_header_shown=False,
        )

    def with_content_appended(self, content: str) -> StreamingState:
        """Return new state with content added."""
        new_parts = self.streaming_content_parts + (content,)
        return replace(self, streaming_content_parts=new_parts)

    def with_pending_tool_results(self, pending: bool) -> StreamingState:
        """Return new state with pending_tool_results flag updated."""
        return replace(self, pending_tool_results=pending)

    def with_response_header_shown(self, shown: bool) -> StreamingState:
        """Return new state with response_header_shown flag updated."""
        return replace(self, response_header_shown=shown)


# =============================================================================
# Output Renderer
# =============================================================================


class OutputRenderer:
    """
    Handles all console output with box-drawing formatting.

    All methods are static to emphasize they are pure I/O operations
    with no state dependencies.
    """

    @staticmethod
    def render_tool_calls(tool_calls: list[dict], formatter: ToolCallFormatter) -> None:
        """Render tool calls section."""
        print("\n┌─ Tool Calls")
        for tc in tool_calls:
            name = tc.get("name", "unknown")
            args = tc.get("args", {})
            args_str = formatter.format_args(args)
            print(f"│  🔧 {name}({args_str})")
        print("└─")

    @staticmethod
    def render_response_header() -> None:
        """Render response section header."""
        print("\n┌─ Agent 回答")
        print("│  ", end="", flush=True)

    @staticmethod
    def render_response_footer() -> None:
        """Render response section footer."""
        print()
        print("└─")

    @staticmethod
    def render_token(content: str) -> None:
        """Render a single token without newline."""
        print(content, end="", flush=True)

    @staticmethod
    def render_section_close() -> None:
        """Close a pending section with newline."""
        print()


# =============================================================================
# Formatting Utilities
# =============================================================================


class ToolCallFormatter:
    """
    Formats tool arguments and text for display.

    Provides both verbose and compact formatting modes.
    """

    # Keys that should not be truncated
    FULL_DISPLAY_KEYS = {"description", "query", "prompt"}

    def __init__(self, verbose: bool = False):
        """
        Initialize formatter.

        Args:
            verbose: If True, show full argument values.
        """
        self.verbose = verbose

    def format_args(self, args: dict) -> str:
        """
        Format tool arguments for display.

        Args:
            args: Dictionary of tool arguments.

        Returns:
            Formatted string representation of arguments.
        """
        if not args:
            return ""

        if self.verbose:
            return self._format_verbose(args)
        return self._format_compact(args)

    def _format_verbose(self, args: dict) -> str:
        """Format all args in verbose mode."""
        parts = []
        for k, v in args.items():
            if isinstance(v, str) and len(v) > 50 and k not in self.FULL_DISPLAY_KEYS:
                v = v[:47] + "..."
            parts.append(f"{k}={json.dumps(v, ensure_ascii=False)}")
        return ", ".join(parts)

    def _format_compact(self, args: dict) -> str:
        """Format args in compact mode."""
        parts = []
        for k, v in args.items():
            if isinstance(v, str):
                if k not in self.FULL_DISPLAY_KEYS and len(v) > 30:
                    v = v[:27] + "..."
                parts.append(f'{k}="{v}"')
            elif isinstance(v, (int, float, bool)):
                parts.append(f"{k}={v}")
            elif isinstance(v, list):
                parts.append(f"{k}=[{len(v)} items]")
            elif isinstance(v, dict):
                parts.append(f"{k}={{...}}")
        return ", ".join(parts)

    @staticmethod
    def truncate(text: str, max_length: int) -> str:
        """
        Truncate text to max length with ellipsis.

        Args:
            text: Text to truncate.
            max_length: Maximum length.

        Returns:
            Truncated text.
        """
        # Remove newlines and collapse spaces
        text = text.replace("\n", " ").replace("\r", "")
        while "  " in text:
            text = text.replace("  ", " ")
        text = text.strip()

        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."


# =============================================================================
# Chunk Handlers (Strategy Pattern)
# =============================================================================


class UpdatesChunkHandler:
    """
    Handles 'updates' mode chunks - node completion events.

    Processes tool calls from model node updates.
    """

    def __init__(self, renderer: OutputRenderer, formatter: ToolCallFormatter):
        """
        Initialize handler.

        Args:
            renderer: Output renderer for display.
            formatter: Formatter for tool arguments.
        """
        self._renderer = renderer
        self._formatter = formatter

    def handle(
        self, chunk: dict, state: StreamingState
    ) -> tuple[StreamingState, str | None]:
        """
        Process updates mode chunk.

        Args:
            chunk: Update dict with {node_name: {messages: [...]}}
            state: Current streaming state.

        Returns:
            Tuple of (new_state, final_content).
            final_content is always None for updates mode.
        """
        new_state = state

        for node_name, data in chunk.items():
            # Skip middleware events
            if "Middleware" in node_name:
                continue

            if node_name == "model":
                new_state = self._handle_model_node(data, new_state)
            # Tools node: skip displaying results (kept for future extension)

        return new_state, None

    def _handle_model_node(
        self,
        data: dict | None,  # Accept Optional to match actual LangGraph behavior
        state: StreamingState,
    ) -> StreamingState:
        """
        Handle model node update - only tool calls.

        Args:
            data: Model update data containing messages, or None.
            state: Current streaming state.

        Returns:
            Updated streaming state.
        """
        if data is None:
            return state

        messages = data.get("messages", [])
        for msg in messages:
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                state = self._display_tool_calls(tool_calls, state)

        return state

    def _display_tool_calls(
        self, tool_calls: list, state: StreamingState
    ) -> StreamingState:
        """
        Display tool calls and update state.

        Args:
            tool_calls: List of tool call dictionaries.
            state: Current streaming state.

        Returns:
            Updated streaming state.
        """
        # Close any pending sections
        if state.pending_tool_results:
            self._renderer.render_section_close()
            state = state.with_pending_tool_results(False)

        if state.is_streaming_response:
            self._renderer.render_response_footer()
            state = state.with_streaming_finished()

        # Render tool calls
        self._renderer.render_tool_calls(tool_calls, self._formatter)

        return state.with_pending_tool_results(True)


class MessagesChunkHandler:
    """
    Handles 'messages' mode chunks - token-level streaming.

    Processes LLM response tokens for real-time display.
    """

    def __init__(self, renderer: OutputRenderer):
        """
        Initialize handler.

        Args:
            renderer: Output renderer for display.
        """
        self._renderer = renderer

    def handle(
        self,
        chunk: tuple | None,  # Accept None for robustness
        state: StreamingState,
    ) -> tuple[StreamingState, str | None]:
        """
        Process messages mode chunk.

        Args:
            chunk: Tuple of (message_chunk, metadata) or None.
            state: Current streaming state.

        Returns:
            Tuple of (new_state, final_content).
            final_content is set when streaming completes.
        """
        if chunk is None or not isinstance(chunk, tuple) or len(chunk) != 2:
            return state, None

        message_chunk, _metadata = chunk

        # Skip ToolMessage chunks
        if "ToolMessage" in type(message_chunk).__name__:
            return state, None

        # Skip tool call chunks (handled by updates mode)
        if getattr(message_chunk, "tool_calls", None):
            return state, None

        # Extract content
        content = self._extract_content(message_chunk)
        if not content:
            # Check for finish signal even without content
            if self._is_finish_signal(message_chunk):
                return self._finish_streaming(state)
            return state, None

        # Start streaming if needed
        if not state.is_streaming_response:
            state = self._start_streaming(state)

        # Render and accumulate token
        self._renderer.render_token(content)
        state = state.with_content_appended(content)

        # Check for finish signal
        if self._is_finish_signal(message_chunk):
            return self._finish_streaming(state)

        return state, None

    def _extract_content(self, message_chunk: Any) -> str:
        """
        Extract text content from message chunk.

        Args:
            message_chunk: LangGraph message chunk.

        Returns:
            Extracted text content.
        """
        content = getattr(message_chunk, "content", "")

        # Handle list content (e.g., from MCP tools)
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(text_parts)

        return str(content) if content else ""

    def _is_finish_signal(self, message_chunk: Any) -> bool:
        """
        Check if chunk signals end of streaming.

        Args:
            message_chunk: LangGraph message chunk.

        Returns:
            True if this is the final chunk.
        """
        response_metadata = getattr(message_chunk, "response_metadata", {})
        finish_reason = response_metadata.get("finish_reason")
        usage_metadata = getattr(message_chunk, "usage_metadata", None)

        return finish_reason == "stop" or usage_metadata is not None

    def _start_streaming(self, state: StreamingState) -> StreamingState:
        """
        Start streaming response.

        Args:
            state: Current streaming state.

        Returns:
            Updated streaming state.
        """
        # Close any pending tool results
        if state.pending_tool_results:
            self._renderer.render_section_close()
            state = state.with_pending_tool_results(False)

        # Show header if first time
        if not state.response_header_shown:
            self._renderer.render_response_header()
            state = state.with_response_header_shown(True)

        return state.with_streaming_started()

    def _finish_streaming(self, state: StreamingState) -> tuple[StreamingState, str]:
        """
        Finish streaming and return accumulated content.

        Args:
            state: Current streaming state.

        Returns:
            Tuple of (new_state, final_content).
        """
        if state.is_streaming_response:
            self._renderer.render_response_footer()

        final_content = "".join(state.streaming_content_parts)
        new_state = state.with_streaming_finished()

        return new_state, final_content


# =============================================================================
# Public Facade
# =============================================================================


class StreamDisplay:
    """
    Facade for stream display functionality.

    Handles mixed-mode LangGraph streaming:
    - "updates": Node completion events (tool calls, results)
    - "messages": Token-level streaming for real-time output

    This is the only public-facing class. All implementation details
    are encapsulated in specialized handlers.

    Usage:
        display = StreamDisplay(verbose=True)
        async for mode, chunk in agent_stream:
            result = display.process_stream_chunk(mode, chunk)
            if result:
                final_content = result
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize stream display.

        Args:
            verbose: If True, show detailed output including full tool args.
        """
        # Initialize dependencies
        self._formatter = ToolCallFormatter(verbose=verbose)
        self._renderer = OutputRenderer()
        self._updates_handler = UpdatesChunkHandler(self._renderer, self._formatter)
        self._messages_handler = MessagesChunkHandler(self._renderer)

        # Initialize state
        self._state = StreamingState()

    def process_stream_chunk(self, mode: str, chunk: Any) -> str | None:
        """
        Process a single chunk from mixed-mode LangGraph stream.

        This is the main entry point for handling streaming output.

        Args:
            mode: Stream mode - "updates" or "messages"
            chunk: The chunk data. Structure depends on mode:
                   - "updates": dict with {node_name: {messages: [...]}}
                   - "messages": tuple of (message_chunk, metadata)

        Returns:
            Final complete response content when streaming ends, None otherwise.
        """
        if mode == "updates":
            self._state, result = self._updates_handler.handle(chunk, self._state)
            return result
        elif mode == "messages":
            self._state, result = self._messages_handler.handle(chunk, self._state)
            return result
        return None
