"""Game Service v2.0 - Player Session

Represents a player's session within a room.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.connection_manager import ClientConnection

logger = logging.getLogger(__name__)


@dataclass
class PlayerSession:
    """Player session data within a room."""
    user_id: int
    username: str
    nickname: str = ""
    side: str = ""          # red / black
    rating: int = 1500
    connected: bool = True
    remaining_time: int = 600  # seconds

    # Reference to the WebSocket connection (not persisted)
    _conn: Optional["ClientConnection"] = field(default=None, repr=False)

    @property
    def is_connected(self) -> bool:
        return self.connected and self._conn is not None

    async def send(self, msg: dict) -> bool:
        """Send a message to this player via WebSocket."""
        if not self.is_connected or self._conn is None:
            return False
        return await self._conn.send(msg)

    def disconnect(self) -> None:
        """Mark player as disconnected."""
        self.connected = False

    def reconnect(self, conn: "ClientConnection") -> None:
        """Reconnect player with a new WebSocket connection."""
        self._conn = conn
        self.connected = True
