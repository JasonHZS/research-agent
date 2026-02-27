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
from src.api.schemas.feeds import FeedDigestItem, FeedDigestResponse

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "Conversation",
    "ConversationCreate",
    "ConversationSummary",
    "FeedDigestItem",
    "FeedDigestResponse",
    "ModelInfo",
    "StreamEvent",
    "StreamEventType",
    "ToolCall",
    # Backward compatibility
    "WebSocketEvent",
    "WebSocketEventType",
]
