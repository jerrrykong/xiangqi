"""棋子与棋盘数据结构."""
from dataclasses import dataclass
from typing import Iterator, Optional, List, Tuple
import copy
import zlib

from chess.constants import (
    Color,
    PieceType,
    PIECE_EMPTY,
    PIECE_RED_KING, PIECE_RED_ADVISOR, PIECE_RED_BISHOP, PIECE_RED_KNIGHT,
    PIECE_RED_ROOK, PIECE_RED_CANNON, PIECE_RED_PAWN,
    PIECE_BLACK_KING, PIECE_BLACK_ADVISOR, PIECE_BLACK_BISHOP, PIECE_BLACK_KNIGHT,
    PIECE_BLACK_ROOK, PIECE_BLACK_CANNON, PIECE_BLACK_PAWN,
    BOARD_ROWS, BOARD_COLS,
    get_color_from_piece, get_piece_type_from_piece,
    is_red_piece, is_black_piece, is_piece,
    encode_piece, decode_piece,
)

from chess.move import Move


@dataclass(frozen=True)
class Piece:
    """棋子数据类 (不可变)"""
    color: Color
    piece_type: PieceType

    def encode(self) -> int:
        """编码为整数"""
        return encode_piece(self.color, self.piece_type)

    @classmethod
    def decode(cls, encoded: int) -> "Piece":
        """从编码解码"""
        if encoded < 0:
            return EMPTY_PIECE
        color, ptype = decode_piece(encoded)
        return cls(color, ptype)

    @classmethod
    def from_encoding(cls, encoding: int) -> "Piece":
        """从编码创建棋子"""
        return cls.decode(encoding)

    def __repr__(self) -> str:
        color_name = "红" if self.color == Color.RED else "黑"
        type_names = {
            PieceType.KING: "将" if self.color == Color.RED else "帅",
            PieceType.ADVISOR: "士",
            PieceType.BISHOP: "相" if self.color == Color.RED else "象",
            PieceType.KNIGHT: "马",
            PieceType.ROOK: "车",
            PieceType.CANNON: "炮",
            PieceType.PAWN: "兵" if self.color == Color.RED else "卒",
        }
        return f"{color_name}{type_names.get(self.piece_type, '?')}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Piece):
            return False
        return self.color == other.color and self.piece_type == other.piece_type

    def __hash__(self) -> int:
        return hash((self.color, self.piece_type))


# 空棋子
EMPTY_PIECE = Piece(Color.NONE, PieceType.KING)


def piece_from_encoding(encoding: int) -> Piece:
    """从编码获取棋子"""
    return Piece.decode(encoding)


def create_red_king() -> Piece:
    return Piece(Color.RED, PieceType.KING)


def create_black_king() -> Piece:
    return Piece(Color.BLACK, PieceType.KING)


