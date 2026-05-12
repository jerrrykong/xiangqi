"""Shared constants for Xiangqi game."""
from enum import IntEnum
from typing import Final, Optional, Tuple

# ============ 棋子编码 ============
# 棋子编码: encoded = color * 10 + piece_type
# 红方 color = 0, 黑方 color = 1

# Piece encoding constants
PIECE_EMPTY: Final[int] = -1

# Red pieces (color = 0)
PIECE_RED_KING: Final[int] = 0      # 将
PIECE_RED_ADVISOR: Final[int] = 1   # 士
PIECE_RED_BISHOP: Final[int] = 2     # 相
PIECE_RED_KNIGHT: Final[int] = 3     # 马
PIECE_RED_ROOK: Final[int] = 4       # 车
PIECE_RED_CANNON: Final[int] = 5     # 炮
PIECE_RED_PAWN: Final[int] = 6       # 兵

# Black pieces (color = 1)
PIECE_BLACK_KING: Final[int] = 10    # 帅
PIECE_BLACK_ADVISOR: Final[int] = 11 # 仕
PIECE_BLACK_BISHOP: Final[int] = 12   # 象
PIECE_BLACK_KNIGHT: Final[int] = 13   # 马
PIECE_BLACK_ROOK: Final[int] = 14     # 车
PIECE_BLACK_CANNON: Final[int] = 15   # 炮
PIECE_BLACK_PAWN: Final[int] = 16     # 卒


class Color(IntEnum):
    """棋子颜色枚举"""
    RED = 0
    BLACK = 1
    NONE = -1


class PieceType(IntEnum):
    """棋子类型枚举"""
    KING = 0      # 将/帅
    ADVISOR = 1  # 士/仕
    BISHOP = 2    # 相/象
    KNIGHT = 3    # 马
    ROOK = 4      # 车
    CANNON = 5    # 炮
    PAWN = 6      # 兵


# ============ 棋盘常量 ============
# 棋盘: 10行 × 9列
# 坐标: 列 0-8 (对应 a-i), 行 0-9 (0为红方底线)

BOARD_ROWS: Final[int] = 10
BOARD_COLS: Final[int] = 9
BOARD_SIZE: Final[int] = BOARD_ROWS * BOARD_COLS  # 90

# 九宫格范围
RED_PALACE_TOP: Final[int] = 7      # 红方九宫顶行
RED_PALACE_BOTTOM: Final[int] = 9   # 红方九宫底行
RED_PALACE_LEFT: Final[int] = 3    # 红方九宫左列
RED_PALACE_RIGHT: Final[int] = 5    # 红方九宫右列

BLACK_PALACE_TOP: Final[int] = 0    # 黑方九宫顶行
BLACK_PALACE_BOTTOM: Final[int] = 2 # 黑方九宫底行
BLACK_PALACE_LEFT: Final[int] = 3   # 黑方九宫左列
BLACK_PALACE_RIGHT: Final[int] = 5  # 黑方九宫右列

RIVER_ROW: Final[int] = 4  # 楚河汉界所在行 (红方视角)

# ============ 难度等级 ============
class Difficulty(IntEnum):
    """AI 难度等级"""
    EASY = 1     # 简单: 100 次 MCTS 模拟
    MEDIUM = 2   # 中等: 400 次 MCTS 模拟
    HARD = 3     # 困难: 800 次 MCTS 模拟
    EXPERT = 4   # 大师: 1600 次 MCTS 模拟
    MASTER = 5   # 宗师: 3200+ 次 MCTS 模拟


DIFFICULTY_SIMULATIONS: Final[dict[int, int]] = {
    Difficulty.EASY: 100,
    Difficulty.MEDIUM: 400,
    Difficulty.HARD: 800,
    Difficulty.EXPERT: 1600,
    Difficulty.MASTER: 3200,
}

# ============ 房间状态 ============
class RoomStatus:
    """房间状态"""
    WAITING = "waiting"     # 等待玩家
    READY = "ready"        # 玩家已就绪
    PLAYING = "playing"    # 对局中
    FINISHED = "finished"  # 对局结束


# ============ 房间类型 ============
class RoomType:
    """房间类型"""
    PVP = "pvp"  # 人人对战
    PVE = "pve"  # 人机对战


# ============ 游戏结果 ============
class GameResult:
    """游戏结果"""
    RED_WINS = "RED_WINS"
    BLACK_WINS = "BLACK_WINS"
    DRAW = "DRAW"
    RED_RESIGN = "RED_RESIGN"
    BLACK_RESIGN = "BLACK_RESIGN"
    RED_TIMEOUT = "RED_TIMEOUT"
    BLACK_TIMEOUT = "BLACK_TIMEOUT"


