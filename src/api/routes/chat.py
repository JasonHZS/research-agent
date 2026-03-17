"""Chat routes with SSE streaming support."""

import asyncio
import json
from contextlib import suppress
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.auth import get_current_user
from src.api.schemas.chat import (
    StreamEvent,
    StreamEventType,
)
from src.api.services.agent_service import get_agent_service
from src.utils.logging_config import bind_context, get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)
SSE_COMMENT_HEARTBEAT_SECONDS = 10.0


class ChatStreamRequest(BaseModel):
    """Request body for streaming chat."""

    session_id: str
    message: str
    request_id: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    is_deep_research: bool = False


class ChatResetRequest(BaseModel):
    """Request body for resetting a chat session."""

    session_id: str


def _format_sse_event(event: StreamEvent) -> str:
    """Serialize a StreamEvent as a standard SSE frame."""
    payload = json.dumps(event.data, ensure_ascii=False)
    event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _format_sse_comment(comment: str = "") -> str:
    """Serialize an SSE comment frame used for transport-level keepalive."""
    return f": {comment}\n\n" if comment else ":\n\n"


def _streaming_response(stream_factory, session_id: str = "") -> StreamingResponse:
    async def event_generator():
        stream = None
        stream_iter = None
        pending_event_task: asyncio.Task | None = None

        try:
            yield _format_sse_comment("open")

            stream = stream_factory()
            stream_iter = stream.__aiter__()
            pending_event_task = asyncio.create_task(anext(stream_iter))

            while True:
                done, _ = await asyncio.wait(
                    {pending_event_task},
                    timeout=SSE_COMMENT_HEARTBEAT_SECONDS,
                )
                if not done:
                    yield _format_sse_comment()
                    continue

                try:
                    event = await pending_event_task
                except StopAsyncIteration:
                    pending_event_task = None
                    break

                pending_event_task = asyncio.create_task(anext(stream_iter))

                if event.type in {
                    StreamEventType.SNAPSHOT,
                    StreamEventType.TOOL_CALL_START,
                    StreamEventType.TOOL_CALL_END,
                    StreamEventType.MESSAGE_COMPLETE,
                    StreamEventType.ERROR,
                }:
                    logger.debug("Sending event", event_type=event.type)

                yield _format_sse_event(event)

            logger.info("SSE stream completed", session_id=session_id)
        except Exception as e:
            logger.exception("SSE stream failed", error=str(e))
            yield _format_sse_event(
                StreamEvent(
                    type=StreamEventType.ERROR,
                    data={"message": str(e)},
                )
            )
        finally:
            if pending_event_task is not None and not pending_event_task.done():
                pending_event_task.cancel()
                with suppress(asyncio.CancelledError):
                    await pending_event_task
            if stream is not None and hasattr(stream, "aclose"):
                with suppress(Exception):
                    await stream.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stream")
async def stream_chat(
    request: ChatStreamRequest,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """
    SSE streaming endpoint for chat using standard event-stream framing.

    The stream uses `text/event-stream` and frames each application event as:
    `event: <type>\\ndata: <json>\\n\\n`.

    Example usage with curl:
        curl -X POST http://localhost:8111/api/chat/stream \
            -H "Content-Type: application/json" \
            -H "Accept: text/event-stream" \
            -d '{"session_id": "test", "message": "Hello"}'
    """
    agent_service = get_agent_service()
    bind_context(session_id=request.session_id)

    message_preview = (
        request.message[:50] + "..."
        if len(request.message) > 50
        else request.message
    )
    logger.info(
        "SSE stream started",
        message_preview=message_preview,
        model_provider=request.model_provider,
        model_name=request.model_name,
        is_deep_research=request.is_deep_research,
    )

    try:
        agent_service.start_background_run(
            conversation_id=request.session_id,
            message=request.message,
            model_provider=request.model_provider,
            model_name=request.model_name,
            is_deep_research=request.is_deep_research,
            request_id=request.request_id,
        )
    except ValueError as start_error:
        raise HTTPException(status_code=409, detail=str(start_error)) from start_error

    return _streaming_response(
        lambda: agent_service.subscribe_to_run(request.session_id),
        session_id=request.session_id,
    )


@router.get("/stream/{session_id}")
async def resume_stream(
    session_id: str,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """Subscribe to an existing in-flight background run."""
    agent_service = get_agent_service()
    bind_context(session_id=session_id)

    if not agent_service.has_background_run(session_id):
        raise HTTPException(status_code=404, detail="No active or resumable run found")

    logger.info("SSE stream resumed", session_id=session_id)
    return _streaming_response(
        lambda: agent_service.subscribe_to_run(session_id),
        session_id=session_id,
    )


@router.post("/reset")
async def reset_chat(
    request: ChatResetRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """Reset a chat session and clear any cached state."""
    agent_service = get_agent_service()
    agent_service.remove_agent(request.session_id)
    logger.info("Chat session reset", session_id=request.session_id)
    return {"status": "ok"}