class Board:
    """棋盘类 (10行 × 9列)
    
    坐标系统: (col, row)
    - col: 列, 从左到右 0-8 (对应 a-i)
    - row: 行, 从上到下 0-9 (0为红方底线)
    
    初始布局:
        9  黑方底线
        8  黑底线
        7  黑宫
        6  
        5  楚河汉界
        4  
        3  红宫
        2  红底线
        1  
        0  红方底线
           0 1 2 3 4 5 6 7 8
    """

    def __init__(self, board: Optional[List[List[int]]] = None):
        """初始化棋盘
        
        Args:
            board: 10x9 二维数组，值为棋子编码。None 则创建初始布局。
        """
        if board is not None:
            self._board = [row[:] for row in board]  # 深拷贝
        else:
            self._board = self._create_initial_board()

    @staticmethod
    def _create_initial_board() -> list[list[int]]:
        """创建初始棋盘布局
        
        位置说明:
        - row 0: 红方底线 (将帅士象马车炮兵)
        - row 2: 黑方底线 (帅仕象马车炮卒)
        - row 3,6: 炮和车
        - row 5: 楚河汉界
        - row 4: 卒/兵
        """
        # 创建空棋盘
        board = [[PIECE_EMPTY for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]

        # ========== 黑方 (上方) ==========
        # 黑帅 (row 0, col 4)
        board[0][4] = PIECE_BLACK_KING
        # 黑仕 (row 0, col 3, 5)
        board[0][3] = PIECE_BLACK_ADVISOR
        board[0][5] = PIECE_BLACK_ADVISOR
        # 黑象 (row 0, col 2, 6)
        board[0][2] = PIECE_BLACK_BISHOP
        board[0][6] = PIECE_BLACK_BISHOP
        # 黑马 (row 0, col 1, 7)
        board[0][1] = PIECE_BLACK_KNIGHT
        board[0][7] = PIECE_BLACK_KNIGHT
        # 黑车 (row 0, col 0, 8)
        board[0][0] = PIECE_BLACK_ROOK
        board[0][8] = PIECE_BLACK_ROOK
        # 黑炮 (row 2, col 1, 7)
        board[2][1] = PIECE_BLACK_CANNON
        board[2][7] = PIECE_BLACK_CANNON
        # 黑卒 (row 3, col 0, 2, 4, 6, 8) - 已过河
        board[3][0] = PIECE_BLACK_PAWN
        board[3][2] = PIECE_BLACK_PAWN
        board[3][4] = PIECE_BLACK_PAWN
        board[3][6] = PIECE_BLACK_PAWN
        board[3][8] = PIECE_BLACK_PAWN

        # ========== 红方 (下方) ==========
        # 红将 (row 9, col 4)
        board[9][4] = PIECE_RED_KING
        # 红士 (row 9, col 3, 5)
        board[9][3] = PIECE_RED_ADVISOR
        board[9][5] = PIECE_RED_ADVISOR
        # 红相 (row 9, col 2, 6)
        board[9][2] = PIECE_RED_BISHOP
        board[9][6] = PIECE_RED_BISHOP
        # 红马 (row 9, col 1, 7)
        board[9][1] = PIECE_RED_KNIGHT
        board[9][7] = PIECE_RED_KNIGHT
        # 红车 (row 9, col 0, 8)
        board[9][0] = PIECE_RED_ROOK
        board[9][8] = PIECE_RED_ROOK
        # 红炮 (row 7, col 1, 7)
        board[7][1] = PIECE_RED_CANNON
        board[7][7] = PIECE_RED_CANNON
        # 红兵 (row 6, col 0, 2, 4, 6, 8) - 未过河
        board[6][0] = PIECE_RED_PAWN
        board[6][2] = PIECE_RED_PAWN
        board[6][4] = PIECE_RED_PAWN
        board[6][6] = PIECE_RED_PAWN
        board[6][8] = PIECE_RED_PAWN

        return board

    def clone(self) -> "Board":
        """创建棋盘深拷贝"""
        return Board([row[:] for row in self._board])

    def get(self, col: int, row: int) -> int:
        """获取指定位置的棋子编码
        
        Args:
            col: 列 (0-8)
            row: 行 (0-9)
            
        Returns:
            棋子编码，负数表示空位
        """
        if not self._is_valid_pos(col, row):
            return PIECE_EMPTY
        return self._board[row][col]

    def set(self, col: int, row: int, piece: int) -> None:
        """设置指定位置的棋子
        
        Args:
            col: 列 (0-8)
            row: 行 (0-9)
            piece: 棋子编码，负数表示清空
        """
        if self._is_valid_pos(col, row):
            self._board[row][col] = piece

    def make_move(self, move: Move) -> int:
        """执行着法并返回被吃掉的棋子编码"""
        piece = self.get(move.from_col, move.from_row)
        captured = self.get(move.to_col, move.to_row)
        self.set(move.to_col, move.to_row, piece)
        self.set(move.from_col, move.from_row, PIECE_EMPTY)
        return captured

    def unmake_move(self, move: Move, captured: int) -> None:
        """撤销着法，恢复被吃掉的棋子"""
        piece = self.get(move.to_col, move.to_row)
        self.set(move.from_col, move.from_row, piece)
        self.set(move.to_col, move.to_row, captured)

    def get_piece(self, col: int, row: int) -> Optional[Piece]:
        """获取指定位置的棋子对象
        
        Returns:
            Piece 对象，空位返回 None
        """
        encoding = self.get(col, row)
        if encoding < 0:
            return None
        return Piece.decode(encoding)

    def is_empty(self, col: int, row: int) -> bool:
        """判断指定位置是否为空"""
        return self.get(col, row) < 0

    def is_valid_pos(self, col: int, row: int) -> bool:
        """判断坐标是否有效"""
        return self._is_valid_pos(col, row)

    @staticmethod
    def _is_valid_pos(col: int, row: int) -> bool:
        """判断坐标是否在棋盘范围内"""
        return 0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS

    def find_king(self, color: Color) -> Optional[Tuple[int, int]]:
        """找到指定颜色将/帅的位置
        
        Args:
            color: 棋子颜色
            
        Returns:
            (col, row) 或 None
        """
        king_encoding = PIECE_RED_KING if color == Color.RED else PIECE_BLACK_KING
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                if self._board[row][col] == king_encoding:
                    return (col, row)
        return None

    def count_pieces(self, color: Optional[Color] = None) -> int:
        """统计棋子数量
        
        Args:
            color: 统计指定颜色，None 统计所有
            
        Returns:
            棋子数量
        """
        count = 0
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                piece = self._board[row][col]
                if piece >= 0:
                    if color is None or get_color_from_piece(piece) == color:
                        count += 1
        return count

    def get_all_pieces(self, color: Optional[Color] = None) -> List[Tuple[int, int, int]]:
        """获取所有棋子的位置
        
        Args:
            color: 获取指定颜色，None 获取所有
            
        Returns:
            [(col, row, encoding), ...]
        """
        pieces = []
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                piece = self._board[row][col]
                if piece >= 0:
                    if color is None or get_color_from_piece(piece) == color:
                        pieces.append((col, row, piece))
        return pieces

    def to_array(self) -> list[list[int]]:
        """转换为二维数组"""
        return [row[:] for row in self._board]

    def __repr__(self) -> str:
        """打印棋盘
        
        返回格式:
            9  车 马 相 仕 帅 仕 象 马 车
            8  · · 炮 · · · 炮 · ·
            7  · · · · · · · · ·
            6  兵 · 兵 · 兵 · 兵 · 兵
            5  ─ ─ ─ ─ ─ ─ ─ ─ ─
            4  ─ ─ ─ ─ ─ ─ ─ ─ ─
            3  卒 · 卒 · 卒 · 卒 · 卒
            2  · · 炮 · · · 炮 · ·
            1  · · · · · · · · ·
            0  车 马 相 仕 将 仕 相 马 车
              0 1 2 3 4 5 6 7 8
        """
        lines = []
        piece_chars = {
            PIECE_RED_KING: "将", PIECE_RED_ADVISOR: "士", PIECE_RED_BISHOP: "相",
            PIECE_RED_KNIGHT: "马", PIECE_RED_ROOK: "车", PIECE_RED_CANNON: "炮",
            PIECE_RED_PAWN: "兵",
            PIECE_BLACK_KING: "帅", PIECE_BLACK_ADVISOR: "仕", PIECE_BLACK_BISHOP: "象",
            PIECE_BLACK_KNIGHT: "马", PIECE_BLACK_ROOK: "车", PIECE_BLACK_CANNON: "炮",
            PIECE_BLACK_PAWN: "卒",
        }

        for row in range(BOARD_ROWS - 1, -1, -1):
            line = f"{row}  "
            for col in range(BOARD_COLS):
                piece = self._board[row][col]
                if piece in piece_chars:
                    line += piece_chars[piece]
                elif row == 5 and col == 4:  # 楚河汉界
                    line += "楚"
                elif row == 4 and col == 4:  # 汉界
                    line += "汉"
                else:
                    line += "·"
                line += " "
            lines.append(line)
        
        lines.append("   0 1 2 3 4 5 6 7 8")
        return "\n".join(lines)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Board):
            return False
        return self._board == other._board

    def __hash__(self) -> int:
        # 将棋盘转换为元组用于哈希
        return hash(tuple(tuple(row) for row in self._board))


