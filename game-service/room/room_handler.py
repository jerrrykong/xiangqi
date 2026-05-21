"""Game Service v2.0 - Room Handler

Handles all room and game-related WebSocket messages.
"""

import logging
from typing import Optional

from chess.constants import Color, GameResult
from chess.move import Move
from chess.move_validator import MoveValidator
from chess.piece import board_to_fen
from gateway.connection_manager import ClientConnection
from gateway.connection_state import ConnectionState
from room.room import Room, RoomPhase, RoomType
from room.room_manager import RoomManager
from room.player_session import PlayerSession

logger = logging.getLogger(__name__)


class RoomHandler:
    """Handles all room and game-related WebSocket messages."""

    def __init__(self, room_manager: RoomManager):
        self.room_manager = room_manager

    async def handle(self, conn: ClientConnection, msg: dict) -> None:
        """Route room/game message to the appropriate handler."""
        handlers = {
            "room_create": self._create_room,
            "room_list": self._list_rooms,
            "room_join": self._join_room,
            "room_leave": self._leave_room,
            "game_move": self._game_move,
            "game_resign": self._game_resign,
            "game_draw_req": self._game_draw_req,
            "game_draw_ans": self._game_draw_ans,
        }
        handler = handlers.get(msg.get("type", ""))
        if handler:
            await handler(conn, msg)
        else:
            seq = msg.get("seq", 0)
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 1002, "message": "Unknown room/game message type"},
            })

    async def _create_room(self, conn: ClientConnection, msg: dict) -> None:
        """Handle room_create message."""
        seq = msg.get("seq", 0)
        data = msg.get("data", {})

        # Check if user already in room
        if self.room_manager.is_user_in_room(conn.user_id):
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 3004, "message": "Already in a room"},
            })
            return

        room_type = data.get("room_type", "pvp")
        difficulty = data.get("difficulty", 3)
        initial_time = data.get("initial_time", 600)
        increment = data.get("increment", 10)

        player = self._make_player_session(conn, "")

        if room_type == "pve":
            # PvE: player chooses side, directly starts
            player_side = data.get("player_side", "red")
            player.side = player_side
            room = await self.room_manager.create_pve_room(
                player, player_side, difficulty, initial_time, increment,
            )
            conn.set_state(ConnectionState.IN_ROOM)
            conn.room_id = room.room_id

            await conn.send({
                "type": "room_created",
                "seq": seq,
                "data": {
                    "room_id": room.room_id,
                    "room_type": "pve",
                    "your_side": player_side,
                    "difficulty": difficulty,
                    "status": "playing",
                },
            })
        else:
            # PvP: creator is red, waiting for opponent
            player.side = "red"
            room = await self.room_manager.create_manual_room(
                player, initial_time, increment,
            )
            conn.set_state(ConnectionState.IN_ROOM)
            conn.room_id = room.room_id

            await conn.send({
                "type": "room_created",
                "seq": seq,
                "data": {
                    "room_id": room.room_id,
                    "room_type": "pvp",
                    "your_side": "red",
                    "status": "waiting",
                },
            })

    async def _list_rooms(self, conn: ClientConnection, msg: dict) -> None:
        """Handle room_list message - list waiting rooms."""
        seq = msg.get("seq", 0)
        rooms = self.room_manager.get_waiting_rooms()

        room_list = []
        for r in rooms:
            room_list.append({
                "room_id": r.room_id,
                "room_type": "pvp",
                "red_player": {
                    "user_id": r.red_player.user_id,
                    "username": r.red_player.username,
                    "nickname": r.red_player.nickname,
                    "rating": r.red_player.rating,
                } if r.red_player else None,
                "initial_time": r.initial_time,
                "increment": r.increment,
            })

        await conn.send({
            "type": "room_list_result",
            "seq": seq,
            "data": {"rooms": room_list},
        })

    async def _join_room(self, conn: ClientConnection, msg: dict) -> None:
        """Handle room_join message."""
        seq = msg.get("seq", 0)
        data = msg.get("data", {})
        room_id = data.get("room_id", "")

        if self.room_manager.is_user_in_room(conn.user_id):
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 3004, "message": "Already in a room"},
            })
            return

        player = self._make_player_session(conn, "black")
        room = await self.room_manager.join_room(room_id, player)

        if not room:
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 3001, "message": "Cannot join room"},
            })
            return

        conn.set_state(ConnectionState.IN_ROOM)
        conn.room_id = room_id

        # game_start will be broadcast by RoomManager._run_room

    async def _leave_room(self, conn: ClientConnection, msg: dict) -> None:
        """Handle room_leave message."""
        seq = msg.get("seq", 0)
        room = self.room_manager.get_user_room(conn.user_id)
        if not room:
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 3001, "message": "Not in a room"},
            })
            return

        if room.phase == RoomPhase.PLAYING:
            # In a game - resign automatically
            await self.room_manager.resign(room, conn.user_id)
        elif room.phase == RoomPhase.WAITING:
            # In waiting room - just leave
            # If red (creator) leaves, room is destroyed
            side = room.get_player_side(conn.user_id)
            if side == "red":
                # Notify opponent if any
                opponent = room.get_opponent(conn.user_id)
                if opponent and opponent.is_connected:
                    await opponent.send({
                        "type": "room_removed",
                        "data": {"reason": "creator_left"},
                    })
                # Clean up
                self.room_manager.user_rooms.pop(conn.user_id, None)
                self.room_manager.rooms.pop(room.room_id, None)
                try:
                    await self.room_manager.room_repo.delete(room.room_id)
                except Exception:
                    pass

        conn.set_state(ConnectionState.AUTHENTICATED)
        conn.room_id = None

        await conn.send({
            "type": "room_left",
            "seq": seq,
            "data": {"room_id": room.room_id},
        })

    async def _game_move(self, conn: ClientConnection, msg: dict) -> None:
        """Handle game_move message."""
        seq = msg.get("seq", 0)
        room = self.room_manager.get_user_room(conn.user_id)
        if not room or room.phase != RoomPhase.PLAYING:
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 4003, "message": "Not in an active game"},
            })
            return

        side = room.get_player_side(conn.user_id)
        current_side = "red" if room.game_state.current_player == Color.RED else "black"

        if side != current_side:
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 4002, "message": "Not your turn"},
            })
            return

        # Parse move
        data = msg.get("data", {})
        try:
            from_pos = data.get("from_pos", [])
            to_pos = data.get("to_pos", [])
            if len(from_pos) < 2 or len(to_pos) < 2:
                raise ValueError("Invalid move format")
            move = Move(
                from_col=from_pos[1], from_row=from_pos[0],
                to_col=to_pos[1], to_row=to_pos[0],
            )
        except Exception as e:
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 4001, "message": f"Invalid move: {e}"},
            })
            return

        # Validate and apply move via room manager
        # (validation is done inside ChessGame.make_move)
        await self.room_manager.apply_player_move(room, move)

    async def _game_resign(self, conn: ClientConnection, msg: dict) -> None:
        """Handle game_resign message."""
        room = self.room_manager.get_user_room(conn.user_id)
        if not room or room.phase != RoomPhase.PLAYING:
            return

        await self.room_manager.resign(room, conn.user_id)

    async def _game_draw_req(self, conn: ClientConnection, msg: dict) -> None:
        """Handle game_draw_req message."""
        room = self.room_manager.get_user_room(conn.user_id)
        if not room or room.phase != RoomPhase.PLAYING:
            return

        await self.room_manager.draw_request(room, conn.user_id)

    async def _game_draw_ans(self, conn: ClientConnection, msg: dict) -> None:
        """Handle game_draw_ans message."""
        data = msg.get("data", {})
        accept = data.get("accept", False)

        room = self.room_manager.get_user_room(conn.user_id)
        if not room or room.phase != RoomPhase.PLAYING:
            return

        await self.room_manager.draw_answer(room, conn.user_id, accept)

    # ---- Helpers ----

    def _make_player_session(self, conn: ClientConnection, side: str) -> PlayerSession:
        """Create a PlayerSession from a connection."""
        return PlayerSession(
            user_id=conn.user_id,
            username=conn.username or "",
            side=side,
            rating=1500,  # Will be updated from DB
            _conn=conn,
        )
