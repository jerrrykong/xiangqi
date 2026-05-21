"""Game Service v2.0 - Admin Handler

Handles admin-related WebSocket messages.
All admin operations require conn.is_admin == True.
"""

import logging

from admin.admin_service import AdminService
from gateway.connection_manager import ClientConnection
from room.room_manager import RoomManager

logger = logging.getLogger(__name__)


class AdminHandler:
    """Handles admin-related WebSocket messages."""

    def __init__(self, admin_service: AdminService, room_manager: RoomManager):
        self.admin_service = admin_service
        self.room_manager = room_manager

    async def handle(self, conn: ClientConnection, msg: dict) -> None:
        """Route admin message to the appropriate handler."""
        seq = msg.get("seq", 0)

        # Admin check
        if not conn.is_admin:
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 2003, "message": "Admin access required"},
            })
            return

        handlers = {
            "admin_users": self._users,
            "admin_ban": self._ban,
            "admin_stats": self._stats,
            "admin_models": self._models,
        }
        handler = handlers.get(msg.get("type", ""))
        if handler:
            await handler(conn, msg)
        else:
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 1002, "message": "Unknown admin message type"},
            })

    async def _users(self, conn: ClientConnection, msg: dict) -> None:
        """Handle admin_users message."""
        seq = msg.get("seq", 0)
        data = msg.get("data", {})

        result = await self.admin_service.list_users(
            page=data.get("page", 1),
            page_size=data.get("page_size", 20),
            search=data.get("search"),
        )

        await conn.send({
            "type": "admin_users_result",
            "seq": seq,
            "data": result,
        })

    async def _ban(self, conn: ClientConnection, msg: dict) -> None:
        """Handle admin_ban message."""
        seq = msg.get("seq", 0)
        data = msg.get("data", {})

        result = await self.admin_service.ban_user(
            user_id=data.get("user_id", 0),
            banned=data.get("banned", False),
            reason=data.get("reason", ""),
        )

        await conn.send({
            "type": "admin_ban_result",
            "seq": seq,
            "data": result,
        })

    async def _stats(self, conn: ClientConnection, msg: dict) -> None:
        """Handle admin_stats message."""
        seq = msg.get("seq", 0)

        active_rooms = len(self.room_manager.rooms)
        result = await self.admin_service.get_stats(active_rooms)

        await conn.send({
            "type": "admin_stats_result",
            "seq": seq,
            "data": result,
        })

    async def _models(self, conn: ClientConnection, msg: dict) -> None:
        """Handle admin_models message."""
        seq = msg.get("seq", 0)

        result = await self.admin_service.list_models()

        await conn.send({
            "type": "admin_models_result",
            "seq": seq,
            "data": result,
        })
