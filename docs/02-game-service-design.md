# Game 服务详细设计（Python）

> 服务职责：实时对局引擎、棋盘规则、胜负判定、AI 推理调用
> 技术栈：Python 3.11+ / FastAPI / asyncio / websockets / PyTorch
> 文档版本：v1.0

---

## 一、项目结构

```
game-service/
├── main.py                     # 程序入口（FastAPI + WebSocket）
├── config.py                   # 配置加载
├── chess/
│   ├── __init__.py
│   ├── board.py               # 棋盘数据结构（Board 类）
│   ├── piece.py               # 棋子定义（Piece, Color）
│   ├── move.py                # 着法数据结构（Move）
│   ├── move_generator.py      # 合法着法生成器
│   ├── move_validator.py      # 着法合法性验证
│   ├── win_checker.py         # 胜负判定（将军/困毙）
│   └── game_state.py          # 完整游戏状态（GameState）
├── room/
│   ├── __init__.py
│   ├── room_manager.py        # 房间管理器（RoomManager）
│   ├── room.py                # 房间对象（Room）
│   ├── player_session.py       # 玩家连接会话（PlayerSession）
│   └── timers.py              # 计时器管理
├── protocol/
│   ├── __init__.py
│   ├── message.py             # 消息基类定义
│   ├── inbound.py             # 客户端入站消息
│   ├── outbound.py            # 服务端出站消息
│   └── serializer.py          # JSON 序列化/反序列化
├── handlers/
│   ├── __init__.py
│   ├── move_handler.py        # 落子处理
│   ├── resign_handler.py      # 认输处理
│   ├── draw_handler.py        # 和棋处理
│   └── reconnect_handler.py    # 断线重连处理
├── ai/
│   ├── __init__.py
│   ├── ai_proxy.py            # AI 推理调用封装（AIProxy）
│   ├── difficulty.py          # 难度控制器（DifficultyController）
│   ├── engine.py              # AI 推理引擎接口（推理服务调用）
│   └── timeout.py             # AI 超时处理
├── protocol_handler.py         # 协议总入口
├── http_callback.py           # 对 Game 结果的 HTTP 回调
└── requirements.txt
```

---

## 二、核心数据类

### 2.1 Piece（棋子）

```python
# chess/piece.py
from enum import IntEnum
from dataclasses import dataclass

class Color(IntEnum):
    NONE  = 0
    RED   = 1  # 红方（先手）
    BLACK = 2  # 黑方（后手）

    @property
    def opposite(self) -> 'Color':
        return Color.BLACK if self == Color.RED else Color.RED


class PieceType(IntEnum):
    KING    = 0  # 帅/将
    ADVISOR = 1  # 仕/士
    BISHOP  = 2  # 相/象
    KNIGHT  = 3  # 马
    ROOK    = 4  # 车
    CANNON  = 5  # 炮
    PAWN    = 6  # 兵/卒

    def __str__(self):
        names = {0: '帅将', 1: '仕士', 2: '相象', 3: '马', 4: '车', 5: '炮', 6: '兵卒'}
        return names[self.value]


# 完整棋子编码 = color * 10 + piece_type
def make_code(color: Color, ptype: PieceType) -> int:
    if color == Color.NONE:
        return 0
    return color * 10 + ptype

def decode_code(code: int) -> tuple[Color, PieceType]:
    if code == 0:
        return Color.NONE, PieceType(0)
    color = Color(code // 10)
    ptype = PieceType(code % 10)
    return color, ptype
```

### 2.2 Move（着法）

```python
# chess/move.py
from dataclasses import dataclass, frozen

@frozen(slots=True)
class Move:
    from_col: int   # 起点列 0~8
    from_row: int   # 起点行 0~10
    to_col: int     # 终点列 0~8
    to_row: int     # 终点行 0~10

    def __str__(self) -> str:
        return f"{chr(ord('a') + self.from_col)}{self.from_row}" \
               f"{chr(ord('a') + self.to_col)}{self.to_row}"

    def __repr__(self) -> str:
        return f"Move({self.from_col},{self.from_row}->{self.to_col},{self.to_row})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Move):
            return False
        return (self.from_col == other.from_col
                and self.from_row == other.from_row
                and self.to_col == other.to_col
                and self.to_row == other.to_row)

    def __hash__(self):
        return hash((self.from_col, self.from_row, self.to_col, self.to_row))

    def reversed(self) -> 'Move':
        """生成反向着法（黑方视角，用于对称）"""
        return Move(
            from_col=8 - self.from_col,
            from_row=10 - self.from_row,
            to_col=8 - self.to_col,
            to_row=10 - self.to_row
        )
```

### 2.3 Board（棋盘）

