"""Game Service v2.0 - WebSocket Gateway - Message Router

Routes incoming WebSocket messages to the appropriate handler
based on message type prefix and connection state.
"""

import logging
from typing import Any, Optional

from gateway.connection_manager import ClientConnection
from gateway.connection_state import ConnectionState

logger = logging.getLogger(__name__)

# Messages allowed in each state
STATE_ALLOWED_MESSAGES: dict[ConnectionState, set[str]] = {
    ConnectionState.UNAUTHENTICATED: {
        "auth_login", "auth_register", "auth_token", "auth_refresh", "reconnect",
        "ping",
    },
    ConnectionState.AUTHENTICATED: {
        "user_get_me", "user_update_profile", "user_get_rankings",
        "user_get_history",
        "room_create", "room_list", "room_join", "room_leave",
        "match_join", "match_leave",
        "auth_refresh",
        "admin_users", "admin_ban", "admin_stats", "admin_models",
        "ping",
    },
    ConnectionState.IN_ROOM: {
        "user_get_me", "user_get_rankings", "user_get_history",
        "game_move", "game_resign", "game_draw_req", "game_draw_ans",
        "game_ready", "game_rematch",
        "room_leave", "room_list",
        "reconnect",
        "ping",
    },
    ConnectionState.MATCHMAKING: {
        "match_leave",
        "ping",
    },
}


class MessageRouter:
    """Routes incoming messages to the appropriate handler."""

    def __init__(self):
        self._handlers: dict[str, Any] = {}  # prefix -> handler instance

    def register_handler(self, prefix: str, handler: Any) -> None:
        """Register a handler for a message type prefix.

        Example: register_handler("auth", auth_handler)
        Messages like "auth_login", "auth_register" will be routed to auth_handler.
        """
        self._handlers[prefix] = handler

    async def route(self, conn: ClientConnection, msg: dict) -> None:
        """Route an incoming message to the appropriate handler.

        Args:
            conn: The client connection that sent the message.
            msg: The parsed message dict with at least a "type" key.
        """
        msg_type = msg.get("type", "")
        seq = msg.get("seq", 0)

        logger.debug(f"Routing msg type={msg_type} seq={seq} from user={conn.user_id} state={conn.state.name}")

        # Handle ping directly
        if msg_type == "ping":
            import time
            await conn.send({
                "type": "pong",
                "seq": seq,
                "data": {"timestamp": int(time.time() * 1000)},
            })
            return

        # Check state-based access control
        allowed = STATE_ALLOWED_MESSAGES.get(conn.state, set())
        if msg_type not in allowed:
            logger.warning(
                f"Message {msg_type} not allowed in state {conn.state.name} "
                f"for user={conn.user_id}"
            )
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {
                    "code": 1001,
                    "message": f"Message '{msg_type}' not allowed in current state",
                },
            })
            return

        # Route to handler by prefix
        prefix = msg_type.split("_")[0]
        handler = self._handlers.get(prefix)

        if handler is None:
            logger.warning(f"No handler registered for prefix: {prefix}")
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {
                    "code": 1002,
                    "message": f"Unknown message type: {msg_type}",
                },
            })
            return

        try:
            await handler.handle(conn, msg)
        except Exception as e:
            logger.error(f"Handler error for {msg_type}: {e}", exc_info=True)
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {
                    "code": 1000,
                    "message": "Internal server error",
                },
            })