# ============ 胜负原因 ============
class WinReason:
    """胜负原因"""
    CHECKMATE = "CHECKMATE"      # 将死
    STALEMATE = "STALEMATE"     # 困毙
    RESIGN = "RESIGN"           # 认输
    TIMEOUT = "TIMEOUT"          # 超时
    AGREEMENT = "AGREEMENT"      # 双方同意
    FIFTY_MOVE = "FIFTY_MOVE"    # 50回合和棋


# ============ WebSocket 消息类型 ============
class WSMessageType:
    """WebSocket 消息类型"""
    # Client -> Server
    MOVE = "move"
    RESIGN = "resign"
    DRAW_REQ = "draw_req"
    DRAW_ANS = "draw_ans"
    PING = "ping"
    RECONNECT = "reconnect"

    # Server -> Client
    STATE_SYNC = "state_sync"
    OPPONENT_MOVE = "opponent_move"
    GAME_START = "game_start"
    GAME_OVER = "game_over"
    CHECK = "check"
    DRAW_NOTIFY = "draw_notify"
    ERROR = "error"
    PONG = "pong"


# ============ 错误码 ============
class ErrorCode:
    """错误码定义"""
    # 1xxx: 系统错误
    SYSTEM = 1000
    INTERNAL = 1001
    DATABASE = 1002
    REDIS = 1003
    INVALID_PARAM = 1004

    # 2xxx: 认证错误
    AUTH = 2000
    UNAUTHORIZED = 2001
    TOKEN_EXPIRED = 2002
    TOKEN_INVALID = 2003
    WRONG_PASSWORD = 2004
    USER_NOT_FOUND = 2005
    USER_EXISTS = 2006

    # 3xxx: 房间错误
    ROOM = 3000
    ROOM_NOT_FOUND = 3001
    ROOM_FULL = 3002
    ROOM_NOT_STARTED = 3003
    ROOM_ALREADY_STARTED = 3004
    NOT_ROOM_OWNER = 3005
    NOT_YOUR_TURN = 3006
    ALREADY_READY = 3007
    NOT_READY = 3008

    # 4xxx: 游戏错误
    GAME = 4000
    INVALID_MOVE = 4001
    MOVE_NOT_YOUR_TURN = 4002
    GAME_NOT_STARTED = 4003
    GAME_ALREADY_OVER = 4004
    CHECK = 4005


# ============ 辅助函数 ============

def get_color_from_piece(piece: int) -> Color:
    """从棋子编码获取颜色"""
    if piece < 0:
        return Color.NONE
    return Color(piece // 10)


def get_piece_type_from_piece(piece: int) -> PieceType:
    """从棋子编码获取棋子类型"""
    if piece < 0:
        return PieceType.KING  # 默认值
    return PieceType(piece % 10)


def is_red_piece(piece: int) -> bool:
    """判断是否为红方棋子"""
    return 0 <= piece < 10


def is_black_piece(piece: int) -> bool:
    """判断是否为黑方棋子"""
    return 10 <= piece < 20


def is_piece(piece: int) -> bool:
    """判断是否为有效棋子"""
    return piece >= 0


def encode_piece(color: Color, piece_type: PieceType) -> int:
    """编码棋子"""
    return color * 10 + piece_type


def decode_piece(piece: int) -> tuple[Color, PieceType]:
    """解码棋子"""
    return Color(piece // 10), PieceType(piece % 10)


def get_piece_name(piece: int) -> str:
    """获取棋子名称"""
    if piece < 0:
        return "空"
    
    color = get_color_from_piece(piece)
    ptype = get_piece_type_from_piece(piece)
    
    color_name = "红" if color == Color.RED else "黑"
    
    names = {
        PieceType.KING: "将" if color == Color.RED else "帅",
        PieceType.ADVISOR: "士",
        PieceType.BISHOP: "相" if color == Color.RED else "象",
        PieceType.KNIGHT: "马",
        PieceType.ROOK: "车",
        PieceType.CANNON: "炮",
        PieceType.PAWN: "兵" if color == Color.RED else "卒",
    }
    
    return color_name + names.get(ptype, "?")


def coord_to_notation(col: int, row: int) -> str:
    """坐标转记谱法 (如 a0, i9)"""
    if not (0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS):
        return "??"
    col_letter = chr(ord('a') + col)
    return f"{col_letter}{row}"


def notation_to_coord(notation: str) -> Optional[Tuple[int, int]]:
    """记谱法转坐标 (如 a0 -> (0, 0))"""
    if len(notation) != 2:
        return None
    col = ord(notation[0].lower()) - ord('a')
    try:
        row = int(notation[1])
    except ValueError:
        return None
    if 0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS:
        return (col, row)
    return None