```python
# chess/board.py
import copy
from .piece import Color, PieceType, make_code, decode_code, EMPTY

# 初始棋盘布局
INITIAL_BOARD = [
    [make_code(Color.BLACK, PieceType.ROOK),    0, make_code(Color.BLACK, PieceType.BISHOP), make_code(Color.BLACK, PieceType.ADVISOR),
     make_code(Color.BLACK, PieceType.KING),    make_code(Color.BLACK, PieceType.ADVISOR), make_code(Color.BLACK, PieceType.BISHOP), 0,
     make_code(Color.BLACK, PieceType.ROOK)],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, make_code(Color.BLACK, PieceType.CANNON), 0, 0, 0, 0, 0, make_code(Color.BLACK, PieceType.CANNON), 0],
    [make_code(Color.BLACK, PieceType.PAWN), 0, make_code(Color.BLACK, PieceType.PAWN), 0,
     make_code(Color.BLACK, PieceType.PAWN), 0, make_code(Color.BLACK, PieceType.PAWN), 0, make_code(Color.BLACK, PieceType.PAWN)],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [make_code(Color.RED, PieceType.PAWN), 0, make_code(Color.RED, PieceType.PAWN), 0,
     make_code(Color.RED, PieceType.PAWN), 0, make_code(Color.RED, PieceType.PAWN), 0, make_code(Color.RED, PieceType.PAWN)],
    [0, make_code(Color.RED, PieceType.CANNON), 0, 0, 0, 0, 0, make_code(Color.RED, PieceType.CANNON), 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [make_code(Color.RED, PieceType.ROOK), 0, make_code(Color.RED, PieceType.BISHOP), make_code(Color.RED, PieceType.ADVISOR),
     make_code(Color.RED, PieceType.KING),   make_code(Color.RED, PieceType.ADVISOR), make_code(Color.RED, PieceType.BISHOP), 0,
     make_code(Color.RED, PieceType.ROOK)],
]


class Board:
    """棋盘状态，10×9 数组表示"""

    ROWS = 11  # 0~10
    COLS = 9   # 0~8

    def __init__(self, board: list[list[int]] | None = None):
        if board is None:
            self.grid = [row[:] for row in INITIAL_BOARD]  # 深拷贝
        else:
            self.grid = [row[:] for row in board]

    def get(self, row: int, col: int) -> int:
        """获取指定位置的棋子编码"""
        if 0 <= row < self.ROWS and 0 <= col < self.COLS:
            return self.grid[row][col]
        return 0

    def set(self, row: int, col: int, code: int):
        self.grid[row][col] = code

    def is_empty(self, row: int, col: int) -> bool:
        return self.get(row, col) == 0

    def piece_color(self, row: int, col: int) -> Color:
        code = self.get(row, col)
        if code == 0:
            return Color.NONE
        return Color(code // 10)

    def piece_type(self, row: int, col: int) -> PieceType:
        code = self.get(row, col)
        if code == 0:
            return PieceType(0)
        return PieceType(code % 10)

    def apply_move(self, move: Move) -> tuple[int, bool]:
        """
        执行着法，返回 (被吃棋子编码, 是否吃子)
        """
        captured = self.get(move.to_row, move.to_col)
        self.set(move.to_row, move.to_col, self.get(move.from_row, move.from_col))
        self.set(move.from_row, move.from_col, 0)
        return captured, captured != 0

    def undo_move(self, move: Move, captured: int):
        """撤销着法"""
        self.set(move.from_row, move.from_col, self.get(move.to_row, move.to_col))
        self.set(move.to_row, move.to_col, captured)

    def copy(self) -> 'Board':
        return Board([row[:] for row in self.grid])

    def to_list(self) -> list[list[int]]:
        """转换为嵌套列表（用于网络传输）"""
        return [row[:] for row in self.grid]

    def __str__(self) -> str:
        lines = []
        for r in range(self.ROWS):
            row_str = []
            for c in range(self.COLS):
                code = self.grid[r][c]
                if code == 0:
                    row_str.append(" . ")
                else:
                    color, ptype = decode_code(code)
                    chars = {0: 'K', 1: 'A', 2: 'B', 3: 'N', 4: 'R', 5: 'C', 6: 'P'}
                    ch = chars[ptype.value]
                    row_str.append(f"\033[31m{ch}\033[0m" if color == Color.RED else f"\033[30m{ch}\033[0m")
            lines.append(f"{r:2d} " + "".join(row_str))
        lines.append("    a  b  c  d  e  f  g  h  i")
        return "\n".join(lines)
```

### 2.4 GameState（完整游戏状态）

