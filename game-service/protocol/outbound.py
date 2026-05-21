"""Game Service v2.0 - Protocol - Outbound Message Types

Defines all server→client message type constants and data structures.
Strictly follows 04-shared-protocols.md v2.0.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


# ========== Message Type Constants ==========

# Authentication responses
AUTH_RESULT = "auth_result"
AUTH_REGISTER_RESULT = "auth_register_result"
AUTH_TOKEN_RESULT = "auth_token_result"
AUTH_REFRESH_RESULT = "auth_refresh_result"
RECONNECT_RESULT = "reconnect_result"

# User responses
USER_ME = "user_me"
USER_PROFILE_UPDATED = "user_profile_updated"
USER_RANKINGS = "user_rankings"
USER_HISTORY = "user_history"
RATING_UPDATE = "rating_update"

# Room responses
ROOM_CREATED = "room_created"
ROOM_LIST_RESULT = "room_list_result"
ROOM_JOINED = "room_joined"
ROOM_LEFT = "room_left"
ROOM_REMOVED = "room_removed"
PLAYER_JOINED = "player_joined"
PLAYER_LEFT = "player_left"

# Game responses
GAME_START = "game_start"
MOVE_RESULT = "move_result"
OPPONENT_MOVE = "opponent_move"
AI_THINKING = "ai_thinking"
AI_MOVE = "ai_move"
GAME_OVER = "game_over"
DRAW_REQUEST = "draw_request"
DRAW_RESULT = "draw_result"

# Match responses
MATCH_QUEUED = "match_queued"
MATCH_LEFT = "match_left"
MATCH_FOUND = "match_found"

# Admin responses
ADMIN_USERS_RESULT = "admin_users_result"
ADMIN_BAN_RESULT = "admin_ban_result"
ADMIN_STATS_RESULT = "admin_stats_result"
ADMIN_MODELS_RESULT = "admin_models_result"

# State sync
STATE_SYNC = "state_sync"

# Common
PONG = "pong"
ERROR = "error"


# ========== Outbound Message Data Classes ==========

@dataclass
class AuthResultData:
    """auth_result message data."""
    success: bool = False
    token: str = ""
    refresh_token: str = ""
    session_token: str = ""
    user: Optional[dict] = None
    message: str = ""


@dataclass
class UserMeData:
    """user_me message data."""
    id: int = 0
    username: str = ""
    nickname: str = ""
    avatar: str = ""
    rating: int = 1500
    games_count: int = 0
    is_admin: bool = False


@dataclass
class UserRankingsData:
    """user_rankings message data."""
    rankings: list[dict] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


@dataclass
class UserHistoryData:
    """user_history message data."""
    games: list[dict] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


@dataclass
class RatingUpdateData:
    """rating_update message data."""
    rating: int = 0
    change: int = 0
    games_count: int = 0


@dataclass
class RoomCreatedData:
    """room_created message data."""
    room_id: str = ""
    room_type: str = ""
    difficulty: int = 0


@dataclass
class RoomListResultData:
    """room_list_result message data."""
    rooms: list[dict] = field(default_factory=list)


@dataclass
class RoomJoinedData:
    """room_joined message data."""
    room_id: str = ""
    room_type: str = ""
    players: list[dict] = field(default_factory=list)


@dataclass
class PlayerJoinedData:
    """player_joined message data (broadcast to room)."""
    user_id: int = 0
    username: str = ""
    nickname: str = ""
    side: str = ""  # red / black
    rating: int = 0


@dataclass
class GameStartData:
    """game_start message data."""
    room_id: str = ""
    red_player: Optional[dict] = None
    black_player: Optional[dict] = None
    initial_time: int = 600
    increment: int = 10
    fen: str = ""


@dataclass
class MoveResultData:
    """move_result message data (sent to the mover)."""
    success: bool = False
    fen: str = ""
    move: Optional[dict] = None
    message: str = ""


@dataclass
class OpponentMoveData:
    """opponent_move message data (sent to the opponent)."""
    from_pos: list[int] = field(default_factory=list)
    to_pos: list[int] = field(default_factory=list)
    fen: str = ""
    captured: Optional[dict] = None


@dataclass
class AIThinkingData:
    """ai_thinking message data."""
    pass


@dataclass
class AIMoveData:
    """ai_move message data."""
    from_pos: list[int] = field(default_factory=list)
    to_pos: list[int] = field(default_factory=list)
    fen: str = ""
    captured: Optional[dict] = None
    think_time_ms: int = 0


@dataclass
class GameOverData:
    """game_over message data."""
    room_id: str = ""
    winner: str = ""  # red / black / draw
    reason: str = ""  # checkmate / resign / timeout / draw / disconnect
    red_rating_change: int = 0
    black_rating_change: int = 0


@dataclass
class DrawRequestData:
    """draw_request message data (forwarded to opponent)."""
    from_user_id: int = 0
    from_username: str = ""


@dataclass
class DrawResultData:
    """draw_result message data."""
    accepted: bool = False


@dataclass
class MatchQueuedData:
    """match_queued message data."""
    position: int = 0
    estimated_wait: int = 30


@dataclass
class MatchFoundData:
    """match_found message data."""
    room_id: str = ""
    opponent: Optional[dict] = None
    your_side: str = ""  # red / black


@dataclass
class StateSyncData:
    """state_sync message data (for reconnect)."""
    room_id: str = ""
    room_type: str = ""
    phase: str = ""
    fen: str = ""
    your_side: str = ""
    red_player: Optional[dict] = None
    black_player: Optional[dict] = None
    red_remaining_time: int = 0
    black_remaining_time: int = 0
    moves: list[dict] = field(default_factory=list)


@dataclass
class ErrorData:
    """error message data."""
    code: int = 0
    message: str = ""
