"""WebSocket connection handler."""

import json
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from src.api.schemas.chat import WebSocketEvent


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        """Initialize connection manager."""
        # conversation_id -> WebSocket
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        # Close existing connection for this conversation if any
        if conversation_id in self._connections:
            try:
                await self._connections[conversation_id].close()
            except Exception:
                pass
        self._connections[conversation_id] = websocket

    def disconnect(self, conversation_id: str) -> None:
        """Remove a WebSocket connection."""
        self._connections.pop(conversation_id, None)

    async def send_event(self, conversation_id: str, event: WebSocketEvent) -> bool:
        """Send an event to a specific conversation's WebSocket."""
        websocket = self._connections.get(conversation_id)
        if websocket:
            try:
                await websocket.send_json(event.model_dump())
                return True
            except Exception:
                self.disconnect(conversation_id)
        return False

    async def send_json(self, conversation_id: str, data: dict) -> bool:
        """Send raw JSON data to a specific conversation's WebSocket."""
        websocket = self._connections.get(conversation_id)
        if websocket:
            try:
                await websocket.send_json(data)
                return True
            except Exception:
                self.disconnect(conversation_id)
        return False

    def is_connected(self, conversation_id: str) -> bool:
        """Check if a conversation has an active WebSocket connection."""
        return conversation_id in self._connections


# Singleton instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get the connection manager singleton."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
