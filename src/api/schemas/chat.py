"""Pydantic schemas for chat API."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ToolCallStatus(str, Enum):
    """Status of a tool call."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolCall(BaseModel):
    """Tool call information."""

    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    status: ToolCallStatus = ToolCallStatus.RUNNING


class ChatMessage(BaseModel):
    """A single chat message."""

    id: str
    role: MessageRole
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    message: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from chat endpoint (non-streaming)."""

    message: ChatMessage
    conversation_id: str


class ConversationCreate(BaseModel):
    """Request to create a new conversation."""

    title: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None


class ConversationSummary(BaseModel):
    """Summary of a conversation for list view."""

    id: str
    title: str
    model_provider: str
    model_name: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class Conversation(BaseModel):
    """Full conversation with messages."""

    id: str
    title: str
    model_provider: str
    model_name: str
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StreamEventType(str, Enum):
    """Types of streaming events (transport-agnostic)."""

    TOKEN = "token"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    MESSAGE_COMPLETE = "message_complete"
    ERROR = "error"
    THINKING = "thinking"


class StreamEvent(BaseModel):
    """Streaming event message (transport-agnostic)."""

    type: StreamEventType
    data: Any = None


# Backward compatibility aliases
WebSocketEventType = StreamEventType
WebSocketEvent = StreamEvent


class ModelInfo(BaseModel):
    """Information about an available model."""

    provider: str
    name: str
    display_name: str
    supports_thinking: bool = False


class ModelsResponse(BaseModel):
    """Response for models endpoint."""

    models: list[ModelInfo]
    current_provider: str
    current_model: str
