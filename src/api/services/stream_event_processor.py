"""Convert agent runtime streams into API StreamEvent objects."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import suppress
from typing import Any, Optional

from langchain_core.messages import AIMessage

from src.api.schemas.chat import (
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolCallStatus,
)
from src.api.services.message_utils import (
    extract_messages_recursive,
    format_tool_result,
    is_error_result,
    is_stream_disconnect_error,
    sanitize_tool_args,
)
from src.deep_research.state import ClarificationStatus, Section


class StreamEventProcessor:
    """Owns LangGraph stream parsing and fallback event recovery."""

    def __init__(
        self,
        *,
        get_or_create_agent: Callable[..., Any],
        resolve_runtime_settings: Callable[..., Any],
        run_research_stream: Callable[..., Any],
        run_research_async: Callable[..., Any],
        heartbeat_interval_seconds: float,
        heartbeat_fallback_node: str,
        logger: Any,
    ) -> None:
        self._get_or_create_agent = get_or_create_agent
        self._resolve_runtime_settings = resolve_runtime_settings
        self._run_research_stream = run_research_stream
        self._run_research_async = run_research_async
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._heartbeat_fallback_node = heartbeat_fallback_node
        self._logger = logger

    async def stream_agent_events(
        self,
        conversation_id: str,
        message: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream agent response as API events.

        Each request is independent. Historical tool call IDs are loaded first so
        checkpointed tool calls are not re-emitted as new UI events.
        """
        runtime_settings = self._resolve_runtime_settings(
            provider_override=model_provider,
            model_name_override=model_name,
        )

        agent = self._get_or_create_agent(
            conversation_id,
            runtime_settings.llm.provider,
            runtime_settings.llm.model_name,
            is_deep_research=is_deep_research,
        )

        config = {"configurable": {"thread_id": conversation_id}}
        existing_tool_ids: set[str] = set()
        try:
            state = agent.get_state(config)
            if state and state.values:
                existing_messages = extract_messages_recursive(state.values)
                for msg in existing_messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_id = tc.get("id", "")
                            if tool_id:
                                existing_tool_ids.add(tool_id)
            if existing_tool_ids:
                self._logger.debug(
                    "Found existing tool calls in checkpoint",
                    conversation_id=conversation_id,
                    count=len(existing_tool_ids),
                )
        except Exception as e:
            self._logger.warning(
                "Could not retrieve checkpoint state",
                conversation_id=conversation_id,
                error=str(e),
            )

        active_tool_calls: dict[str, ToolCall] = {}
        tool_call_start_times: dict[str, float] = {}
        seen_tool_ids: set[str] = existing_tool_ids.copy()
        tool_call_counter = 0

        clarification_sent = False
        brief_sent = False
        last_progress_node = ""
        last_heartbeat_time = 0.0

        extra_config = None
        max_concurrency = None
        completed_tool_ids: set[str] = set()
        stream = None
        stream_iter = None
        pending_chunk_task: asyncio.Task | None = None

        def emit_progress_if_changed(node_name: str) -> StreamEvent | None:
            nonlocal last_progress_node, last_heartbeat_time
            if not node_name or node_name == last_progress_node:
                return None

            last_progress_node = node_name
            last_heartbeat_time = time.monotonic()
            return StreamEvent(
                type=StreamEventType.PROGRESS,
                data={"node": node_name},
            )

        def build_tool_call_start(tc: dict[str, Any]) -> tuple[str, ToolCall]:
            nonlocal tool_call_counter
            tool_id = tc.get("id", f"tc_{tool_call_counter}")
            tool_call_counter += 1
            sanitized_args = sanitize_tool_args(tc.get("args", {}))
            tool_call = ToolCall(
                id=tool_id,
                name=tc.get("name", "unknown"),
                args=sanitized_args,
                status=ToolCallStatus.RUNNING,
            )
            active_tool_calls[tool_id] = tool_call
            tool_call_start_times[tool_id] = time.time()
            return tool_id, tool_call

        def complete_tool_call(tool_id: str, content: Any) -> tuple[ToolCall, float | None, bool]:
            tool_call = active_tool_calls[tool_id]
            tool_call.result = format_tool_result(content)
            is_error = is_error_result(tool_call.result)
            tool_call.status = ToolCallStatus.FAILED if is_error else ToolCallStatus.COMPLETED
            completed_tool_ids.add(tool_id)

            start_time = tool_call_start_times.get(tool_id)
            duration_ms = round((time.time() - start_time) * 1000, 2) if start_time else None
            return tool_call, duration_ms, is_error

        def build_section_list(sections: Any) -> list[dict[str, str]]:
            section_list = []
            for section in sections:
                if isinstance(section, Section):
                    section_list.append(
                        {
                            "title": section.title,
                            "description": section.description,
                        }
                    )
                elif isinstance(section, dict):
                    section_list.append(
                        {
                            "title": section.get("title", ""),
                            "description": section.get("description", ""),
                        }
                    )
            return section_list

        try:
            if is_deep_research:
                extra_config = {
                    "verbose": True,
                    "model_provider": runtime_settings.llm.provider,
                    "model_name": runtime_settings.llm.model_name,
                    "max_iterations": runtime_settings.deep_research.max_iterations,
                    "max_tool_calls": runtime_settings.deep_research.max_tool_calls,
                }
                max_concurrency = runtime_settings.deep_research.max_concurrent

            stream = self._run_research_stream(
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
                    done, _ = await asyncio.wait(
                        {pending_chunk_task},
                        timeout=self._heartbeat_interval_seconds,
                    )
                    if not done:
                        last_heartbeat_time = time.monotonic()
                        yield StreamEvent(
                            type=StreamEventType.PROGRESS,
                            data={"node": last_progress_node or self._heartbeat_fallback_node},
                        )
                        continue

                try:
                    mode, chunk = await pending_chunk_task
                except StopAsyncIteration:
                    pending_chunk_task = None
                    break

                pending_chunk_task = asyncio.create_task(anext(stream_iter))

                if mode == "messages":
                    message_chunk, metadata = chunk
                    if not isinstance(message_chunk, AIMessage):
                        continue

                    if is_deep_research:
                        current_node = metadata.get("langgraph_node", "")
                        progress_event = emit_progress_if_changed(current_node)
                        if progress_event is not None:
                            yield progress_event
                        if current_node not in {"final_report"}:
                            continue

                    if hasattr(message_chunk, "content") and message_chunk.content:
                        content = message_chunk.content
                        if isinstance(content, str) and content:
                            yield StreamEvent(
                                type=StreamEventType.TOKEN,
                                data={"content": content},
                            )
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
                    for node_name, node_data in chunk.items():
                        if node_data is None:
                            continue
                        if is_deep_research:
                            progress_event = emit_progress_if_changed(node_name)
                            if progress_event is not None:
                                yield progress_event

                        tool_calls_log = (
                            node_data.get("tool_calls_log") if isinstance(node_data, dict) else None
                        )
                        if hasattr(tool_calls_log, "value"):
                            tool_calls_log = tool_calls_log.value

                        if is_deep_research and not clarification_sent:
                            clarification_status = node_data.get("clarification_status")
                            if hasattr(clarification_status, "value"):
                                clarification_status = clarification_status.value

                            if clarification_status is not None:
                                need_clarification = False
                                question = ""
                                verification = ""

                                if isinstance(clarification_status, ClarificationStatus):
                                    need_clarification = clarification_status.need_clarification
                                    question = clarification_status.question
                                    verification = clarification_status.verification
                                elif isinstance(clarification_status, dict):
                                    need_clarification = clarification_status.get(
                                        "need_clarification", False
                                    )
                                    question = clarification_status.get("question", "")
                                    verification = clarification_status.get("verification", "")

                                if need_clarification and question:
                                    yield StreamEvent(
                                        type=StreamEventType.CLARIFICATION,
                                        data={"question": question},
                                    )
                                    clarification_sent = True
                                elif not need_clarification and verification:
                                    yield StreamEvent(
                                        type=StreamEventType.TOKEN,
                                        data={"content": verification},
                                    )

                        if is_deep_research and not brief_sent:
                            research_brief = node_data.get("research_brief")
                            sections = node_data.get("sections")

                            if hasattr(research_brief, "value"):
                                research_brief = research_brief.value
                            if hasattr(sections, "value"):
                                sections = sections.value

                            if research_brief and sections:
                                section_list = build_section_list(sections)
                                if section_list:
                                    yield StreamEvent(
                                        type=StreamEventType.BRIEF,
                                        data={
                                            "research_brief": research_brief,
                                            "sections": section_list,
                                        },
                                    )
                                    brief_sent = True

                        all_messages = extract_messages_recursive(node_data)
                        for msg in all_messages:
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    tool_id = tc.get("id", f"tc_{tool_call_counter}")

                                    if tool_id in seen_tool_ids:
                                        continue

                                    seen_tool_ids.add(tool_id)
                                    tool_id, tool_call = build_tool_call_start(tc)

                                    self._logger.info(
                                        "Tool call started",
                                        tool_id=tool_id,
                                        tool_name=tool_call.name,
                                        tool_args=tool_call.args,
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
                                    tool_call, duration_ms, is_error = complete_tool_call(
                                        tool_id,
                                        getattr(msg, "content", None),
                                    )

                                    result_preview = (
                                        str(tool_call.result)[:200] if tool_call.result else None
                                    )
                                    if is_error:
                                        self._logger.warning(
                                            "Tool call failed",
                                            tool_id=tool_id,
                                            tool_name=tool_call.name,
                                            duration_ms=duration_ms,
                                            error_preview=result_preview,
                                            conversation_id=conversation_id,
                                        )
                                    else:
                                        self._logger.info(
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

            yield StreamEvent(
                type=StreamEventType.MESSAGE_COMPLETE,
                data={
                    "tool_calls": [tc.model_dump() for tc in active_tool_calls.values()],
                    "is_clarification": clarification_sent,
                },
            )

        except Exception as e:
            if is_stream_disconnect_error(e):
                self._logger.warning(
                    "Streaming connection closed early, retrying with non-streaming",
                    conversation_id=conversation_id,
                )

                max_retries = 5
                base_delay = 1.0

                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            delay = base_delay * (2 ** (attempt - 1))
                            self._logger.info(
                                "Retry attempt",
                                attempt=attempt + 1,
                                max_retries=max_retries,
                                delay_seconds=delay,
                                conversation_id=conversation_id,
                            )
                            await asyncio.sleep(delay)

                        final_text = await self._run_research_async(
                            query=message,
                            agent=agent,
                            thread_id=conversation_id,
                        )
                        if final_text:
                            yield StreamEvent(
                                type=StreamEventType.TOKEN,
                                data={"content": final_text},
                            )

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
                                        section_list = build_section_list(sections)
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

                        try:
                            fallback_state = agent.get_state(
                                {"configurable": {"thread_id": conversation_id}}
                            )
                            if fallback_state and fallback_state.values:
                                fallback_messages = extract_messages_recursive(
                                    fallback_state.values
                                )
                                for msg in fallback_messages:
                                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                                        for tc in msg.tool_calls:
                                            tool_id = tc.get("id", f"tc_{tool_call_counter}")
                                            if tool_id in seen_tool_ids:
                                                continue
                                            seen_tool_ids.add(tool_id)
                                            tool_id, tool_call = build_tool_call_start(tc)

                                            self._logger.info(
                                                "Tool call started (fallback)",
                                                tool_id=tool_id,
                                                tool_name=tool_call.name,
                                                tool_args=tool_call.args,
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
                                            tool_call, duration_ms, is_error = complete_tool_call(
                                                tool_id,
                                                getattr(msg, "content", None),
                                            )

                                            result_preview = (
                                                str(tool_call.result)[:200]
                                                if tool_call.result
                                                else None
                                            )
                                            if is_error:
                                                self._logger.warning(
                                                    "Tool call failed (fallback)",
                                                    tool_id=tool_id,
                                                    tool_name=tool_call.name,
                                                    duration_ms=duration_ms,
                                                    error_preview=result_preview,
                                                    conversation_id=conversation_id,
                                                )
                                            else:
                                                self._logger.info(
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
                            self._logger.warning(
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
                                    clarification_status = state.values.get("clarification_status")
                                    if hasattr(clarification_status, "value"):
                                        clarification_status = clarification_status.value
                                    if isinstance(clarification_status, ClarificationStatus):
                                        is_clarification = clarification_status.need_clarification
                                    elif isinstance(clarification_status, dict):
                                        is_clarification = clarification_status.get(
                                            "need_clarification", False
                                        )
                            except Exception as state_error:
                                self._logger.warning(
                                    "Could not read clarification status from state",
                                    conversation_id=conversation_id,
                                    error=str(state_error),
                                )

                        yield StreamEvent(
                            type=StreamEventType.MESSAGE_COMPLETE,
                            data={
                                "tool_calls": [
                                    tc.model_dump() for tc in active_tool_calls.values()
                                ],
                                "is_clarification": is_clarification,
                            },
                        )
                        return

                    except Exception as fallback_error:
                        retryable = is_stream_disconnect_error(fallback_error)

                        if retryable and attempt < max_retries - 1:
                            self._logger.warning(
                                "Retry failed with retryable error",
                                attempt=attempt + 1,
                                conversation_id=conversation_id,
                                error=str(fallback_error),
                            )
                            continue

                        self._logger.error(
                            "Non-streaming fallback failed",
                            attempt=attempt + 1,
                            conversation_id=conversation_id,
                            error=str(fallback_error),
                            exc_info=True,
                        )
                        break

            self._logger.exception(
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
