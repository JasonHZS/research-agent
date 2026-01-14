"""Conversations CRUD routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.api.schemas.chat import (
    ChatMessage,
    Conversation,
    ConversationCreate,
    ConversationSummary,
    MessageRole,
)
from src.api.services.agent_service import get_agent_service
from src.api.services.db import get_conversation_store

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations():
    """List all conversations."""
    store = get_conversation_store()
    conversations = await store.list_conversations()

    return [
        ConversationSummary(
            id=conv.id,
            title=conv.title,
            model_provider=conv.model_provider,
            model_name=conv.model_name,
            message_count=getattr(conv, "message_count", 0),
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )
        for conv in conversations
    ]


@router.post("", response_model=ConversationSummary)
async def create_conversation(request: ConversationCreate):
    """Create a new conversation."""
    store = get_conversation_store()
    conv = await store.create_conversation(
        title=request.title,
        model_provider=request.model_provider or "aliyun",
        model_name=request.model_name or "qwen-max",
    )

    return ConversationSummary(
        id=conv.id,
        title=conv.title,
        model_provider=conv.model_provider,
        model_name=conv.model_name,
        message_count=0,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a conversation with all messages."""
    store = get_conversation_store()
    conv = await store.get_conversation(conversation_id)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Use _loaded_messages to avoid lazy loading issues
    loaded_messages = getattr(conv, "_loaded_messages", None) or []
    messages = [
        ChatMessage(
            id=msg.id,
            role=MessageRole(msg.role),
            content=msg.content,
            tool_calls=msg.tool_calls or [],
            created_at=msg.created_at,
        )
        for msg in loaded_messages
    ]

    return Conversation(
        id=conv.id,
        title=conv.title,
        model_provider=conv.model_provider,
        model_name=conv.model_name,
        messages=messages,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    store = get_conversation_store()
    deleted = await store.delete_conversation(conversation_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Also remove agent instance
    agent_service = get_agent_service()
    agent_service.remove_agent(conversation_id)

    return {"status": "deleted", "conversation_id": conversation_id}


@router.patch("/{conversation_id}/title")
async def update_conversation_title(conversation_id: str, title: str):
    """Update conversation title."""
    store = get_conversation_store()
    conv = await store.update_conversation_title(conversation_id, title)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"status": "updated", "title": conv.title}
