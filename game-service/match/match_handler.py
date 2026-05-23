"""Game Service v2.0 - Match Handler

Handles match-related WebSocket messages.
"""

import logging

from gateway.connection_manager import ClientConnection
from gateway.connection_state import ConnectionState
from match.match_service import MatchService
from room.room_manager import RoomManager
from user.user_service import UserService

logger = logging.getLogger(__name__)


class MatchHandler:
    """Handles match-related WebSocket messages."""

    def __init__(self, match_service: MatchService, room_manager: RoomManager,
                 user_service: UserService):
        self.match_service = match_service
        self.room_manager = room_manager
        self.user_service = user_service

    async def handle(self, conn: ClientConnection, msg: dict) -> None:
        """Route match message to the appropriate handler."""
        handlers = {
            "match_join": self._join,
            "match_leave": self._leave,
        }
        handler = handlers.get(msg.get("type", ""))
        if handler:
            await handler(conn, msg)
        else:
            seq = msg.get("seq", 0)
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 1002, "message": "Unknown match message type"},
            })

    async def _join(self, conn: ClientConnection, msg: dict) -> None:
        """Handle match_join message."""
        seq = msg.get("seq", 0)

        # Check if already in room
        if self.room_manager.is_user_in_room(conn.user_id):
            logger.warning(f"Match join rejected: user={conn.user_id} already in room")
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 3004, "message": "Already in a room"},
            })
            return

        # Get user rating
        user_info = await self.user_service.get_user_info(conn.user_id)
        rating = user_info.get("rating", 1500) if user_info else 1500

        result = await self.match_service.join_match(
            user_id=conn.user_id,
            username=conn.username or "",
            rating=rating,
        )

        if "error" in result:
            logger.info(f"Match join failed: user={conn.user_id}, error={result['error']}")
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 3005, "message": result["error"]},
            })
            return

        conn.set_state(ConnectionState.MATCHMAKING)
        logger.info(f"User {conn.username}(id={conn.user_id}, rating={rating}) joined match queue, position={result.get('position')}")

        await conn.send({
            "type": "match_queued",
            "seq": seq,
            "data": result,
        })

    async def _leave(self, conn: ClientConnection, msg: dict) -> None:
        """Handle match_leave message."""
        seq = msg.get("seq", 0)

        success = await self.match_service.leave_match(conn.user_id)
        logger.info(f"User {conn.username}(id={conn.user_id}) left match queue, success={success}")

        if success:
            conn.set_state(ConnectionState.AUTHENTICATED)

        await conn.send({
            "type": "match_left",
            "seq": seq,
            "data": {"success": success},
        })
