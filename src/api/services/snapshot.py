"""StreamingSnapshot data structure and segment manipulation operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.api.schemas.chat import StreamEvent, StreamEventType
from src.deep_research.state import ClarificationStatus, Section


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


# ---------------------------------------------------------------------------
# Segment manipulation helpers (pure functions)
# ---------------------------------------------------------------------------


def append_text_segment(
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


def set_text_segment(
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


def append_tool_call_segment(
    segments: list[dict[str, Any]],
    tool_call: dict[str, Any],
) -> list[dict[str, Any]]:
    updated_segments = [dict(segment) for segment in segments]
    if updated_segments and updated_segments[-1].get("type") == "tool_calls":
        last_segment = dict(updated_segments[-1])
        existing_tool_calls = [
            dict(existing_tool_call) for existing_tool_call in last_segment.get("toolCalls", [])
        ]
        if all(tc.get("status") == "running" for tc in existing_tool_calls):
            existing_tool_calls.append(dict(tool_call))
            last_segment["toolCalls"] = existing_tool_calls
            updated_segments[-1] = last_segment
            return updated_segments

    updated_segments.append({"type": "tool_calls", "toolCalls": [dict(tool_call)]})
    return updated_segments


def replace_tool_call(
    tool_calls: list[dict[str, Any]],
    tool_call: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        dict(tool_call)
        if existing_tool_call.get("id") == tool_call.get("id")
        else dict(existing_tool_call)
        for existing_tool_call in tool_calls
    ]


def replace_tool_call_in_segments(
    segments: list[dict[str, Any]],
    tool_call: dict[str, Any],
) -> list[dict[str, Any]]:
    updated_segments: list[dict[str, Any]] = []
    for segment in segments:
        updated_segment = dict(segment)
        if updated_segment.get("type") == "tool_calls":
            updated_segment["toolCalls"] = replace_tool_call(
                updated_segment.get("toolCalls", []),
                tool_call,
            )
        updated_segments.append(updated_segment)
    return updated_segments


def _section_title(section: Section | dict[str, Any]) -> str:
    return section.title if isinstance(section, Section) else section.get("title", "")


def _section_description(section: Section | dict[str, Any]) -> str:
    return section.description if isinstance(section, Section) else section.get("description", "")


# ---------------------------------------------------------------------------
# Event -> Snapshot application
# ---------------------------------------------------------------------------


def apply_event_to_snapshot(
    snapshot: StreamingSnapshot,
    event: StreamEvent,
) -> None:
    """Apply a single StreamEvent to a StreamingSnapshot, mutating it in place."""
    if event.type == StreamEventType.TOKEN:
        content = str(event.data.get("content", ""))
        snapshot.append_content(content)
        snapshot.segments = append_text_segment(snapshot.segments, content)
    elif event.type == StreamEventType.THINKING:
        snapshot.append_thinking(str(event.data.get("content", "")))
    elif event.type == StreamEventType.TOOL_CALL_START:
        tc = dict(event.data)
        snapshot.tool_calls.append(tc)
        snapshot.segments = append_tool_call_segment(snapshot.segments, tc)
    elif event.type == StreamEventType.TOOL_CALL_END:
        tc = dict(event.data)
        snapshot.tool_calls = replace_tool_call(snapshot.tool_calls, tc)
        snapshot.segments = replace_tool_call_in_segments(snapshot.segments, tc)
    elif event.type == StreamEventType.CLARIFICATION:
        question = str(event.data.get("question", ""))
        snapshot.content = question
        snapshot.segments = set_text_segment(snapshot.segments, question)
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
        snapshot.segments = append_text_segment(
            snapshot.segments,
            f"\n\n{brief_content}" if snapshot.segments else brief_content,
        )
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


# ---------------------------------------------------------------------------
# Build a full snapshot dict from agent graph state (for late-joining clients)
# ---------------------------------------------------------------------------


def build_snapshot_from_state(
    agent: Any,
    conversation_id: str,
    run_snapshot: StreamingSnapshot,
    logger: Any,
) -> dict[str, Any]:
    """Build a serializable snapshot dict, enriching from agent state if possible."""
    snapshot = StreamingSnapshot(
        request_id=run_snapshot.request_id,
        tool_calls=[dict(tc) for tc in run_snapshot.tool_calls],
        segments=[dict(seg) for seg in run_snapshot.segments],
        progress_node=run_snapshot.progress_node,
        is_clarification=run_snapshot.is_clarification,
        is_running=run_snapshot.is_running,
        error=run_snapshot.error,
    )
    snapshot.content = run_snapshot.content
    snapshot.thinking_content = run_snapshot.thinking_content

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
                        f"### {index + 1}. {_section_title(section)}\n\n"
                        f"{_section_description(section)}"
                        for index, section in enumerate(sections)
                    )
                    brief_content = (
                        f"## 研究大纲\n\n{sections_text}" if sections_text else "## 研究大纲"
                    )
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