```python
# chess/game_state.py
from dataclasses import dataclass, field
from enum import IntEnum
from .board import Board
from .move import Move
from .piece import Color

class GameResult(IntEnum):
    ONGOING          = 0
    RED_WINS         = 1
    BLACK_WINS       = 2
    DRAW             = 3
    RED_RESIGN       = 4
    BLACK_RESIGN     = 5
    RED_TIMEOUT      = 6
    BLACK_TIMEOUT    = 7


@dataclass
class GameState:
    """完整对局状态"""
    room_id: str
    board: Board
    current_turn: Color = field(default=Color.RED)  # 红方先手
    result: GameResult = GameResult.ONGOING
    move_no: int = 0

    # 着法历史（用于分析、存档）
    move_history: list[Move] = field(default_factory=list)
    # 每步吃掉的棋子（与 move_history 对应）
    captured_history: list[int] = field(default_factory=list)

    # 红方/黑方是否已认输/申请和棋
    red_resigned: bool = False
    black_resigned: bool = False
    draw_requests: set[Color] = field(default_factory=set)  # 已提交和棋申请的方

    # 计时
    started_at: float = 0.0  # 对局开始时间戳

    def make_move(self, move: Move) -> int:
        """执行着法，返回被吃棋子编码（0=未吃子）"""
        captured, _ = self.board.apply_move(move)
        self.move_history.append(move)
        self.captured_history.append(captured)
        self.move_no += 1
        self.current_turn = self.current_turn.opposite
        return captured

    def undo_last_move(self) -> tuple[Move | None, int]:
        """撤销最后一步，用于悔棋"""
        if not self.move_history:
            return None, 0
        move = self.move_history.pop()
        captured = self.captured_history.pop()
        self.board.undo_move(move, captured)
        self.move_no -= 1
        self.current_turn = self.current_turn.opposite
        return move, captured

    def is_over(self) -> bool:
        return self.result != GameResult.ONGOING

    def to_dict(self) -> dict:
        """转换为 dict（用于断线重连时返回完整状态）"""
        return {
            "room_id": self.room_id,
            "board": self.board.to_list(),
            "current_turn": "red" if self.current_turn == Color.RED else "black",
            "result": int(self.result),
            "move_no": self.move_no,
            "move_history": [str(m) for m in self.move_history],
        }
```

---

## 三、棋盘规则模块

### 3.1 MoveGenerator（合法着法生成）

```python
# chess/move_generator.py
from .board import Board
from .move import Move
from .piece import Color, PieceType

class MoveGenerator:

    def __init__(self, board: Board):
        self.board = board

    def generate_all_moves(self, color: Color) -> list[Move]:
        """生成某方所有合法着法"""
        moves = []
        for row in range(Board.ROWS):
            for col in range(Board.COLS):
                if self.board.piece_color(row, col) == color:
                    moves.extend(self._generate_piece_moves(row, col))
        return moves

    def _generate_piece_moves(self, row: int, col: int) -> list[Move]:
        ptype = self.board.piece_type(row, col)
        color = self.board.piece_color(row, col)

        generators = {
            PieceType.KING:    self._king_moves,
            PieceType.ADVISOR: self._advisor_moves,
            PieceType.BISHOP: self._bishop_moves,
            PieceType.KNIGHT: self._knight_moves,
            PieceType.ROOK:   self._rook_moves,
            PieceType.CANNON: self._cannon_moves,
            PieceType.PAWN:   self._pawn_moves,
        }
        return generators[ptype](row, col, color)

    # ---- 帅/将 ----
    def _king_moves(self, row: int, col: int, color: Color) -> list[Move]:
        moves = []
        # 只能在九宫内移动（红：row 7~10, 黑：row 0~2）
        row_min = 7 if color == Color.RED else 0
        row_max = 10 if color == Color.RED else 2
        col_min, col_max = 3, 5

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if row_min <= nr <= row_max and col_min <= nc <= col_max:
                if self.board.piece_color(nr, nc) != color:
                    moves.append(Move(col, row, nc, nr))
        return moves

    # ---- 仕/士 ----
    def _advisor_moves(self, row: int, col: int, color: Color) -> list[Move]:
        moves = []
        row_min = 7 if color == Color.RED else 0
        row_max = 10 if color == Color.RED else 2
        col_min, col_max = 3, 5

        for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nr, nc = row + dr, col + dc
            if row_min <= nr <= row_max and col_min <= nc <= col_max:
                if self.board.piece_color(nr, nc) != color:
                    moves.append(Move(col, row, nc, nr))
        return moves

    # ---- 相/象 ----
    def _bishop_moves(self, row: int, col: int, color: Color) -> list[Move]:
        moves = []
        row_min = 5 if color == Color.RED else 0
        row_max = 10 if color == Color.RED else 4
        col_min, col_max = 0, 8

        for dr, dc in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
            nr, nc = row + dr, col + dc
            # 象眼不能被堵
            eye_r, eye_c = row + dr // 2, col + dc // 2
            if row_min <= nr <= row_max and col_min <= nc <= col_max:
                if self.board.piece_color(nr, nc) != color and self.board.is_empty(eye_r, eye_c):
                    moves.append(Move(col, row, nc, nr))
        return moves

    # ---- 马 ----
    def _knight_moves(self, row: int, col: int, color: Color) -> list[Move]:
        moves = []
        # 马腿方向 + 马走法
        legs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        jumps = [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                 (1, -2), (1, 2), (2, -1), (2, 1)]

        for (lr, lc), (jr, jc) in zip(legs, jumps):
            leg_r, leg_c = row + lr, col + lc
            jump_r, jump_c = row + jr, col + jc

            if 0 <= leg_r < Board.ROWS and 0 <= leg_c < Board.COLS:
                if self.board.is_empty(leg_r, leg_c):
                    if 0 <= jump_r < Board.ROWS and 0 <= jump_c < Board.COLS:
                        if self.board.piece_color(jump_r, jump_c) != color:
                            moves.append(Move(col, row, jump_c, jump_r))
        return moves

    # ---- 车 ----
    def _rook_moves(self, row: int, col: int, color: Color) -> list[Move]:
        moves = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            while 0 <= nr < Board.ROWS and 0 <= nc < Board.COLS:
                if self.board.is_empty(nr, nc):
                    moves.append(Move(col, row, nc, nr))
                elif self.board.piece_color(nr, nc) != color:
                    moves.append(Move(col, row, nc, nr))
                    break
                else:
                    break
                nr += dr
                nc += dc
        return moves

    # ---- 炮 ----
    def _cannon_moves(self, row: int, col: int, color: Color) -> list[Move]:
        moves = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            jumped = False
            while 0 <= nr < Board.ROWS and 0 <= nc < Board.COLS:
                if not jumped:
                    if self.board.is_empty(nr, nc):
                        moves.append(Move(col, row, nc, nr))
                    elif self.board.piece_color(nr, nc) == color.opposite:
                        jumped = True
                    else:  # 同色棋子在中间
                        break
                else:  # 已跳过一个棋子，寻找炮台
                    if self.board.piece_color(nr, nc) == color.opposite:
                        moves.append(Move(col, row, nc, nr))
                        break
                    elif not self.board.is_empty(nr, nc):
                        break
                nr += dr
                nc += dc
        return moves

    # ---- 兵/卒 ----
    def _pawn_moves(self, row: int, col: int, color: Color) -> list[Move]:
        moves = []
        crossed = (row < 5) if color == Color.RED else (row > 5)
        # 前进方向：红方向上（row-1），黑方向下（row+1）
        forward = -1 if color == Color.RED else 1
        nr = row + forward

        if 0 <= nr < Board.ROWS:
            if self.board.piece_color(nr, col) != color:
                moves.append(Move(col, row, col, nr))

        if crossed:
            # 过河后可横走
            for dc in [-1, 1]:
                nc = col + dc
                if 0 <= nc < Board.COLS and self.board.piece_color(row, nc) != color:
                    moves.append(Move(col, row, nc, row))
        return moves
```

