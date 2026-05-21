"""Game Service v2.0 - Protocol - Inbound Message Types

Defines all client→server message type constants and data structures.
Strictly follows 04-shared-protocols.md v2.0.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


# ========== Message Type Constants ==========

# Authentication
AUTH_LOGIN = "auth_login"
AUTH_REGISTER = "auth_register"
AUTH_TOKEN = "auth_token"
AUTH_REFRESH = "auth_refresh"
RECONNECT = "reconnect"

# User
USER_GET_ME = "user_get_me"
USER_UPDATE_PROFILE = "user_update_profile"
USER_GET_RANKINGS = "user_get_rankings"
USER_GET_HISTORY = "user_get_history"

# Room
ROOM_CREATE = "room_create"
ROOM_LIST = "room_list"
ROOM_JOIN = "room_join"
ROOM_LEAVE = "room_leave"

# Game
GAME_MOVE = "game_move"
GAME_RESIGN = "game_resign"
GAME_DRAW_REQ = "game_draw_req"
GAME_DRAW_ANS = "game_draw_ans"

# Match
MATCH_JOIN = "match_join"
MATCH_LEAVE = "match_leave"

# Admin
ADMIN_USERS = "admin_users"
ADMIN_BAN = "admin_ban"
ADMIN_STATS = "admin_stats"
ADMIN_MODELS = "admin_models"

# Common
PING = "ping"


# ========== Inbound Message Data Classes ==========

@dataclass
class AuthLoginData:
    """auth_login message data."""
    username: str = ""
    password: str = ""


@dataclass
class AuthRegisterData:
    """auth_register message data."""
    username: str = ""
    password: str = ""
    nickname: str = ""


@dataclass
class AuthTokenData:
    """auth_token message data."""
    token: str = ""


@dataclass
class AuthRefreshData:
    """auth_refresh message data."""
    refresh_token: str = ""


@dataclass
class ReconnectData:
    """reconnect message data."""
    session_token: str = ""
    room_id: str = ""


@dataclass
class UserUpdateProfileData:
    """user_update_profile message data."""
    nickname: Optional[str] = None
    avatar: Optional[str] = None


@dataclass
class UserGetRankingsData:
    """user_get_rankings message data."""
    page: int = 1
    page_size: int = 20


@dataclass
class UserGetHistoryData:
    """user_get_history message data."""
    page: int = 1
    page_size: int = 20
    game_type: Optional[str] = None


@dataclass
class RoomCreateData:
    """room_create message data."""
    room_type: str = "pvp"  # pvp / pve
    difficulty: int = 3      # AI难度 1-5 (pve时)
    initial_time: int = 600  # 初始时间(秒)
    increment: int = 10      # 每步增加时间(秒)


@dataclass
class RoomListData:
    """room_list message data."""
    room_type: Optional[str] = None


@dataclass
class RoomJoinData:
    """room_join message data."""
    room_id: str = ""


@dataclass
class RoomLeaveData:
    """room_leave message data."""
    room_id: str = ""


@dataclass
class GameMoveData:
    """game_move message data."""
    from_pos: list[int] = field(default_factory=list)  # [row, col]
    to_pos: list[int] = field(default_factory=list)    # [row, col]


@dataclass
class GameResignData:
    """game_resign message data."""
    pass


@dataclass
class GameDrawReqData:
    """game_draw_req message data."""
    pass


@dataclass
class GameDrawAnsData:
    """game_draw_ans message data."""
    accept: bool = False


@dataclass
class MatchJoinData:
    """match_join message data."""
    game_type: str = "pvp"


@dataclass
class MatchLeaveData:
    """match_leave message data."""
    pass


@dataclass
class AdminUsersData:
    """admin_users message data."""
    page: int = 1
    page_size: int = 20
    search: Optional[str] = None


@dataclass
class AdminBanData:
    """admin_ban message data."""
    user_id: int = 0
    banned: bool = False
    reason: str = ""


@dataclass
class AdminStatsData:
    """admin_stats message data."""
    pass


@dataclass
class AdminModelsData:
    """admin_models message data."""
    pass
