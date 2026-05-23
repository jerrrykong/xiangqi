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

    def __init__(self, room_manager: RoomManager, connection_manager=None):
        self.room_manager = room_manager
        self.connection_manager = connection_manager

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
            logger.warning(f"Room create rejected: user={conn.user_id} already in room")
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

            logger.info(f"PvE room created: room_id={room.room_id}, user={conn.username}(id={conn.user_id}), side={player_side}, difficulty={difficulty}")

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

            logger.info(f"PvP room created: room_id={room.room_id}, creator={conn.username}(id={conn.user_id}), waiting for opponent")

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

            # 广播房间变更通知 (排除创建者)
            await self._broadcast_room_update(exclude_user=conn.user_id)

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
            logger.warning(f"Room join rejected: user={conn.user_id} already in room")
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 3004, "message": "Already in a room"},
            })
            return

        player = self._make_player_session(conn, "black")
        room = await self.room_manager.join_room(room_id, player)

        if not room:
            logger.info(f"Room join failed: room_id={room_id} not found or not joinable, user={conn.user_id}")
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 3001, "message": "Cannot join room"},
            })
            return

        conn.set_state(ConnectionState.IN_ROOM)
        conn.room_id = room_id

        logger.info(f"Room joined: room_id={room_id}, user={conn.username}(id={conn.user_id}), game starting")

        # Send room_joined response to the joining player
        await conn.send({
            "type": "room_joined",
            "seq": seq,
            "data": {
                "room_id": room_id,
                "room_type": "pvp",
                "your_side": "black",
                "players": [
                    self.room_manager._player_info(room.red_player),
                    self.room_manager._player_info(room.black_player),
                ],
            },
        })

        # 广播房间变更通知 (加入后房间不再等待，通知其他用户刷新)
        await self._broadcast_room_update(exclude_user=conn.user_id)

        # game_start will be broadcast by RoomManager._run_room

    async def _leave_room(self, conn: ClientConnection, msg: dict) -> None:
        """Handle room_leave message."""
        seq = msg.get("seq", 0)
        room = self.room_manager.get_user_room(conn.user_id)

        if not room:
            # Room already cleaned up (e.g. game over) - just confirm leave
            logger.info(f"Room leave: user={conn.user_id} not in any room (already cleaned up), confirming leave")
            conn.set_state(ConnectionState.AUTHENTICATED)
            conn.room_id = None
            await conn.send({
                "type": "room_left",
                "seq": seq,
                "data": {"room_id": None},
            })
            return

        if room.phase == RoomPhase.PLAYING:
            # In a game - resign automatically
            logger.info(f"Player {conn.username}(id={conn.user_id}) leaving during game, auto-resign, room={room.room_id}")
            await self.room_manager.resign(room, conn.user_id)
        elif room.phase == RoomPhase.WAITING:
            # In waiting room - just leave
            # If red (creator) leaves, room is destroyed
            side = room.get_player_side(conn.user_id)
            logger.info(f"Player {conn.username}(id={conn.user_id}) leaving waiting room, side={side}, room={room.room_id}")
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

                # 广播房间变更通知
                await self._broadcast_room_update()

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
            logger.warning(f"Move rejected: user={conn.user_id} not in active game")
            await conn.send({
                "type": "error",
                "seq": seq,
                "data": {"code": 4003, "message": "Not in an active game"},
            })
            return

        side = room.get_player_side(conn.user_id)
        current_side = "red" if room.game_state.current_player == Color.RED else "black"

        if side != current_side:
            logger.warning(f"Move rejected: not user's turn, user={conn.user_id}, side={side}, current={current_side}, room={room.room_id}")
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
            logger.warning(f"Invalid move format from user={conn.user_id}: {e}, data={data}")
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

        logger.info(f"Player {conn.username}(id={conn.user_id}) resigns, room={room.room_id}")
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

    async def _broadcast_room_update(self, exclude_user: int = None) -> None:
        """Broadcast room update notification to all authenticated connections."""
        if not self.connection_manager:
            logger.debug("Skip room_update broadcast: no connection_manager")
            return

        logger.debug(f"Broadcasting room_update, exclude_user={exclude_user}")
        await self.connection_manager.broadcast({
            "type": "room_update",
            "data": {"action": "refresh"},
        }, exclude={exclude_user} if exclude_user else None)