def create_initial_board() -> Board:
    """创建初始棋盘"""
    return Board()


def board_from_array(board_array: list[list[int]]) -> Board:
    """从数组创建棋盘"""
    return Board(board_array)


def board_to_fen(board: Board, turn: Color) -> str:
    """将棋盘转换为 FEN 格式 (简化版)
    
    FEN 行顺序: 从棋盘顶部(row 0, 黑方底线) 到底部(row 9, 红方底线)
    大写字母 = 红方, 小写字母 = 黑方
    """
    lines = []
    for row in range(BOARD_ROWS):
        line = ""
        empty_count = 0
        for col in range(BOARD_COLS):
            piece = board.get(col, row)
            if piece < 0:
                empty_count += 1
            else:
                if empty_count > 0:
                    line += str(empty_count)
                    empty_count = 0
                ptype = get_piece_type_from_piece(piece)
                color = get_color_from_piece(piece)
                
                # FEN 使用大写表示红方，小写表示黑方
                fen_chars = {
                    PieceType.KING: "k" if color == Color.BLACK else "K",
                    PieceType.ADVISOR: "a" if color == Color.BLACK else "A",
                    PieceType.BISHOP: "b" if color == Color.BLACK else "B",
                    PieceType.KNIGHT: "n" if color == Color.BLACK else "N",
                    PieceType.ROOK: "r" if color == Color.BLACK else "R",
                    PieceType.CANNON: "c" if color == Color.BLACK else "C",
                    PieceType.PAWN: "p" if color == Color.BLACK else "P",
                }
                line += fen_chars.get(ptype, "?")
        if empty_count > 0:
            line += str(empty_count)
        lines.append(line)
    
    return "/".join(lines) + f" {('b' if turn == Color.BLACK else 'r')} - - 0 1"


