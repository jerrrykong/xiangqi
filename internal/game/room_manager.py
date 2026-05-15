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
from shared.protocol import Move
from internal.game.player_session import PlayerSession, ConnectionState
from internal.game.protocol import outbound as out_msg


logger = logging.getLogger(__name__)


def _log(level: str, msg: str, **kwargs):
    """Structured logging helper."""
    parts = [msg]
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    log_msg = " | ".join(parts)
    getattr(logger, level)(log_msg)


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
            _log("warning", "room_assign_side_failed",
                 room_id=self.room_id,
                 session_id=session.session_id,
                 side="red",
                 reason="side_occupied")
            return False
        self.red_session = session
        session.room_id = self.room_id
        session.side = "red"
        _log("info", "room_assign_side",
             room_id=self.room_id,
             session_id=session.session_id,
             side="red",
             user_id=session.user_id)
        return True

    def assign_black(self, session: PlayerSession) -> bool:
        """Assign a session to black side."""
        if self.black_session is not None:
            _log("warning", "room_assign_side_failed",
                 room_id=self.room_id,
                 session_id=session.session_id,
                 side="black",
                 reason="side_occupied")
            return False
        self.black_session = session
        session.room_id = self.room_id
        session.side = "black"
        _log("info", "room_assign_side",
             room_id=self.room_id,
             session_id=session.session_id,
             side="black",
             user_id=session.user_id)
        return True

    def start_game(self) -> None:
        """Start the game."""
        if self.state != RoomState.READY:
            _log("warning", "room_start_game_failed",
                 room_id=self.room_id,
                 reason="not_ready",
                 current_state=self.state.value)
            return
        self.state = RoomState.PLAYING
        self.started_at = time.time()
        self.game = ChessGame()
        _log("info", "room_game_started",
             room_id=self.room_id,
             room_type=self.room_type,
             difficulty=self.difficulty)

    def get_current_side(self) -> str:
        """Get the current turn side."""
        if self.game is None:
            return "red"
        return "red" if self.game.turn == Color.RED else "black"

    def make_move(self, session_id: str, from_pos: str, to_pos: str) -> tuple[bool, str]:
        """
        Make a move in the game.
        Returns: (success, error_message)
        """
        if self.state != RoomState.PLAYING:
            msg = "Game not in playing state"
            _log("warning", "room_make_move_failed",
                 room_id=self.room_id,
                 session_id=session_id,
                 reason=msg)
            return False, msg

        side = self.get_side(session_id)
        if side is None:
            msg = "Session not in room"
            _log("warning", "room_make_move_failed",
                 room_id=self.room_id,
                 session_id=session_id,
                 reason=msg)
            return False, msg

        current_side = self.get_current_side()
        if side != current_side:
            msg = f"Not your turn (current: {current_side})"
            _log("warning", "room_make_move_failed",
                 room_id=self.room_id,
                 session_id=session_id,
                 side=side,
                 reason=msg,
                 current_turn=current_side)
            return False, msg

        # Parse positions
        try:
            from_col = ord(from_pos[0].lower()) - ord('a')
            from_row = int(from_pos[1]) - 1  # Convert 1-indexed to 0-indexed
            to_col = ord(to_pos[0].lower()) - ord('a')
            to_row = int(to_pos[1]) - 1  # Convert 1-indexed to 0-indexed
        except (ValueError, IndexError):
            msg = "Invalid position format"
            _log("warning", "room_make_move_failed",
                 room_id=self.room_id,
                 session_id=session_id,
                 reason=msg,
                 from_pos=from_pos,
                 to_pos=to_pos)
            return False, msg

        # Create Move object and execute
        move = Move(from_col=from_col, from_row=from_row, to_col=to_col, to_row=to_row)
        success, error = self.game.make_move(move)

        if not success:
            _log("warning", "room_make_move_failed",
                 room_id=self.room_id,
                 session_id=session_id,
                 side=side,
                 from_pos=from_pos,
                 to_pos=to_pos,
                 reason=error)
            return False, error

        _log("info", "room_move_success",
             room_id=self.room_id,
             session_id=session_id,
             side=side,
             from_pos=from_pos,
             to_pos=to_pos,
             move_no=self.game.move_count)

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

        _log("info", "room_game_over_detected",
             room_id=self.room_id,
             winner=winner,
             result=result_str,
             reason=reason)

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
        _log("info", "room_cleanup",
             room_id=self.room_id,
             state=self.state.value)


