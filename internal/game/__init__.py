"""Game service - WebSocket server for real-time Xiangqi games."""
from .player_session import PlayerSession, ConnectionState


def get_websocket_server():
    """Lazy import for WebSocketServer."""
    from .websocket_server import WebSocketServer
    return WebSocketServer


def get_room_manager():
    """Lazy import for RoomManager."""
    from .room_manager import RoomManager
    return RoomManager


def get_message_handler():
    """Lazy import for MessageHandler."""
    from .message_handler import MessageHandler
    return MessageHandler


__all__ = [
    "PlayerSession",
    "ConnectionState",
    "get_websocket_server",
    "get_room_manager",
    "get_message_handler",
]
