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

        user = await self.auth_service.login(username, data.get("password", ""))
        if not user:
            logger.info(f"Login failed: invalid credentials for username='{username}' conn={conn.conn_id}")
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
        
        logger.info(f"User {user['username']} login success, create session_token [{session_token}]")

        # Register connection
        conn.user_id = user["id"]
        conn.username = user["username"]
        conn.nickname = user.get("nickname", "")
        conn.avatar = user.get("avatar", "")
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
                "avatar": user.get("avatar", ""),
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
        avatar = data.get("avatar", "")

        user = await self.auth_service.register(username, password, nickname, avatar)
        if not user:
            logger.info(f"Register failed: username='{username}' already exists, conn={conn.conn_id}")
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
        conn.nickname = user.get("nickname", "")
        conn.avatar = user.get("avatar", "")
        conn.session_token = session_token
        conn.is_admin = False
        conn.set_state(ConnectionState.AUTHENTICATED)
        self.connection_manager.bind_user(conn, user["id"])

        logger.info(f"User {user['username']} registered and auto-login, conn={conn.conn_id}")

        await conn.send({
            "type": "auth_register_result",
            "seq": seq,
            "data": {
                "success": True,
                "user_id": user["id"],
                "username": user["username"],
                "nickname": user.get("nickname", ""),
                "avatar": user.get("avatar", ""),
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
        token_str = data.get("token", "")

        claims = self.jwt_manager.parse_token(token_str)
        if not claims:
            logger.info(f"Token auth failed: invalid token, conn={conn.conn_id}")
            await conn.send({
                "type": "auth_token_result",
                "seq": seq,
                "data": {"success": False, "error": "token_invalid"},
            })
            return

        user = await self.user_service.get_user_info(claims.user_id)
        if not user or user.get("is_banned", False):
            logger.info(f"Token auth failed: user_id={claims.user_id} not found or banned, conn={conn.conn_id}")
            await conn.send({
                "type": "auth_token_result",
                "seq": seq,
                "data": {"success": False, "error": "user_banned"},
            })
            return

        session_token = str(uuid.uuid4())
        conn.user_id = claims.user_id
        conn.username = claims.username
        conn.nickname = user.get("nickname", "")
        conn.avatar = user.get("avatar", "")
        conn.session_token = session_token
        conn.is_admin = claims.is_admin
        conn.set_state(ConnectionState.AUTHENTICATED)
        self.connection_manager.bind_user(conn, claims.user_id)
        
        logger.info(f"User {conn.username}(id={conn.user_id}) token auth success, session_token={session_token[:8]}..., conn={conn.conn_id}")

        # Check if user has an active room (reconnection scenario)
        user_state = "authenticated"
        user_room_id = None
        user_room_phase = None
        room_manager_ref = getattr(self.connection_manager, '_room_manager_ref', None)
        if room_manager_ref:
            room = room_manager_ref.get_user_room(claims.user_id)
            if room:
                from room.room import RoomPhase
                if room.phase in (RoomPhase.WAITING, RoomPhase.READY, RoomPhase.PLAYING, RoomPhase.FINISHED):
                    user_state = "in_room"
                    user_room_id = room.room_id
                    user_room_phase = room.phase.name.lower()
                    conn.room_id = room.room_id
                    conn.set_state(ConnectionState.IN_ROOM)
                    logger.info(f"User {conn.username}(id={conn.user_id}) token auth: found active room={room.room_id}, phase={user_room_phase}, state=in_room")

        await conn.send({
            "type": "auth_token_result",
            "seq": seq,
            "data": {
                "success": True,
                "user_id": claims.user_id,
                "username": claims.username,
                "nickname": user.get("nickname", ""),
                "avatar": user.get("avatar", ""),
                "rating": user.get("rating", 1500),
                "games_count": user.get("games_count", 0),
                "is_admin": claims.is_admin,
                "session_token": session_token,
                "state": user_state,
                "room_id": user_room_id,
                "room_phase": user_room_phase,
            },
        })

        # If user is in a room, restore room state (reconnect)
        if user_state == "in_room" and user_room_id:
            await self._restore_room_state(conn)

    async def _handle_refresh(self, conn: ClientConnection, msg: dict) -> None:
        """Handle auth_refresh - refresh access token."""
        data = msg.get("data", {})
        seq = msg.get("seq", 0)
        refresh_token_str = data.get("refresh_token", "")

        result = self.jwt_manager.refresh_token(refresh_token_str)
        if not result:
            logger.info(f"Token refresh failed: invalid refresh_token, user_id={conn.user_id}, conn={conn.conn_id}")
            await conn.send({
                "type": "auth_refresh_result",
                "seq": seq,
                "data": {"success": False, "error": "refresh_token_invalid"},
            })
            return

        new_token, expires_at = result
        logger.info(f"Token refresh success, user_id={conn.user_id}, conn={conn.conn_id}")
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

        # Find original connection by session_token
        original_conn = self._find_connection_by_session(session_token)
        if not original_conn:
            logger.info(f"Reconnect failed: session_token not found, conn={conn.conn_id}")
            await conn.send({
                "type": "reconnect_result",
                "seq": seq,
                "data": {"success": False, "error": "session_invalid"},
            })
            return

        logger.info(f"Reconnect: user={original_conn.username}(id={original_conn.user_id}), room_id={original_conn.room_id}, conn={conn.conn_id}")

        # Transfer state from original connection
        conn.user_id = original_conn.user_id
        conn.username = original_conn.username
        conn.nickname = original_conn.nickname
        conn.avatar = original_conn.avatar
        conn.session_token = str(uuid.uuid4())  # New session token
        conn.is_admin = original_conn.is_admin

        # Determine reconnection state
        in_room = bool(original_conn.room_id) and original_conn.state == ConnectionState.IN_ROOM

        if in_room:
            # Verify room still exists
            room_manager_ref = getattr(self.connection_manager, '_room_manager_ref', None)
            if room_manager_ref:
                room = room_manager_ref.get_user_room(conn.user_id)
                if not room:
                    # Room no longer exists
                    logger.info(f"Reconnect: user={conn.username}(id={conn.user_id}) room_id={original_conn.room_id} no longer exists")
                    in_room = False

        if in_room:
            conn.room_id = original_conn.room_id
            conn.set_state(ConnectionState.IN_ROOM)
        else:
            conn.set_state(ConnectionState.AUTHENTICATED)

        # Bind the new connection (this may kick the old connection)
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

        # If in room, reconnect the player session and send state_sync
        if in_room and conn.room_id:
            await self._restore_room_state(conn)

    async def _restore_room_state(self, conn: ClientConnection) -> None:
        """Restore player's room state after reconnection."""
        # Import here to avoid circular imports
        from room.room import RoomPhase
        from chess.piece import board_to_fen

        room = self.connection_manager._room_manager_ref.get_user_room(conn.user_id) if hasattr(self.connection_manager, '_room_manager_ref') and self.connection_manager._room_manager_ref else None

        if not room:
            logger.warning(f"Reconnect: user={conn.user_id} has room_id={conn.room_id} but room not found, resetting to authenticated")
            conn.set_state(ConnectionState.AUTHENTICATED)
            conn.room_id = None
            return

        # Reconnect the player session in the room
        side = room.get_player_side(conn.user_id)
        if not side:
            logger.warning(f"Reconnect: user={conn.user_id} not a player in room={room.room_id}")
            conn.set_state(ConnectionState.AUTHENTICATED)
            conn.room_id = None
            return

        player = room.get_player(side)
        if player:
            player.reconnect(conn)
            logger.info(f"Reconnect: player {conn.username}(id={conn.user_id}) reconnected to room={room.room_id}, side={side}")

            # Notify the opponent about reconnection
            opponent = room.get_opponent(conn.user_id)
            if opponent and opponent.is_connected:
                await opponent.send({
                    "type": "opponent_status_change",
                    "data": {"user_id": conn.user_id, "online": True},
                })

        # Build state_sync data
        fen = board_to_fen(room.game_state.board) if room.game_state else ""
        current_side = "red" if room.game_state and room.game_state.current_player == 0 else "black" if room.game_state else "red"

        state_data = {
            "room_id": room.room_id,
            "room_type": "pvp" if room.room_type == 1 else "pve",
            "phase": room.phase.name.lower(),
            "fen": fen,
            "your_side": side,
            "current_side": current_side,
            "red_player": self._player_info_from_room(room.red_player),
            "black_player": self._player_info_from_room(room.black_player),
            "red_remaining_time": room.timer.red_remaining if room.timer else room.initial_time,
            "black_remaining_time": room.timer.black_remaining if room.timer else room.initial_time,
            "moves": [],
            "ready_players": list(room.ready_players),
            "rematch_players": list(room.rematch_players),
        }

        # Include AI player info for PvE rooms
        if room.room_type == 2 and room.ai_side is not None:  # 2 = RoomType.PVE
            ai_info = {
                "user_id": 0,
                "username": room.ai_name,
                "nickname": room.ai_name,
                "avatar": room.ai_avatar,
                "rating": 0,
                "is_bot": True,
                "online": True,
            }
            if room.ai_side == 0:  # Color.RED = 0
                state_data["red_player"] = ai_info
            else:
                state_data["black_player"] = ai_info

        # Build moves list from game history
        if room.game_state and hasattr(room.game_state, 'history'):
            try:
                for record in room.game_state.history:
                    state_data["moves"].append({
                        "from_pos": [record.move.from_row, record.move.from_col],
                        "to_pos": [record.move.to_row, record.move.to_col],
                    })
            except Exception as e:
                logger.warning(f"Failed to build moves list for state_sync: {e}")

        await conn.send({
            "type": "state_sync",
            "data": state_data,
        })

        logger.info(f"Reconnect: state_sync sent for user={conn.user_id}, room={room.room_id}, phase={room.phase.name}, side={side}")

    @staticmethod
    def _player_info_from_room(player) -> Optional[dict]:
        """Get player info dict for state_sync."""
        if not player:
            return None
        return {
            "user_id": player.user_id,
            "username": player.username,
            "nickname": player.nickname,
            "avatar": player.avatar,
            "rating": player.rating,
            "is_bot": player.is_bot,
            "online": player.is_bot or player.is_connected,
        }

    def _find_connection_by_session(self, session_token: str) -> Optional[ClientConnection]:
        """Find a connection by its session token."""
        for conn in self.connection_manager._connections.values():
            if conn.session_token == session_token:
                return conn
        return None