### 3.2 MoveValidator（着法验证）

```python
# chess/move_validator.py
from .board import Board
from .move import Move
from .piece import Color, PieceType
from .move_generator import MoveGenerator
from .win_checker import WinChecker

class MoveValidator:

    def __init__(self, board: Board):
        self.board = board
        self.move_gen = MoveGenerator(board)
        self.win_checker = WinChecker(board)

    def is_valid(self, move: Move, color: Color) -> bool:
        """验证着法是否合法"""
        # 1. 在棋盘范围内
        if not (0 <= move.to_row < Board.ROWS and 0 <= move.to_col < Board.COLS):
            return False

        # 2. 起点有己方棋子
        if self.board.piece_color(move.from_row, move.from_col) != color:
            return False

        # 3. 终点不是己方棋子
        if self.board.piece_color(move.to_row, move.to_col) == color:
            return False

        # 4. 着法在合法着法列表中
        legal_moves = self.move_gen._generate_piece_moves(move.from_row, move.from_col)
        if move not in legal_moves:
            return False

        # 5. 执行后不能送将
        board_copy = self.board.copy()
        board_copy.apply_move(move)
        if self.win_checker.is_king_exposed(color.opposite):
            return False

        return True

    def validate_and_apply(self, game_state, move: Move) -> tuple[bool, str]:
        """验证并执行着法，返回 (成功, 错误信息)"""
        color = game_state.current_turn

        if self.is_valid(move, color):
            captured = game_state.make_move(move)
            return True, ""
        else:
            return False, "invalid move"
```

### 3.3 WinChecker（胜负判定）

