"""Game Service v2.0 - Player Session

Represents a player's session within a room.
"""

import logging
import time
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
    is_bot: bool = False    # 机器人标记（预留，用于自动对局）
    remaining_time: int = 600  # seconds
    disconnected_at: Optional[float] = None  # time.time() when disconnected

    # Reference to the WebSocket connection (not persisted)
    _conn: Optional["ClientConnection"] = field(default=None, repr=False)

    @property
    def is_connected(self) -> bool:
        return self.connected and self._conn is not None

    @property
    def disconnect_duration(self) -> float:
        """Seconds since disconnected. 0 if connected."""
        if self.connected or self.disconnected_at is None:
            return 0.0
        return time.time() - self.disconnected_at

    async def send(self, msg: dict) -> bool:
        """Send a message to this player via WebSocket."""
        if not self.is_connected or self._conn is None:
            return False
        return await self._conn.send(msg)

    def disconnect(self) -> None:
        """Mark player as disconnected."""
        self.connected = False
        self.disconnected_at = time.time()

    def reconnect(self, conn: "ClientConnection") -> None:
        """Reconnect player with a new WebSocket connection."""
        self._conn = conn
        self.connected = True
        self.disconnected_at = None