def compute_board_hash(fen: str) -> int:
    """Compute CRC32 hash of a FEN string for board state verification.

    Used by frontend and backend to ensure both sides agree on the current
    board state before accepting a move. The hash is sent alongside every
    board-state message and validated on incoming moves.

    Args:
        fen: FEN string representing the current board state.

    Returns:
        CRC32 checksum (unsigned 32-bit integer).
    """
    return zlib.crc32(fen.encode("utf-8"))


def fen_to_board(fen: str) -> Board:
    """从 FEN 字符串恢复棋盘
    
    Args:
        fen: FEN 格式棋盘字符串
        
    Returns:
        Board 对象
    """
    # 只取 FEN 的棋盘部分 (第一个空格之前)
    board_part = fen.split(" ")[0] if " " in fen else fen
    rows = board_part.split("/")
    
    fen_to_piece_upper = {
        "K": PIECE_RED_KING,
        "A": PIECE_RED_ADVISOR,
        "B": PIECE_RED_BISHOP,
        "N": PIECE_RED_KNIGHT,
        "R": PIECE_RED_ROOK,
        "C": PIECE_RED_CANNON,
        "P": PIECE_RED_PAWN,
    }
    fen_to_piece_lower = {
        "k": PIECE_BLACK_KING,
        "a": PIECE_BLACK_ADVISOR,
        "b": PIECE_BLACK_BISHOP,
        "n": PIECE_BLACK_KNIGHT,
        "r": PIECE_BLACK_ROOK,
        "c": PIECE_BLACK_CANNON,
        "p": PIECE_BLACK_PAWN,
    }
    
    board = Board()  # Creates empty board
    # FEN rows go from top (row 0, black side) to bottom (row 9, red side)
    for i, row_str in enumerate(rows):
        row = i  # FEN row 0 = board row 0 (black side)
        col = 0
        for ch in row_str:
            if ch.isdigit():
                # Empty squares
                count = int(ch)
                for _ in range(count):
                    if col < BOARD_COLS:
                        board.set(col, row, PIECE_EMPTY)
                        col += 1
            else:
                if ch.isupper():
                    piece = fen_to_piece_upper.get(ch, PIECE_EMPTY)
                else:
                    piece = fen_to_piece_lower.get(ch, PIECE_EMPTY)
                if col < BOARD_COLS:
                    board.set(col, row, piece)
                    col += 1
    
    return board