```python
# chess/win_checker.py
from .board import Board
from .piece import Color, PieceType
from .move_generator import MoveGenerator

class WinChecker:

    def __init__(self, board: Board):
        self.board = board
        self.move_gen = MoveGenerator(board)

    def find_king(self, color: Color) -> tuple[int, int] | None:
        """找到将/帅的位置"""
        for row in range(Board.ROWS):
            for col in range(Board.COLS):
                if (self.board.piece_type(row, col) == PieceType.KING
                        and self.board.piece_color(row, col) == color):
                    return row, col
        return None

    def is_king_exposed(self, king_color: Color) -> bool:
        """将/帅是否被将军（暴露）"""
        king_pos = self.find_king(king_color)
        if king_pos is None:
            return True  # 将/帅被吃
        krow, kcol = king_pos

        # 检查所有对方棋子是否能吃到将/帅
        attacker_color = king_color.opposite
        for row in range(Board.ROWS):
            for col in range(Board.COLS):
                if self.board.piece_color(row, col) == attacker_color:
                    moves = self.move_gen._generate_piece_moves(row, col)
                    for m in moves:
                        if m.to_row == krow and m.to_col == kcol:
                            return True
        return False

    def is_check(self, color: Color) -> bool:
        """某方是否处于将军状态"""
        return self.is_king_exposed(color)

    def has_legal_moves(self, color: Color) -> bool:
        """某方是否还有合法着法"""
        moves = self.move_gen.generate_all_moves(color)
        for move in moves:
            # 模拟执行
            captured = self.board.get(move.to_row, move.to_col)
            self.board.set(move.to_row, move.to_col, self.board.get(move.from_row, move.from_col))
            self.board.set(move.from_row, move.from_col, 0)

            is_legal = not self.is_king_exposed(color.opposite)

            # 撤销
            self.board.set(move.from_row, move.from_col, self.board.get(move.to_row, move.to_col))
            self.board.set(move.to_row, move.to_col, captured)

            if is_legal:
                return True
        return False

    def check_game_over(self, current_turn: Color) -> tuple[bool, str]:
        """
        检查游戏是否结束及原因
        返回 (是否结束, 结束原因)
        """
        opponent = current_turn.opposite

        if self.is_king_exposed(opponent):
            # 对手将被军
            if self.has_legal_moves(opponent):
                return False, ""  # 被将军但有合法着法
            else:
                # 被将死（无合法着法）
                return True, "checkmate"
        else:
            # 无将军，检查是否困毙
            if not self.has_legal_moves(opponent):
                return True, "stalemate"
        return False, ""
```

---

## 四、房间与连接管理

### 4.1 PlayerSession（玩家会话）

```python
# room/player_session.py
import asyncio
import uuid
from dataclasses import dataclass
from typing import Callable, Awaitable
from enum import IntEnum

class ConnectionState(IntEnum):
    CONNECTED    = 1
    DISCONNECTED = 2


@dataclass
class PlayerSession:
    """单个玩家的 WebSocket 连接会话"""
    user_id: int
    username: str
    side: str              # "red" / "black"
    ws: Any               # websockets.WebSocketServerProtocol
    session_token: str    # 断线重连用
    state: ConnectionState = ConnectionState.CONNECTED

    @staticmethod
    def new_token() -> str:
        return str(uuid.uuid4())
```

### 4.2 Room（房间对象）

```python
# room/room.py
import asyncio
from dataclasses import dataclass, field
from typing import Callable
from enum import IntEnum

from chess.game_state import GameState, GameResult
from chess.piece import Color
from room.player_session import PlayerSession

class RoomPhase(IntEnum):
    WAITING   = 1  # 等待玩家
    PLAYING   = 2  # 对局中
    FINISHED  = 3  # 已结束


@dataclass
class Room:
    room_id: str
    game_type: str            # "pvp" / "pve"
    difficulty: int | None    # PvE 难度，1~5
    phase: RoomPhase = RoomPhase.WAITING

    red_player: PlayerSession | None = None
    black_player: PlayerSession | None = None

    game_state: GameState | None = None

    # 计时器
    move_timer: asyncio.Task | None = None
    move_timeout_seconds: int = 60  # 每步思考时限

    # AI 会话（PvE 专用）
    ai_side: Color | None = None     # AI 控制哪方

    # 回调函数
    on_game_over: Callable | None = None

    @property
    def red_ws(self) -> Any:
        return self.red_player.ws if self.red_player else None

    @property
    def black_ws(self) -> Any:
        return self.black_player.ws if self.black_player else None

    def is_full(self) -> bool:
        return self.red_player is not None and self.black_player is not None

    def is_player_disconnected(self, side: str) -> bool:
        player = self.red_player if side == "red" else self.black_player
        return player is None or player.state == ConnectionState.DISCONNECTED

    def other_side(self, side: str) -> str:
        return "black" if side == "red" else "red"
```

### 4.3 RoomManager（房间生命周期）

