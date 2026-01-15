"""API Schemas - Pydantic models for request/response validation."""

from src.api.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Conversation,
    ConversationCreate,
    ConversationSummary,
    ModelInfo,
    StreamEvent,
    StreamEventType,
    ToolCall,
    # Backward compatibility aliases
    WebSocketEvent,
    WebSocketEventType,
)

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "Conversation",
    "ConversationCreate",
    "ConversationSummary",
    "ModelInfo",
    "StreamEvent",
    "StreamEventType",
    "ToolCall",
    # Backward compatibility
    "WebSocketEvent",
    "WebSocketEventType",
]
