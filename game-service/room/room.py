"""Game Service v2.0 - Room

Room object containing complete game state and lifecycle.
Room is the sole carrier of a game from creation to finish.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from chess.constants import Color, GameResult
from chess.game import ChessGame, GamePhase
from room.player_session import PlayerSession
from room.timers import MoveTimer

logger = logging.getLogger(__name__)


class RoomSource(IntEnum):
    MANUAL = 1
    MATCH = 2


class RoomPhase(IntEnum):
    WAITING = 1   # 等待对手加入
    READY = 2     # 双方都在，等待点击开始
    PLAYING = 3   # 对局中
    FINISHED = 4  # 对局结束


class RoomType(IntEnum):
    PVP = 1
    PVE = 2


@dataclass
class Room:
    """Room object - the sole carrier of a complete game.

    Lifecycle:
    - Manual PvP: create → WAITING → join → READY → both ready → PLAYING → FINISHED
    - Match PvP: match_found → directly PLAYING → FINISHED
    - PvE: create → directly PLAYING → FINISHED
    - Rematch: FINISHED → both rematch → swap colors → PLAYING → FINISHED
    """
    room_id: str
    room_type: RoomType
    source: RoomSource = RoomSource.MANUAL
    phase: RoomPhase = RoomPhase.WAITING
    difficulty: Optional[int] = None

    # Players
    red_player: Optional[PlayerSession] = None
    black_player: Optional[PlayerSession] = None

    # Game state (initialized when both players are ready)
    game_state: ChessGame|None = None

    # Timer
    timer: MoveTimer|None = None
    initial_time: int = 600
    increment: int = 10
    started_at: float = 0.0

    # AI (PvE only)
    ai_side: Optional[Color] = None
    ai_name: str = ""        # AI display name (e.g. "电脑（困难）")
    ai_avatar: str = ""      # AI avatar identifier (e.g. "sys:ai-hard")

    # Async event for move signaling
    move_event: asyncio.Event = field(default_factory=asyncio.Event)

    # Draw state
    draw_requester_id: Optional[int] = None

    # Ready state (READY phase: both must click start)
    ready_players: set = field(default_factory=set)

    # Rematch state (FINISHED phase: both must click rematch)
    rematch_players: set = field(default_factory=set)

    # Game count in this room (for tracking multi-game sessions)
    game_count: int = 0
    # Allow full-AI rooms to run automatically when no humans present.
    # This is a reserved flag that is set via API when creating AI-only rooms.
    allow_full_ai_run: bool = False

    @property
    def is_full(self) -> bool:
        return self.red_player is not None and self.black_player is not None

    @property
    def is_playing(self) -> bool:
        return self.phase == RoomPhase.PLAYING

    def get_player(self, side: str) -> Optional[PlayerSession]:
        """Get player by side ('red' or 'black')."""
        if side == "red":
            return self.red_player
        return self.black_player

    def get_opponent(self, user_id: int) -> Optional[PlayerSession]:
        """Get the opponent of the given user."""
        if self.red_player and self.red_player.user_id == user_id:
            return self.black_player
        if self.black_player and self.black_player.user_id == user_id:
            return self.red_player
        return None

    def get_player_side(self, user_id: int) -> Optional[str]:
        """Get which side a user is on ('red' or 'black')."""
        if self.red_player and self.red_player.user_id == user_id:
            return "red"
        if self.black_player and self.black_player.user_id == user_id:
            return "black"
        return None

    def init_game(self) -> None:
        """Initialize game state and timer."""
        self.game_state = ChessGame()
        self.game_state.start()  # Set phase to PLAYING
        self.phase = RoomPhase.PLAYING
        import time
        self.started_at = time.time()
        self.game_count += 1
        self.ready_players.clear()
        self.rematch_players.clear()

    def swap_colors(self) -> None:
        """Swap red and black players for rematch."""
        self.red_player, self.black_player = self.black_player, self.red_player
        if self.red_player:
            self.red_player.side = "red"
        if self.black_player:
            self.black_player.side = "black"
        # If this is a PvE room, the AI side should also be flipped
        # when players swap colors so AI continues to act on the correct side.
        if self.ai_side is not None:
            self.ai_side = Color.RED if self.ai_side == Color.BLACK else Color.BLACK

    def add_player(self, player: PlayerSession, side: str) -> None:
        """Add a player to the specified side."""
        if side == "red":
            self.red_player = player
        else:
            self.black_player = player
        player.side = side