```python
# room/room_manager.py
import asyncio
import logging
from typing import Dict

from chess.game_state import GameState
from chess.piece import Color
from room.room import Room, RoomPhase
from room.player_session import PlayerSession
from room.timers import MoveTimer
from chess.move_validator import MoveValidator
from chess.win_checker import WinChecker
from ai.ai_proxy import AIProxy

logger = logging.getLogger(__name__)


class RoomManager:
    """
    房间管理器 — 核心调度器
    每个房间一个 asyncio.Task，独立运行
    """

    def __init__(
        self,
        http_callback_url: str,
        internal_key: str,
    ):
        self.rooms: Dict[str, Room] = {}  # room_id → Room
        self.tasks: Dict[str, asyncio.Task] = {}  # room_id → Task
        self.http_callback_url = http_callback_url
        self.internal_key = internal_key
        self.ai_proxy = AIProxy()

    async def create_pvp_room(
        self,
        room_id: str,
        red_session: PlayerSession,
    ) -> Room:
        """创建人人房间（红方已就位，等待黑方）"""
        room = Room(room_id=room_id, game_type="pvp")
        room.red_player = red_session
        self.rooms[room_id] = room
        return room

    async def join_pvp_room(
        self,
        room_id: str,
        black_session: PlayerSession,
    ) -> Room:
        """黑方加入，开始游戏"""
        room = self.rooms[room_id]
        room.black_player = black_session
        room.phase = RoomPhase.PLAYING
        room.game_state = GameState(room_id=room_id, board=Board())
        room.game_state.started_at = asyncio.get_event_loop().time()

        # 启动房间协程
        room_task = asyncio.create_task(self._run_room(room))
        self.tasks[room_id] = room_task

        return room

    async def create_pve_room(
        self,
        room_id: str,
        player_session: PlayerSession,
        player_side: str,  # 玩家执红或执黑
        difficulty: int,
    ) -> Room:
        """创建人机房间"""
        room = Room(
            room_id=room_id,
            game_type="pve",
            difficulty=difficulty,
        )

        if player_side == "red":
            room.red_player = player_session
            room.ai_side = Color.BLACK
        else:
            room.black_player = player_session
            room.ai_side = Color.RED

        room.phase = RoomPhase.PLAYING
        room.game_state = GameState(room_id=room_id, board=Board())
        room.game_state.started_at = asyncio.get_event_loop().time()

        room_task = asyncio.create_task(self._run_room(room))
        self.tasks[room_id] = room_task

        return room

    async def _run_room(self, room: Room):
        """房间主协程 — 管理整个对局流程"""
        try:
            await self._broadcast_state(room)

            while room.phase == RoomPhase.PLAYING and not room.game_state.is_over():
                current_side = "red" if room.game_state.current_turn == Color.RED else "black"

                # 如果是 AI 回合
                if room.game_type == "pve" and room.ai_side == room.game_state.current_turn:
                    await self._do_ai_move(room)
                    continue

                # 人人 / 玩家回合 — 等待操作或超时
                timeout_task = asyncio.create_task(
                    self._wait_for_move_or_timeout(room, current_side)
                )
                # 在外部通过 room 上挂载的 Future 来触发操作
                room.current_turn = room.game_state.current_turn
                room.move_event = asyncio.Event()

                try:
                    await asyncio.wait_for(
                        room.move_event.wait(),
                        timeout=room.move_timeout_seconds
                    )
                except asyncio.TimeoutError:
                    # 超时判负
                    await self._handle_timeout(room, current_side)
                    break

        except Exception as e:
            logger.exception(f"Room {room.room_id} error: {e}")
        finally:
            await self._cleanup_room(room)

    async def _do_ai_move(self, room: Room):
        """AI 落子"""
        from protocol.outbound import send_ai_thinking

        ws = room.red_ws if room.ai_side == Color.BLACK else room.black_ws
        if ws:
            await send_ai_thinking(ws)

        # 调用 AI 推理
        move = await self.ai_proxy.get_best_move(
            board=room.game_state.board,
            difficulty=room.difficulty,
        )

        await self._apply_and_broadcast_move(room, move)

    async def _apply_and_broadcast_move(
        self,
        room: Room,
        move: Move,
    ):
        """执行着法并广播"""
        from protocol.outbound import send_move_result, send_ai_move, broadcast_game_over

        gs = room.game_state
        captured = gs.make_move(move)
        color = Color.RED if move.from_col < 0 else Color.BLACK  # 简化

        player = gs.move_no % 2 == 1 and room.red_player or room.black_player
        player_side = "red" if gs.current_turn == Color.BLACK else "black"

        msg = {
            "type": "ai_move" if room.game_type == "pve" and room.ai_side == room.game_state.current_turn else "move_result",
            "data": {
                "player": player_side,
                "from": str(move.from_col) + str(move.from_row),
                "to": str(move.to_col) + str(move.to_row),
                "captured": captured,
                "check": False,
            }
        }
        await self._broadcast(room, msg)

        # 胜负判定
        validator = MoveValidator(gs.board)
        win_checker = WinChecker(gs.board)
        is_over, reason = win_checker.check_game_over(gs.current_turn)

        if is_over:
            gs.result = GameResult.RED_WINS if gs.current_turn == Color.BLACK else GameResult.BLACK_WINS
            await self._handle_game_over(room, reason)

    async def _wait_for_move_or_timeout(self, room: Room, side: str):
        """等待玩家操作（由 handlers 调用 room.move_event.set() 触发）"""
        await room.move_event.wait()

    async def _handle_game_over(self, room: Room, reason: str):
        """游戏结束处理"""
        gs = room.game_state
        room.phase = RoomPhase.FINISHED

        result_map = {
            "checkmate": GameResult.RED_WINS if gs.current_turn == Color.BLACK else GameResult.BLACK_WINS,
            "stalemate": GameResult.DRAW,
        }
        gs.result = result_map.get(reason, GameResult.DRAW)

        await self._broadcast_game_over(room, reason)
        await self._http_callback_game_over(room)

    async def _http_callback_game_over(self, room: Room):
        """HTTP 回调通知 Web 服务对局结束"""
        import httpx
        gs = room.game_state

        payload = {
            "room_id": room.room_id,
            "result": int(gs.result),
            "winner": "red" if gs.result in (GameResult.RED_WINS, GameResult.RED_RESIGN) else "black",
            "total_moves": gs.move_no,
        }

        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.http_callback_url}/internal/game/result",
                json=payload,
                headers={"X-Internal-Key": self.internal_key},
                timeout=5.0,
            )

    async def _broadcast(self, room: Room, msg: dict):
        """向房间内所有玩家广播消息"""
        for side, player in [("red", room.red_player), ("black", room.black_player)]:
            if player and player.state == ConnectionState.CONNECTED:
                try:
                    await player.ws.send_json(msg)
                except Exception:
                    pass

    async def _broadcast_state(self, room: Room):
        """广播完整棋盘状态"""
        if room.game_state:
            msg = {
                "type": "state_sync",
                "data": room.game_state.to_dict()
            }
            await self._broadcast(room, msg)

    async def _cleanup_room(self, room: Room):
        """清理房间资源"""
        room.phase = RoomPhase.FINISHED
        if room.room_id in self.rooms:
            del self.rooms[room.room_id]
        if room.room_id in self.tasks:
            del self.tasks[room.room_id]
```

