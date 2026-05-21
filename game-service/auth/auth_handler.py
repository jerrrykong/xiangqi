"""Game Service v2.0 - Auth Handler

Handles all authentication-related WebSocket messages.
"""

import logging
import uuid
from typing import Optional

from auth.auth_service import AuthService
from auth.jwt_manager import JWTManager
from gateway.connection_manager import ClientConnection, ConnectionManager
from gateway.connection_state import ConnectionState
from user.user_service import UserService

logger = logging.getLogger(__name__)


class AuthHandler:
    """Handles all authentication-related WebSocket messages."""

    def __init__(self, auth_service: AuthService, user_service: UserService,
                 jwt_manager: JWTManager, connection_manager: ConnectionManager):
        self.auth_service = auth_service
        self.user_service = user_service
        self.jwt_manager = jwt_manager
        self.connection_manager = connection_manager

    async def handle(self, conn: ClientConnection, msg: dict) -> None:
        """Route auth message to the appropriate handler."""
        handlers = {
            "auth_login": self._handle_login,
            "auth_register": self._handle_register,
            "auth_token": self._handle_token_auth,
            "auth_refresh": self._handle_refresh,
            "reconnect": self._handle_reconnect,
        }
        handler = handlers.get(msg.get("type", ""))
        if handler:
            await handler(conn, msg)
        else:
            seq = msg.get("seq", 0)
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 1002, "message": "Unknown auth message type"},
            })

    async def _handle_login(self, conn: ClientConnection, msg: dict) -> None:
        """Handle auth_login message."""
        data = msg.get("data", {})
        seq = msg.get("seq", 0)
        username = data.get("username", "")
        password = data.get("password", "")

        user = await self.auth_service.login(username, password)
        if not user:
            await conn.send({
                "type": "auth_result",
                "seq": seq,
                "data": {"success": False, "error": "invalid_credentials"},
            })
            return

        # Generate JWT + session_token
        token, expires_at = self.jwt_manager.create_token(
            user["id"], user["username"], user.get("is_admin", False),
        )
        refresh_token, _ = self.jwt_manager.create_refresh_token(
            user["id"], user["username"], user.get("is_admin", False),
        )
        session_token = str(uuid.uuid4())

        # Register connection
        conn.user_id = user["id"]
        conn.username = user["username"]
        conn.session_token = session_token
        conn.is_admin = user.get("is_admin", False)
        conn.set_state(ConnectionState.AUTHENTICATED)
        self.connection_manager.bind_user(conn, user["id"])

        # Get user rating info
        user_info = await self.user_service.get_user_info(user["id"])

        await conn.send({
            "type": "auth_result",
            "seq": seq,
            "data": {
                "success": True,
                "user_id": user["id"],
                "username": user["username"],
                "nickname": user.get("nickname", ""),
                "rating": user_info.get("rating", 1500),
                "games_count": user_info.get("games_count", 0),
                "is_admin": user.get("is_admin", False),
                "token": token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "session_token": session_token,
            },
        })

    async def _handle_register(self, conn: ClientConnection, msg: dict) -> None:
        """Handle auth_register message."""
        data = msg.get("data", {})
        seq = msg.get("seq", 0)

        username = data.get("username", "")
        password = data.get("password", "")
        nickname = data.get("nickname", username)

        user = await self.auth_service.register(username, password, nickname)
        if not user:
            await conn.send({
                "type": "auth_register_result",
                "seq": seq,
                "data": {"success": False, "error": "username_exists"},
            })
            return

        # Auto-login after registration
        token, expires_at = self.jwt_manager.create_token(
            user["id"], user["username"], False,
        )
        refresh_token, _ = self.jwt_manager.create_refresh_token(
            user["id"], user["username"], False,
        )
        session_token = str(uuid.uuid4())

        conn.user_id = user["id"]
        conn.username = user["username"]
        conn.session_token = session_token
        conn.is_admin = False
        conn.set_state(ConnectionState.AUTHENTICATED)
        self.connection_manager.bind_user(conn, user["id"])

        await conn.send({
            "type": "auth_register_result",
            "seq": seq,
            "data": {
                "success": True,
                "user_id": user["id"],
                "username": user["username"],
                "nickname": user.get("nickname", ""),
                "rating": 1500,
                "games_count": 0,
                "is_admin": False,
                "token": token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "session_token": session_token,
            },
        })

    async def _handle_token_auth(self, conn: ClientConnection, msg: dict) -> None:
        """Handle auth_token - authenticate with existing JWT token."""
        data = msg.get("data", {})
        seq = msg.get("seq", 0)
        token = data.get("token", "")

        claims = self.jwt_manager.parse_token(token)
        if not claims:
            await conn.send({
                "type": "auth_token_result",
                "seq": seq,
                "data": {"success": False, "error": "token_invalid"},
            })
            return

        user = await self.user_service.get_user_info(claims.user_id)
        if not user or user.get("is_banned", False):
            await conn.send({
                "type": "auth_token_result",
                "seq": seq,
                "data": {"success": False, "error": "user_banned"},
            })
            return

        session_token = str(uuid.uuid4())
        conn.user_id = claims.user_id
        conn.username = claims.username
        conn.session_token = session_token
        conn.is_admin = claims.is_admin
        conn.set_state(ConnectionState.AUTHENTICATED)
        self.connection_manager.bind_user(conn, claims.user_id)

        await conn.send({
            "type": "auth_token_result",
            "seq": seq,
            "data": {
                "success": True,
                "user_id": claims.user_id,
                "username": claims.username,
                "nickname": user.get("nickname", ""),
                "rating": user.get("rating", 1500),
                "games_count": user.get("games_count", 0),
                "is_admin": claims.is_admin,
                "session_token": session_token,
            },
        })

    async def _handle_refresh(self, conn: ClientConnection, msg: dict) -> None:
        """Handle auth_refresh - refresh access token."""
        data = msg.get("data", {})
        seq = msg.get("seq", 0)
        refresh_token_str = data.get("refresh_token", "")

        result = self.jwt_manager.refresh_token(refresh_token_str)
        if not result:
            await conn.send({
                "type": "auth_refresh_result",
                "seq": seq,
                "data": {"success": False, "error": "refresh_token_invalid"},
            })
            return

        new_token, expires_at = result
        await conn.send({
            "type": "auth_refresh_result",
            "seq": seq,
            "data": {
                "success": True,
                "token": new_token,
                "expires_at": expires_at,
            },
        })

    async def _handle_reconnect(self, conn: ClientConnection, msg: dict) -> None:
        """Handle reconnect - reconnect with session_token and room_id."""
        data = msg.get("data", {})
        seq = msg.get("seq", 0)
        session_token = data.get("session_token", "")
        room_id = data.get("room_id", "")

        # Find original connection by session_token
        original_conn = self._find_connection_by_session(session_token)
        if not original_conn:
            await conn.send({
                "type": "reconnect_result",
                "seq": seq,
                "data": {"success": False, "error": "session_invalid"},
            })
            return

        # Transfer state from original connection
        conn.user_id = original_conn.user_id
        conn.username = original_conn.username
        conn.session_token = str(uuid.uuid4())  # New session token
        conn.is_admin = original_conn.is_admin

        if room_id and original_conn.room_id == room_id:
            conn.room_id = room_id
            conn.set_state(ConnectionState.IN_ROOM)
        else:
            conn.set_state(ConnectionState.AUTHENTICATED)

        # Bind the new connection
        self.connection_manager.bind_user(conn, conn.user_id)

        # Send reconnect result
        await conn.send({
            "type": "reconnect_result",
            "seq": seq,
            "data": {
                "success": True,
                "user_id": conn.user_id,
                "username": conn.username,
                "session_token": conn.session_token,
                "state": conn.state.name.lower(),
                "room_id": conn.room_id,
            },
        })

        # If in room, room handler will push state_sync separately
        # (This will be connected when T7 room module is implemented)

    def _find_connection_by_session(self, session_token: str) -> Optional[ClientConnection]:
        """Find a connection by its session token."""
        for conn in self.connection_manager._connections.values():
            if conn.session_token == session_token:
                return conn
        return None
