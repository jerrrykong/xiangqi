"""Room manager for managing game rooms."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Callable, Any
import asyncio
import uuid
import time
import logging

from internal.chess.game import ChessGame
from internal.chess.piece import Color
from shared.constants import (
    RoomStatus, RoomType, GameResult, WinReason,
)
from internal.game.player_session import PlayerSession, ConnectionState
from internal.game.protocol import outbound as out_msg


logger = logging.getLogger(__name__)


class RoomState(Enum):
    """Room internal state."""
    WAITING = "waiting"
    READY = "ready"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass
class Room:
    """Represents a game room."""

    room_id: str
    room_type: str  # "pvp" or "pve"
    state: RoomState = RoomState.WAITING
    red_session: Optional[PlayerSession] = None
    black_session: Optional[PlayerSession] = None
    game: Optional[ChessGame] = None
    difficulty: int = 1  # For PvE
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    winner: Optional[str] = None
    result: Optional[str] = None
    reason: Optional[str] = None

    # Callbacks
    on_game_over: Optional[Callable[["Room"], None]] = None

    # Timers
    _turn_timer: Optional[asyncio.Task] = None
    _turn_start_time: float = 0.0
    TURN_TIMEOUT: int = 300  # 5 minutes per turn

    def is_full(self) -> bool:
        """Check if the room is full."""
        return self.red_session is not None and self.black_session is not None

    def is_empty(self) -> bool:
        """Check if the room is empty."""
        return self.red_session is None and self.black_session is None

    def has_player(self, session_id: str) -> bool:
        """Check if a session is in this room."""
        return (
            (self.red_session is not None and self.red_session.session_id == session_id)
            or (self.black_session is not None and self.black_session.session_id == session_id)
        )

    def get_player_session(self, side: str) -> Optional[PlayerSession]:
        """Get the session for a specific side."""
        if side == "red":
            return self.red_session
        elif side == "black":
            return self.black_session
        return None

    def get_opponent_session(self, session_id: str) -> Optional[PlayerSession]:
        """Get the opponent's session."""
        if self.red_session and self.red_session.session_id == session_id:
            return self.black_session
        if self.black_session and self.black_session.session_id == session_id:
            return self.red_session
        return None

    def get_side(self, session_id: str) -> Optional[str]:
        """Get the side for a session."""
        if self.red_session and self.red_session.session_id == session_id:
            return "red"
        if self.black_session and self.black_session.session_id == session_id:
            return "black"
        return None

    def assign_red(self, session: PlayerSession) -> bool:
        """Assign a session to red side."""
        if self.red_session is not None:
            return False
        self.red_session = session
        session.room_id = self.room_id
        session.side = "red"
        return True

    def assign_black(self, session: PlayerSession) -> bool:
        """Assign a session to black side."""
        if self.black_session is not None:
            return False
        self.black_session = session
        session.room_id = self.room_id
        session.side = "black"
        return True

    def start_game(self) -> None:
        """Start the game."""
        if self.state != RoomState.READY:
            return
        self.state = RoomState.PLAYING
        self.started_at = time.time()
        self.game = ChessGame()

    def get_current_side(self) -> str:
        """Get the current turn side."""
        if self.game is None:
            return "red"
        return "red" if self.game.current_color == Color.RED else "black"

    def make_move(self, session_id: str, from_pos: str, to_pos: str) -> tuple[bool, str]:
        """
        Make a move in the game.
        Returns: (success, error_message)
        """
        if self.state != RoomState.PLAYING:
            return False, "Game not in playing state"

        side = self.get_side(session_id)
        if side is None:
            return False, "Session not in room"

        current_side = self.get_current_side()
        if side != current_side:
            return False, f"Not your turn (current: {current_side})"

        # Parse positions
        try:
            from_col = ord(from_pos[0].lower()) - ord('a')
            from_row = int(from_pos[1])
            to_col = ord(to_pos[0].lower()) - ord('a')
            to_row = int(to_pos[1])
        except (ValueError, IndexError):
            return False, "Invalid position format"

        # Make move
        success, captured, is_check = self.game.apply_move(
            from_col, from_row, to_col, to_row
        )

        if not success:
            return False, self.game.last_error or "Invalid move"

        return True, ""

    def check_game_over(self) -> tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Check if the game is over.
        Returns: (is_over, winner, result, reason)
        """
        if self.game is None:
            return False, None, None, None

        result = self.game.check_game_over()
        if not result.is_over:
            return False, None, None, None

        winner_map = {
            Color.RED: "red",
            Color.BLACK: "black",
        }

        winner = winner_map.get(result.winner, None)
        result_str = result.result.value if hasattr(result.result, 'value') else str(result.result)
        reason = result.reason or WinReason.CHECKMATE

        return True, winner, result_str, reason

    def get_state_sync_data(self, session_id: str) -> dict:
        """Get full state for sync (reconnection)."""
        side = self.get_side(session_id)
        if side is None:
            return {}

        board_data = []
        if self.game and self.game.board:
            board_data = [row[:] for row in self.game.board.grid]

        red_time = self.red_session.remaining_time if self.red_session else 600
        black_time = self.black_session.remaining_time if self.black_session else 600

        return {
            "room_id": self.room_id,
            "board": board_data,
            "turn": self.get_current_side(),
            "move_no": self.game.move_count if self.game else 0,
            "red_time": red_time,
            "black_time": black_time,
            "your_side": side,
        }

    def cleanup(self) -> None:
        """Clean up room resources."""
        if self._turn_timer:
            self._turn_timer.cancel()
            self._turn_timer = None


class RoomManager:
    """Manages all game rooms."""

    def __init__(self):
        self._rooms: Dict[str, Room] = {}
        self._session_to_room: Dict[str, str] = {}  # session_id -> room_id
        self._lock = asyncio.Lock()
        self._ai_engine = None  # AI engine, injected later

    async def create_room(
        self,
        room_type: str = RoomType.PVP,
        difficulty: int = 1,
    ) -> Room:
        """Create a new room."""
        async with self._lock:
            room_id = str(uuid.uuid4())
            room = Room(
                room_id=room_id,
                room_type=room_type,
                difficulty=difficulty,
            )
            self._rooms[room_id] = room
            logger.info(f"Room created: {room_id}, type: {room_type}")
            return room

    async def get_room(self, room_id: str) -> Optional[Room]:
        """Get a room by ID."""
        return self._rooms.get(room_id)

    async def get_room_by_session(self, session_id: str) -> Optional[Room]:
        """Get a room by session ID."""
        room_id = self._session_to_room.get(session_id)
        if room_id:
            return self._rooms.get(room_id)
        return None

    async def join_room(
        self,
        room_id: str,
        session: PlayerSession,
    ) -> tuple[bool, str]:
        """
        Join a room.
        Returns: (success, message)
        """
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return False, "Room not found"

            if room.is_full():
                return False, "Room is full"

            if room.state not in (RoomState.WAITING, RoomState.READY):
                return False, "Game already started"

            # Assign to available side
            assigned = False
            if room.red_session is None:
                room.assign_red(session)
                assigned = True
            elif room.black_session is None:
                room.assign_black(session)
                assigned = True

            if not assigned:
                return False, "Failed to assign side"

            self._session_to_room[session.session_id] = room_id

            # If both players are in, start game
            if room.red_session and room.black_session:
                room.state = RoomState.READY
                room.start_game()
                logger.info(f"Game started in room {room_id}")

            return True, "Joined room successfully"

    async def leave_room(self, session_id: str) -> bool:
        """Remove a player from their room."""
        async with self._lock:
            room = await self.get_room_by_session(session_id)
            if room is None:
                return False

            side = room.get_side(session_id)
            if side == "red":
                room.red_session = None
            elif side == "black":
                room.black_session = None

            del self._session_to_room[session_id]

            # Clean up empty rooms
            if room.is_empty():
                room.cleanup()
                del self._rooms[room.room_id]
                logger.info(f"Room {room.room_id} cleaned up (empty)")

            return True

    async def handle_move(
        self,
        session_id: str,
        from_pos: str,
        to_pos: str,
    ) -> tuple[bool, dict]:
        """
        Handle a move.
        Returns: (success, response_data)
        """
        room = await self.get_room_by_session(session_id)
        if room is None:
            return False, out_msg.error_message(4001, "Not in a room")

        success, error = room.make_move(session_id, from_pos, to_pos)
        if not success:
            return False, out_msg.error_message(4001, error)

        # Check game over
        is_over, winner, result, reason = room.check_game_over()
        if is_over:
            room.state = RoomState.FINISHED
            room.ended_at = time.time()
            room.winner = winner
            room.result = result
            room.reason = reason
            # Fire callback
            if room.on_game_over:
                await room.on_game_over(room)

        # Build response
        captured = 0
        if room.game:
            # Get captured piece from last move
            try:
                to_col = ord(to_pos[0].lower()) - ord('a')
                to_row = int(to_pos[1])
                captured = room.game.board.get(to_row, to_col)
            except (ValueError, IndexError):
                pass

        response = out_msg.move_result_message(
            player=room.get_side(session_id),
            from_pos=from_pos,
            to_pos=to_pos,
            captured=captured,
            check=room.game.is_in_check() if room.game else False,
            red_time=room.red_session.remaining_time if room.red_session else 600,
            black_time=room.black_session.remaining_time if room.black_session else 600,
        )

        # Notify opponent
        opponent = room.get_opponent_session(session_id)
        if opponent and opponent.is_connected():
            opponent_response = out_msg.opponent_move_message(
                player=room.get_side(session_id),
                from_pos=from_pos,
                to_pos=to_pos,
                captured=captured,
                check=room.game.is_in_check() if room.game else False,
            )
            # TODO: send to opponent websocket

        # If game over, send game over message to both
        if is_over:
            game_over_resp = out_msg.game_over_message(
                winner=winner or "none",
                result=result or "",
                reason=reason or "",
            )
            # TODO: send to both players

        return True, response

    async def handle_resign(self, session_id: str) -> tuple[bool, dict]:
        """Handle a resignation."""
        room = await self.get_room_by_session(session_id)
        if room is None:
            return False, out_msg.error_message(4001, "Not in a room")

        if room.state != RoomState.PLAYING:
            return False, out_msg.error_message(4001, "Game not in progress")

        side = room.get_side(session_id)
        opponent_side = "black" if side == "red" else "red"

        room.state = RoomState.FINISHED
        room.ended_at = time.time()
        room.winner = opponent_side
        room.result = GameResult.RED_RESIGN if side == "red" else GameResult.BLACK_RESIGN
        room.reason = WinReason.RESIGN

        if room.on_game_over:
            await room.on_game_over(room)

        return True, out_msg.game_over_message(
            winner=opponent_side,
            result=room.result,
            reason=WinReason.RESIGN,
        )

    async def handle_draw_request(self, session_id: str) -> tuple[bool, dict]:
        """Handle a draw request."""
        room = await self.get_room_by_session(session_id)
        if room is None:
            return False, out_msg.error_message(4001, "Not in a room")

        side = room.get_side(session_id)
        response = out_msg.draw_request_message(from_side=side)
        return True, response

    async def handle_draw_answer(self, session_id: str, accept: bool) -> tuple[bool, dict]:
        """Handle a draw answer."""
        room = await self.get_room_by_session(session_id)
        if room is None:
            return False, out_msg.error_message(4001, "Not in a room")

        side = room.get_side(session_id)

        if accept:
            room.state = RoomState.FINISHED
            room.ended_at = time.time()
            room.winner = None
            room.result = GameResult.DRAW
            room.reason = WinReason.AGREEMENT

            if room.on_game_over:
                await room.on_game_over(room)

            return True, out_msg.game_over_message(
                winner="none",
                result=GameResult.DRAW,
                reason=WinReason.AGREEMENT,
            )
        else:
            opponent = room.get_opponent_session(session_id)
            if opponent and opponent.is_connected():
                response = out_msg.draw_answered_message(
                    from_side=side or "unknown",
                    accept=False,
                )
                # TODO: send to opponent
            return True, out_msg.pong_message()

    async def handle_reconnect(
        self,
        session: PlayerSession,
        token: str,
        room_id: str,
    ) -> tuple[bool, dict]:
        """Handle a reconnection."""
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return False, out_msg.error_message(4003, "Room not found")

            # Verify token
            if session.token != token:
                return False, out_msg.error_message(4003, "Invalid token")

            # Find the session in the room
            if room.has_player(session.session_id):
                session.restore()
                self._session_to_room[session.session_id] = room_id

                # Send state sync
                state_sync = out_msg.state_sync_message(
                    **room.get_state_sync_data(session.session_id)
                )
                return True, state_sync

            return False, out_msg.error_message(4003, "Session not in room")

    def list_active_rooms(self) -> List[Room]:
        """List all active rooms."""
        return [
            r for r in self._rooms.values()
            if r.state in (RoomState.WAITING, RoomState.READY, RoomState.PLAYING)
        ]

    def count_active_rooms(self) -> int:
        """Count active rooms."""
        return len(self.list_active_rooms())
