"""WebSocket module."""

from src.api.websocket.handler import ConnectionManager, get_connection_manager

__all__ = ["ConnectionManager", "get_connection_manager"]
