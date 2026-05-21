"""Game Service v2.0 - User Handler

Handles all user-related WebSocket messages.
"""

import logging

from gateway.connection_manager import ClientConnection
from user.user_service import UserService

logger = logging.getLogger(__name__)


class UserHandler:
    """Handles all user-related WebSocket messages."""

    def __init__(self, user_service: UserService):
        self.user_service = user_service

    async def handle(self, conn: ClientConnection, msg: dict) -> None:
        """Route user message to the appropriate handler."""
        handlers = {
            "user_get_me": self._get_me,
            "user_update_profile": self._update_profile,
            "user_get_rankings": self._get_rankings,
            "user_get_history": self._get_history,
        }
        handler = handlers.get(msg.get("type", ""))
        if handler:
            await handler(conn, msg)
        else:
            seq = msg.get("seq", 0)
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 1002, "message": "Unknown user message type"},
            })

    async def _get_me(self, conn: ClientConnection, msg: dict) -> None:
        """Handle user_get_me message."""
        seq = msg.get("seq", 0)
        user = await self.user_service.get_user_info(conn.user_id)
        if not user:
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 2001, "message": "User not found"},
            })
            return

        await conn.send({
            "type": "user_me",
            "seq": seq,
            "data": {
                "user_id": user["id"],
                "username": user["username"],
                "nickname": user["nickname"],
                "avatar": user.get("avatar", ""),
                "rating": user["rating"],
                "games_count": user["games_count"],
                "wins_count": user.get("wins_count", 0),
                "losses_count": user.get("losses_count", 0),
                "draws_count": user.get("draws_count", 0),
                "is_admin": user.get("is_admin", False),
                "created_at": user.get("created_at", ""),
            },
        })

    async def _update_profile(self, conn: ClientConnection, msg: dict) -> None:
        """Handle user_update_profile message."""
        seq = msg.get("seq", 0)
        data = msg.get("data", {})

        result = await self.user_service.update_profile(conn.user_id, data)
        if not result:
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 2002, "message": "Profile update failed"},
            })
            return

        await conn.send({
            "type": "user_profile_updated",
            "seq": seq,
            "data": {
                "success": True,
                "nickname": result.get("nickname", ""),
                "avatar": result.get("avatar", ""),
            },
        })

    async def _get_rankings(self, conn: ClientConnection, msg: dict) -> None:
        """Handle user_get_rankings message."""
        seq = msg.get("seq", 0)
        data = msg.get("data", {})
        page = data.get("page", 1)
        page_size = data.get("page_size", 20)

        result = await self.user_service.get_rankings(page, page_size)
        result["seq"] = seq

        await conn.send({
            "type": "user_rankings",
            "seq": seq,
            "data": result,
        })

    async def _get_history(self, conn: ClientConnection, msg: dict) -> None:
        """Handle user_get_history message."""
        seq = msg.get("seq", 0)
        data = msg.get("data", {})
        page = data.get("page", 1)
        page_size = data.get("page_size", 20)
        game_type = data.get("game_type")

        result = await self.user_service.get_history(
            conn.user_id, page, page_size, game_type,
        )

        await conn.send({
            "type": "user_history",
            "seq": seq,
            "data": result,
        })