---

## 五、WebSocket 协议处理器

### 5.1 入站消息处理

```python
# handlers/inbound_handler.py
from protocol.inbound import InboundMessage

class InboundHandler:

    def __init__(self, room_manager: RoomManager):
        self.room_manager = room_manager

    async def handle(self, room: Room, player: PlayerSession, msg: InboundMessage):
        handlers = {
            "move":      self._handle_move,
            "resign":   self._handle_resign,
            "draw_req": self._handle_draw_req,
            "draw_ans": self._handle_draw_ans,
            "reconnect": self._handle_reconnect,
        }

        handler = handlers.get(msg.type)
        if handler:
            await handler(room, player, msg.data)

    async def _handle_move(self, room: Room, player: PlayerSession, data: dict):
        from chess.move import Move
        from chess.piece import Color
        from protocol.outbound import send_error

        if room.phase != RoomPhase.PLAYING:
            await send_error(player.ws, 4005, "game already finished")
            return

        side = player.side
        current_side = "red" if room.game_state.current_turn == Color.RED else "black"

        if side != current_side:
            await send_error(player.ws, 4002, "not your turn")
            return

        # 解析着法
        try:
            from_col = ord(data["from"][0]) - ord('a')
            from_row = int(data["from"][1])
            to_col = ord(data["to"][0]) - ord('a')
            to_row = int(data["to"][1])
            move = Move(from_col, from_row, to_col, to_row)
        except Exception:
            await send_error(player.ws, 4001, "invalid move format")
            return

        # 验证并执行
        validator = MoveValidator(room.game_state.board)
        valid, err = validator.validate_and_apply(room.game_state, move)

        if not valid:
            await send_error(player.ws, 4001, err)
            return

        # 触发房间协程继续执行
        room.move_event.set()

    async def _handle_resign(self, room: Room, player: PlayerSession, data: dict):
        """认输处理"""
        side = player.side
        if side == "red":
            room.game_state.red_resigned = True
            room.game_state.result = GameResult.BLACK_WINS
        else:
            room.game_state.black_resigned = True
            room.game_state.result = GameResult.RED_WINS

        await self._handle_game_over(room, "resign")

    async def _handle_draw_req(self, room: Room, player: PlayerSession, data: dict):
        """和棋请求"""
        room.game_state.draw_requests.add(player.side)
        opponent_side = room.other_side(player.side)
        opponent = room.red_player if opponent_side == "red" else room.black_player

        from protocol.outbound import send_draw_request
        if opponent:
            await send_draw_request(opponent.ws, player.side)

    async def _handle_draw_ans(self, room: Room, player: PlayerSession, data: dict):
        """和棋应答"""
        if not data.get("accept"):
            room.game_state.draw_requests.discard(player.side)
            return

        room.game_state.result = GameResult.DRAW
        await self._handle_game_over(room, "draw_agreement")

    async def _handle_reconnect(self, room: Room, player: PlayerSession, data: dict):
        """断线重连"""
        # 见断线重连流程 5.2
        pass
```

### 5.2 断线重连流程

```python
# handlers/reconnect_handler.py
async def handle_reconnect(room_manager: RoomManager, ws, msg: dict):
    """
    客户端断线重连：
    1. 验证 session_token + room_id
    2. 更新 PlayerSession.ws
    3. 发送 state_sync（完整棋盘状态）
    """
    token = msg["data"].get("token")
    room_id = msg["data"].get("room_id")

    room = room_manager.rooms.get(room_id)
    if not room:
        await send_error(ws, 4003, "room not found or game already finished")
        return

    # 找到对应 session
    player = None
    for p in [room.red_player, room.black_player]:
        if p and p.session_token == token:
            player = p
            break

    if not player:
        await send_error(ws, 4003, "reconnect failed: invalid token")
        return

    # 更新连接
    player.ws = ws
    player.state = ConnectionState.CONNECTED

    # 通知对手重连
    opponent_side = room.other_side(player.side)
    opponent = room.red_player if opponent_side == "red" else room.black_player
    from protocol.outbound import send_opponent_rejoin
    if opponent:
        await send_opponent_rejoin(opponent.ws, player.username)

    # 发送完整状态
    from protocol.outbound import send_state_sync
    await send_state_sync(ws, room.game_state)
```

