"""Game Service v2.0 - WebSocket Gateway - Connection Manager

Manages all active WebSocket connections, lifecycle, and heartbeat.
"""

import asyncio
import logging
import time
from typing import Optional

from fastapi import WebSocket

from gateway.connection_state import ConnectionState, can_transition

logger = logging.getLogger(__name__)


class ClientConnection:
    """Represents a single WebSocket client connection."""

    def __init__(self, ws: WebSocket, conn_id: str):
        self.ws = ws
        self.conn_id = conn_id
        self.user_id: Optional[int] = None
        self.username: Optional[str] = None
        self.state = ConnectionState.UNAUTHENTICATED
        self.room_id: Optional[str] = None
        self.session_token: Optional[str] = None
        self.is_admin: bool = False
        self.last_ping: float = time.time()
        self._connected = True

    async def send(self, data: dict) -> bool:
        """Send JSON data to the client. Returns False if send failed."""
        if not self._connected:
            return False
        try:
            await self.ws.send_json(data)
            return True
        except Exception as e:
            logger.warning(f"Send failed for conn={self.conn_id}: {e}")
            self._connected = False
            return False

    async def kick(self, reason: str = "") -> None:
        """Close the client connection."""
        if not self._connected:
            return
        self._connected = False
        try:
            await self.ws.close(code=1000, reason=reason)
        except Exception:
            pass

    def set_state(self, new_state: ConnectionState) -> bool:
        """Transition to a new state. Returns True if valid."""
        if can_transition(self.state, new_state):
            self.state = new_state
            return True
        logger.warning(
            f"Invalid state transition: {self.state.name} -> {new_state.name} "
            f"for user={self.user_id}"
        )
        return False

    @property
    def is_authenticated(self) -> bool:
        return self.state != ConnectionState.UNAUTHENTICATED

    def __repr__(self) -> str:
        return (
            f"ClientConnection(conn_id={self.conn_id}, user_id={self.user_id}, "
            f"state={self.state.name})"
        )


class ConnectionManager:
    """Manages all active WebSocket connections."""

    def __init__(self):
        self._connections: dict[str, ClientConnection] = {}  # conn_id -> connection
        self._user_connections: dict[int, str] = {}  # user_id -> conn_id

    def register(self, conn: ClientConnection) -> None:
        """Register a new connection."""
        self._connections[conn.conn_id] = conn

    def bind_user(self, conn: ClientConnection, user_id: int) -> None:
        """Bind a user to a connection after authentication."""
        # Kick existing connection for the same user
        if user_id in self._user_connections:
            old_conn_id = self._user_connections[user_id]
            old_conn = self._connections.get(old_conn_id)
            if old_conn:
                asyncio.create_task(old_conn.kick("Replaced by new connection"))

        conn.user_id = user_id
        self._user_connections[user_id] = conn.conn_id

    def unregister(self, conn: ClientConnection) -> None:
        """Unregister a connection."""
        self._connections.pop(conn.conn_id, None)
        if conn.user_id and self._user_connections.get(conn.user_id) == conn.conn_id:
            self._user_connections.pop(conn.user_id, None)

    def get_by_user_id(self, user_id: int) -> Optional[ClientConnection]:
        """Get connection by user ID."""
        conn_id = self._user_connections.get(user_id)
        if conn_id:
            return self._connections.get(conn_id)
        return None

    def get_by_conn_id(self, conn_id: str) -> Optional[ClientConnection]:
        """Get connection by connection ID."""
        return self._connections.get(conn_id)

    async def send_to_user(self, user_id: int, data: dict) -> bool:
        """Send data to a specific user."""
        conn = self.get_by_user_id(user_id)
        if conn:
            return await conn.send(data)
        return False

    async def broadcast(self, data: dict, exclude: Optional[set[int]] = None) -> None:
        """Broadcast data to all authenticated connections."""
        for conn in self._connections.values():
            if conn.is_authenticated:
                if exclude and conn.user_id in exclude:
                    continue
                await conn.send(data)

    @property
    def online_count(self) -> int:
        """Number of authenticated online users."""
        return len(self._user_connections)

    @property
    def total_connections(self) -> int:
        """Total number of connections (including unauthenticated)."""
        return len(self._connections)