class RoomManager:
    """Manages all game rooms."""

    def __init__(self):
        self._rooms: Dict[str, Room] = {}
        self._session_to_room: Dict[str, str] = {}  # session_id -> room_id
        self._lock = asyncio.Lock()
        self._ai_engine = None  # AI engine, injected later
        _log("info", "room_manager_init")

    async def create_room(
        self,
        room_id: Optional[str] = None,
        room_type: str = RoomType.PVP,
        difficulty: int = 1,
    ) -> Room:
        """Create a new room."""
        async with self._lock:
            room_id = room_id or str(uuid.uuid4())
            room = Room(
                room_id=room_id,
                room_type=room_type,
                difficulty=difficulty,
            )
            self._rooms[room_id] = room
            _log("info", "room_created",
                 room_id=room_id,
                 room_type=room_type,
                 difficulty=difficulty,
                 total_rooms=len(self._rooms))
            return room

    async def get_room(self, room_id: str) -> Optional[Room]:
        """Get a room by ID."""
        room = self._rooms.get(room_id)
        if room:
            _log("debug", "room_get",
                 room_id=room_id,
                 found=True,
                 state=room.state.value)
        else:
            _log("debug", "room_get",
                 room_id=room_id,
                 found=False)
        return room

    async def get_room_by_session(self, session_id: str) -> Optional[Room]:
        """Get a room by session ID."""
        room_id = self._session_to_room.get(session_id)
        if room_id:
            room = self._rooms.get(room_id)
            _log("debug", "room_get_by_session",
                 session_id=session_id,
                 room_id=room_id,
                 found=room is not None)
            return room
        _log("debug", "room_get_by_session",
             session_id=session_id,
             room_id=None,
             found=False)
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
        _log("info", "room_join_attempt",
             room_id=room_id,
             session_id=session.session_id,
             user_id=session.user_id)

        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                _log("warning", "room_join_failed",
                     room_id=room_id,
                     session_id=session.session_id,
                     reason="room_not_found")
                return False, "Room not found"

            if room.is_full():
                _log("warning", "room_join_failed",
                     room_id=room_id,
                     session_id=session.session_id,
                     reason="room_full")
                return False, "Room is full"

            if room.state not in (RoomState.WAITING, RoomState.READY):
                _log("warning", "room_join_failed",
                     room_id=room_id,
                     session_id=session.session_id,
                     reason="game_already_started",
                     room_state=room.state.value)
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
                _log("warning", "room_join_failed",
                     room_id=room_id,
                     session_id=session.session_id,
                     reason="failed_to_assign_side")
                return False, "Failed to assign side"

            self._session_to_room[session.session_id] = room_id

            # If both players are in, start game
            if room.red_session and room.black_session:
                room.state = RoomState.PLAYING
                room.started_at = time.time()
                room.game = ChessGame()
                room.game.start()  # Start the game (sets phase to PLAYING)
                _log("info", "room_game_starting",
                     room_id=room_id,
                     red_session=room.red_session.session_id,
                     black_session=room.black_session.session_id)

            _log("info", "room_join_success",
                 room_id=room_id,
                 session_id=session.session_id,
                 side=session.side,
                 room_state=room.state.value)

            return True, "Joined room successfully"

    async def assign_side(
        self,
        room_id: str,
        session: PlayerSession,
        side: str,
    ) -> tuple[bool, str]:
        """
        Assign a session to a specific side in a room.
        Returns: (success, message)
        """
        _log("info", "room_assign_side_attempt",
             room_id=room_id,
             session_id=session.session_id,
             user_id=session.user_id,
             target_side=side)

        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                _log("warning", "room_assign_side_failed",
                     room_id=room_id,
                     session_id=session.session_id,
                     reason="room_not_found")
                return False, "Room not found"

            # Assign to specified side
            if side == "red":
                if room.red_session is not None:
                    _log("warning", "room_assign_side_failed",
                         room_id=room_id,
                         session_id=session.session_id,
                         reason="red_already_taken")
                    return False, "Red side already taken"
                room.assign_red(session)
            elif side == "black":
                if room.black_session is not None:
                    _log("warning", "room_assign_side_failed",
                         room_id=room_id,
                         session_id=session.session_id,
                         reason="black_already_taken")
                    return False, "Black side already taken"
                room.assign_black(session)
            else:
                _log("warning", "room_assign_side_failed",
                     room_id=room_id,
                     session_id=session.session_id,
                     reason="invalid_side")
                return False, "Invalid side"

            self._session_to_room[session.session_id] = room_id

            _log("info", "room_assign_side_success",
                 room_id=room_id,
                 session_id=session.session_id,
                 side=side)

            return True, "Assigned successfully"

    async def leave_room(self, session_id: str) -> bool:
        """Remove a player from their room."""
        _log("info", "room_leave_attempt",
             session_id=session_id)

        async with self._lock:
            room = await self.get_room_by_session(session_id)
            if room is None:
                _log("warning", "room_leave_failed",
                     session_id=session_id,
                     reason="not_in_any_room")
                return False

            side = room.get_side(session_id)
            if side == "red":
                room.red_session = None
            elif side == "black":
                room.black_session = None

            if session_id in self._session_to_room:
                del self._session_to_room[session_id]

            # Clean up empty rooms
            if room.is_empty():
                room.cleanup()
                del self._rooms[room.room_id]
                _log("info", "room_deleted_empty",
                     room_id=room.room_id,
                     total_rooms=len(self._rooms))

            _log("info", "room_leave_success",
                 session_id=session_id,
                 room_id=room.room_id,
                 side=side)

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
        _log("debug", "room_handle_move",
             session_id=session_id,
             from_pos=from_pos,
             to_pos=to_pos)

        room = await self.get_room_by_session(session_id)
        if room is None:
            _log("warning", "room_handle_move_failed",
                 session_id=session_id,
                 reason="not_in_room")
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
            _log("info", "room_game_ended",
                 room_id=room.room_id,
                 winner=winner,
                 result=result,
                 reason=reason,
                 duration_seconds=int(room.ended_at - room.started_at) if room.started_at else 0)
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
        _log("info", "room_handle_resign",
             session_id=session_id)

        room = await self.get_room_by_session(session_id)
        if room is None:
            _log("warning", "room_handle_resign_failed",
                 session_id=session_id,
                 reason="not_in_room")
            return False, out_msg.error_message(4001, "Not in a room")

        if room.state != RoomState.PLAYING:
            _log("warning", "room_handle_resign_failed",
                 session_id=session_id,
                 reason="game_not_in_progress")
            return False, out_msg.error_message(4001, "Game not in progress")

        side = room.get_side(session_id)
        opponent_side = "black" if side == "red" else "red"

        room.state = RoomState.FINISHED
        room.ended_at = time.time()
        room.winner = opponent_side
        room.result = GameResult.RED_RESIGN if side == "red" else GameResult.BLACK_RESIGN
        room.reason = WinReason.RESIGN

        _log("info", "room_resign_success",
             room_id=room.room_id,
             session_id=session_id,
             side=side,
             winner=opponent_side)

        if room.on_game_over:
            await room.on_game_over(room)

        return True, out_msg.game_over_message(
            winner=opponent_side,
            result=room.result,
            reason=WinReason.RESIGN,
        )

    async def handle_draw_request(self, session_id: str) -> tuple[bool, dict]:
        """Handle a draw request."""
        _log("debug", "room_handle_draw_request",
             session_id=session_id)

        room = await self.get_room_by_session(session_id)
        if room is None:
            return False, out_msg.error_message(4001, "Not in a room")

        side = room.get_side(session_id)
        response = out_msg.draw_request_message(from_side=side)
        return True, response

    async def handle_draw_answer(self, session_id: str, accept: bool) -> tuple[bool, dict]:
        """Handle a draw answer."""
        _log("info", "room_handle_draw_answer",
             session_id=session_id,
             accept=accept)

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

            _log("info", "room_draw_accepted",
                 room_id=room.room_id,
                 session_id=session_id)

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
        _log("info", "room_handle_reconnect",
             session_id=session.session_id,
             room_id=room_id)

        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                _log("warning", "room_reconnect_failed",
                     session_id=session.session_id,
                     room_id=room_id,
                     reason="room_not_found")
                return False, out_msg.error_message(4003, "Room not found")

            # Verify token
            if session.token != token:
                _log("warning", "room_reconnect_failed",
                     session_id=session.session_id,
                     room_id=room_id,
                     reason="invalid_token")
                return False, out_msg.error_message(4003, "Invalid token")

            # Find the session in the room
            if room.has_player(session.session_id):
                session.restore()
                self._session_to_room[session.session_id] = room_id

                # Send state sync
                state_sync = out_msg.state_sync_message(
                    **room.get_state_sync_data(session.session_id)
                )
                _log("info", "room_reconnect_success",
                     session_id=session.session_id,
                     room_id=room_id,
                     side=session.side)
                return True, state_sync

            _log("warning", "room_reconnect_failed",
                 session_id=session.session_id,
                 room_id=room_id,
                 reason="session_not_in_room")
            return False, out_msg.error_message(4003, "Session not in room")

    def list_active_rooms(self) -> List[Room]:
        """List all active rooms."""
        rooms = [
            r for r in self._rooms.values()
            if r.state in (RoomState.WAITING, RoomState.READY, RoomState.PLAYING)
        ]
        _log("debug", "room_list_active",
             count=len(rooms))
        return rooms

    def count_active_rooms(self) -> int:
        """Count active rooms."""
        return len(self.list_active_rooms())
