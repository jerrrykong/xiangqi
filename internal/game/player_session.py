"""Player session management for WebSocket connections."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import asyncio
import uuid


class ConnectionState(Enum):
    """WebSocket connection state."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


@dataclass
class PlayerSession:
    """Represents a player's WebSocket session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[int] = None
    username: Optional[str] = None
    room_id: Optional[str] = None
    side: Optional[str] = None  # "red" or "black"
    state: ConnectionState = ConnectionState.CONNECTED
    token: str = ""  # 用于断线重连验证
    websocket = None  # WebSocket connection, set externally
    last_active: float = 0.0  # Unix timestamp
    remaining_time: int = 600  # 秒
    opponent_session_id: Optional[str] = None

    def is_connected(self) -> bool:
        """Check if the session is connected."""
        return self.state == ConnectionState.CONNECTED

    def is_in_game(self) -> bool:
        """Check if the player is in a game."""
        return self.room_id is not None and self.side is not None

    def is_red(self) -> bool:
        """Check if the player is red side."""
        return self.side == "red"

    def is_black(self) -> bool:
        """Check if the player is black side."""
        return self.side == "black"

    def get_color(self) -> str:
        """Get the color as a string."""
        return self.side or "none"

    def disconnect(self) -> None:
        """Mark the session as disconnected."""
        self.state = ConnectionState.DISCONNECTED

    def reconnect(self) -> None:
        """Mark the session as reconnecting."""
        self.state = ConnectionState.RECONNECTING

    def restore(self) -> None:
        """Restore connection after reconnect."""
        self.state = ConnectionState.CONNECTED

    def update_activity(self) -> None:
        """Update last active timestamp."""
        import time
        self.last_active = time.time()

    def deduct_time(self, seconds: int) -> int:
        """Deduct time and return remaining time."""
        self.remaining_time = max(0, self.remaining_time - seconds)
        return self.remaining_time

    def to_dict(self) -> dict:
        """Serialize to dict for state sync."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "username": self.username,
            "room_id": self.room_id,
            "side": self.side,
            "state": self.state.value,
            "remaining_time": self.remaining_time,
        }
