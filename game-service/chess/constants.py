"""Game Service v2.0 - Chess Constants

Chess piece encoding, board constants, game result definitions.
Migrated from shared/constants.py for self-contained chess module.
"""
from enum import IntEnum
from typing import Final, Optional, Tuple

# ============ 棋子编码 ============
# 棋子编码: encoded = color * 10 + piece_type
# 红方 color = 0, 黑方 color = 1

PIECE_EMPTY: Final[int] = -1

# Red pieces (color = 0)
PIECE_RED_KING: Final[int] = 0
PIECE_RED_ADVISOR: Final[int] = 1
PIECE_RED_BISHOP: Final[int] = 2
PIECE_RED_KNIGHT: Final[int] = 3
PIECE_RED_ROOK: Final[int] = 4
PIECE_RED_CANNON: Final[int] = 5
PIECE_RED_PAWN: Final[int] = 6

# Black pieces (color = 1)
PIECE_BLACK_KING: Final[int] = 10
PIECE_BLACK_ADVISOR: Final[int] = 11
PIECE_BLACK_BISHOP: Final[int] = 12
PIECE_BLACK_KNIGHT: Final[int] = 13
PIECE_BLACK_ROOK: Final[int] = 14
PIECE_BLACK_CANNON: Final[int] = 15
PIECE_BLACK_PAWN: Final[int] = 16


class Color(IntEnum):
    """棋子颜色枚举"""
    RED = 0
    BLACK = 1
    NONE = -1


class PieceType(IntEnum):
    """棋子类型枚举"""
    KING = 0
    ADVISOR = 1
    BISHOP = 2
    KNIGHT = 3
    ROOK = 4
    CANNON = 5
    PAWN = 6


# ============ 棋盘常量 ============
BOARD_ROWS: Final[int] = 10
BOARD_COLS: Final[int] = 9
BOARD_SIZE: Final[int] = BOARD_ROWS * BOARD_COLS

# 九宫格范围
RED_PALACE_TOP: Final[int] = 7
RED_PALACE_BOTTOM: Final[int] = 9
RED_PALACE_LEFT: Final[int] = 3
RED_PALACE_RIGHT: Final[int] = 5

BLACK_PALACE_TOP: Final[int] = 0
BLACK_PALACE_BOTTOM: Final[int] = 2
BLACK_PALACE_LEFT: Final[int] = 3
BLACK_PALACE_RIGHT: Final[int] = 5

RIVER_ROW: Final[int] = 4

# ============ 难度等级 ============
class Difficulty(IntEnum):
    """AI 难度等级"""
    EASY = 1
    MEDIUM = 2
    HARD = 3
    EXPERT = 4
    MASTER = 5


DIFFICULTY_SIMULATIONS: Final[dict[int, int]] = {
    Difficulty.EASY: 100,
    Difficulty.MEDIUM: 400,
    Difficulty.HARD: 800,
    Difficulty.EXPERT: 1600,
    Difficulty.MASTER: 3200,
}

# ============ 游戏结果 ============
class GameResult:
    RED_WINS = "RED_WINS"
    BLACK_WINS = "BLACK_WINS"
    DRAW = "DRAW"
    RED_RESIGN = "RED_RESIGN"
    BLACK_RESIGN = "BLACK_RESIGN"
    RED_TIMEOUT = "RED_TIMEOUT"
    BLACK_TIMEOUT = "BLACK_TIMEOUT"


class WinReason:
    CHECKMATE = "CHECKMATE"
    STALEMATE = "STALEMATE"
    RESIGN = "RESIGN"
    TIMEOUT = "TIMEOUT"
    AGREEMENT = "AGREEMENT"
    FIFTY_MOVE = "FIFTY_MOVE"
    THREEFOLD_REPETITION = "THREEFOLD_REPETITION"  # 三次重复局面 → 和棋
    PERPETUAL_CHECK = "PERPETUAL_CHECK"            # 长将 → 将军方判负
    PERPETUAL_CHASE = "PERPETUAL_CHASE"            # 长捉 → 捉子方判负


# ============ 辅助函数 ============

def get_color_from_piece(piece: int) -> Color:
    if piece < 0:
        return Color.NONE
    return Color(piece // 10)


def get_piece_type_from_piece(piece: int) -> PieceType:
    if piece < 0:
        return PieceType.KING
    return PieceType(piece % 10)


def is_red_piece(piece: int) -> bool:
    return 0 <= piece < 10


def is_black_piece(piece: int) -> bool:
    return 10 <= piece < 20


def is_piece(piece: int) -> bool:
    return piece >= 0


def encode_piece(color: Color, piece_type: PieceType) -> int:
    return color * 10 + piece_type


def decode_piece(piece: int) -> tuple[Color, PieceType]:
    return Color(piece // 10), PieceType(piece % 10)


def get_piece_name(piece: int) -> str:
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
    if not (0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS):
        return "??"
    col_letter = chr(ord('a') + col)
    return f"{col_letter}{row}"


def notation_to_coord(notation: str) -> Optional[Tuple[int, int]]:
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
