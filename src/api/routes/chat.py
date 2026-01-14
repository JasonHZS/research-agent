"""Chat routes including WebSocket for streaming."""

import traceback
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from src.api.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    MessageRole,
    WebSocketEvent,
    WebSocketEventType,
)
from src.api.services.agent_service import get_agent_service
from src.api.services.db import get_conversation_store
from src.api.websocket.handler import get_connection_manager

router = APIRouter(prefix="/chat", tags=["chat"])


@router.websocket("/ws/{conversation_id}")
async def websocket_chat(websocket: WebSocket, conversation_id: str):
    """
    WebSocket endpoint for streaming chat.

    Client sends: {"message": "...", "model_provider": "...", "model_name": "..."}
    Server sends: WebSocketEvent objects (token, tool_call_start, tool_call_end, etc.)
    """
    manager = get_connection_manager()
    agent_service = get_agent_service()
    store = get_conversation_store()

    # Validate conversation before accepting the WebSocket handshake
    conversation = await store.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await manager.connect(websocket, conversation_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            print(f"Received WebSocket message: {data}")
            message = data.get("message", "")
            model_provider = data.get("model_provider") or conversation.model_provider
            model_name = data.get("model_name") or conversation.model_name

            if not message:
                print(f"Empty message received, sending error")
                await websocket.send_json(
                    WebSocketEvent(
                        type=WebSocketEventType.ERROR,
                        data={"message": "Empty message"},
                    ).model_dump()
                )
                continue

            print(f"Processing message: {message[:50]}... with provider={model_provider}, model={model_name}")

            # Save user message to database
            await store.add_message(
                conversation_id=conversation_id,
                role="user",
                content=message,
            )
            print(f"User message saved to database")

            # Collect full response and tool calls for saving
            full_response = ""
            all_tool_calls = []

            # Stream response
            print(f"Starting agent stream for conversation {conversation_id}")
            async for event in agent_service.stream_response(
                conversation_id=conversation_id,
                message=message,
                model_provider=model_provider,
                model_name=model_name,
            ):
                # 仅在关键事件时打印，避免大量 TOKEN 日志刷屏
                if event.type in {
                    WebSocketEventType.TOOL_CALL_START,
                    WebSocketEventType.TOOL_CALL_END,
                    WebSocketEventType.MESSAGE_COMPLETE,
                    WebSocketEventType.ERROR,
                }:
                    print(f"Sending event: {event.type}")

                await websocket.send_json(event.model_dump())

                # Collect response content
                if event.type == WebSocketEventType.TOKEN:
                    full_response += event.data.get("content", "")
                elif event.type == WebSocketEventType.TOOL_CALL_END:
                    all_tool_calls.append(event.data)
                elif event.type == WebSocketEventType.MESSAGE_COMPLETE:
                    # Save assistant message to database
                    await store.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=full_response,
                        tool_calls=all_tool_calls,
                    )

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for conversation {conversation_id}")
        manager.disconnect(conversation_id)
    except Exception as e:
        print(f"ERROR in WebSocket handler: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        try:
            await websocket.send_json(
                WebSocketEvent(
                    type=WebSocketEventType.ERROR,
                    data={"message": str(e)},
                ).model_dump()
            )
        except Exception as send_error:
            print(f"Failed to send error message: {send_error}")
        manager.disconnect(conversation_id)


@router.post("/{conversation_id}", response_model=ChatResponse)
async def send_message(conversation_id: str, request: ChatRequest):
    """
    Send a message and get a non-streaming response.

    For streaming responses, use the WebSocket endpoint.
    """
    store = get_conversation_store()
    agent_service = get_agent_service()

    # Check conversation exists
    conv = await store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Save user message
    await store.add_message(
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )

    # Collect response
    full_response = ""
    all_tool_calls = []

    async for event in agent_service.stream_response(
        conversation_id=conversation_id,
        message=request.message,
        model_provider=request.model_provider or conv.model_provider,
        model_name=request.model_name or conv.model_name,
    ):
        if event.type == WebSocketEventType.TOKEN:
            full_response += event.data.get("content", "")
        elif event.type == WebSocketEventType.TOOL_CALL_END:
            all_tool_calls.append(event.data)

    # Save assistant message
    msg = await store.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=full_response,
        tool_calls=all_tool_calls,
    )

    return ChatResponse(
        message=ChatMessage(
            id=msg.id,
            role=MessageRole.ASSISTANT,
            content=full_response,
            tool_calls=all_tool_calls,
            created_at=msg.created_at,
        ),
        conversation_id=conversation_id,
    )