### 5.3 AIProxy（AI 推理调用）

```python
# ai/ai_proxy.py
import asyncio
from chess.board import Board
from chess.move import Move
from ai.engine import AIEngine
from ai.difficulty import DifficultyController

class AIProxy:
    """
    AI 推理调用封装
    - 内部直接调用 AI 引擎（同一进程），零网络开销
    - 支持难度控制
    """

    def __init__(self):
        self.engine = AIEngine()  # 加载 PyTorch 模型
        self.difficulty = DifficultyController()

    async def get_best_move(
        self,
        board: Board,
        difficulty: int,
    ) -> Move:
        """
        获取最佳着法（异步，非阻塞）
        内部使用线程池运行 PyTorch 推理
        """
        sims = self.difficulty.get_sims(difficulty)
        loop = asyncio.get_event_loop()

        # 在线程池中运行（避免阻塞事件循环）
        move = await loop.run_in_executor(
            None,  # 默认线程池
            lambda: self.engine.mcts_search(board, n_simulations=sims)
        )
        return move

    def reload_model(self, model_path: str):
        """热更新模型（训练服务通知后调用）"""
        self.engine.load_model(model_path)
```

---

## 六、主入口（FastAPI + WebSocket）

```python
# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import asyncio
import logging

from room.room_manager import RoomManager
from handlers.inbound_handler import InboundHandler
from protocol.inbound import InboundMessage
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
room_manager = RoomManager(
    http_callback_url=config.WEB_SERVICE_CALLBACK_URL,
    internal_key=config.INTERNAL_SECRET,
)
handler = InboundHandler(room_manager)


@app.websocket("/game/{room_id}")
async def websocket_endpoint(ws: WebSocket, room_id: str):
    """WebSocket 连接入口"""
    await ws.accept()

    # 从 query params 获取 session_token 和 user_id
    token = ws.query_params.get("token")
    user_id = ws.query_params.get("user_id")

    # TODO: 验证 token，获取用户信息

    player = PlayerSession(
        user_id=int(user_id),
        username="",
        side="",  # 由 RoomManager 设置
        ws=ws,
        session_token=token,
    )

    # 加入房间
    room = room_manager.rooms.get(room_id)
    if not room:
        await ws.send_json({"type": "error", "data": {"code": 3001, "message": "room not found"}})
        await ws.close()
        return

    # 注册到房间
    if room.red_player is None:
        room.red_player = player
        player.side = "red"
    elif room.black_player is None:
        room.black_player = player
        player.side = "black"

    try:
        while True:
            data = await ws.receive_text()
            msg = InboundMessage.from_json(data)
            await handler.handle(room, player, msg)

    except WebSocketDisconnect:
        player.state = ConnectionState.DISCONNECTED
        # 通知对手断线，启动 60s 重连计时器
        await _notify_disconnect(room, player)


@app.post("/internal/game/assign")
async def assign_game(req: AssignRequest):
    """
    Web 服务调用：分配对局
    创建房间，启动游戏
    """
    if req.game_type == "pvp":
        room = await room_manager.create_pvp_room(req.room_id, red_session=None)
        # TODO: 等黑方 Web 服务调用 join
    elif req.game_type == "pve":
        player_session = PlayerSession(...)
        player_side = req.players[0]["side"]
        room = await room_manager.create_pve_room(
            req.room_id, player_session, player_side, req.difficulty
        )

    return {"room_id": req.room_id, "ws_url": f"/game/{req.room_id}"}


@app.get("/health")
async def health():
    return {"status": "ok", "rooms": len(room_manager.rooms)}
```

---

## 七、AI 难度控制策略

```python
# ai/difficulty.py
class DifficultyController:

    # MCTS 模拟次数对照表
    DIFFICULTY_SIMS = {
        1: 100,      # 入门
        2: 200,      # 简单
        3: 800,      # 中等
        4: 3200,     # 困难
        5: 6400,     # 大师
    }

    # 思考时间上限（秒）
    THINKING_TIME_LIMIT = {
        1: 3,
        2: 5,
        3: 10,
        4: 20,
        5: 30,
    }

    def get_sims(self, difficulty: int) -> int:
        return self.DIFFICULTY_SIMS.get(difficulty, 800)

    def get_time_limit(self, difficulty: int) -> float:
        return self.THINKING_TIME_LIMIT.get(difficulty, 10.0)

    def get_temperature(self, difficulty: int) -> float:
        """
        MCTS 温度参数（控制着法随机性）
        低难度 = 高温度（更多随机）= 更弱
        """
        temps = {1: 1.5, 2: 1.2, 3: 1.0, 4: 0.8, 5: 0.5}
        return temps.get(difficulty, 1.0)
```
