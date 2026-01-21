"""Chat routes with SSE streaming support."""

import json
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.schemas.chat import (
    StreamEvent,
    StreamEventType,
)
from src.api.services.agent_service import get_agent_service
from src.utils.logging_config import bind_context, get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


class ChatStreamRequest(BaseModel):
    """Request body for streaming chat."""

    session_id: str
    message: str
    model_provider: str = "aliyun"
    model_name: str = "qwen-max"
    is_deep_research: bool = False


class ChatResetRequest(BaseModel):
    """Request body for resetting a chat session."""

    session_id: str


@router.post("/stream")
async def stream_chat(request: ChatStreamRequest) -> StreamingResponse:
    """
    SSE streaming endpoint for chat using NDJSON format.

    Each line in the response is a JSON object representing a stream event.
    Events include: token, thinking, tool_call_start, tool_call_end, message_complete, error.

    Example usage with curl:
        curl -X POST http://localhost:8000/api/chat/stream \
            -H "Content-Type: application/json" \
            -d '{"session_id": "test", "message": "Hello"}'
    """
    agent_service = get_agent_service()

    async def event_generator():
        """Generate NDJSON events from agent stream."""
        # Bind session context for all logs in this stream
        bind_context(session_id=request.session_id)

        try:
            # Truncate message for logging to avoid huge log entries
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

            async for event in agent_service.stream_response(
                conversation_id=request.session_id,
                message=request.message,
                model_provider=request.model_provider,
                model_name=request.model_name,
                is_deep_research=request.is_deep_research,
            ):
                # Log key events at debug level to reduce noise
                if event.type in {
                    StreamEventType.TOOL_CALL_START,
                    StreamEventType.TOOL_CALL_END,
                    StreamEventType.MESSAGE_COMPLETE,
                    StreamEventType.ERROR,
                }:
                    logger.debug("Sending event", event_type=event.type)

                # Yield NDJSON line
                yield json.dumps(event.model_dump()) + "\n"

            logger.info("SSE stream completed")

        except Exception as e:
            logger.exception("SSE stream failed", error=str(e))
            # Send error event
            error_event = StreamEvent(
                type=StreamEventType.ERROR,
                data={"message": str(e)},
            )
            yield json.dumps(error_event.model_dump()) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


@router.post("/reset")
async def reset_chat(request: ChatResetRequest) -> dict[str, str]:
    """Reset a chat session and clear any cached state."""
    agent_service = get_agent_service()
    agent_service.remove_agent(request.session_id)
    logger.info("Chat session reset", session_id=request.session_id)
    return {"status": "ok"}
