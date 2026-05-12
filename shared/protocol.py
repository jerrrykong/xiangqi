"""Protocol definitions for Xiangqi game."""
from dataclasses import dataclass
from typing import Any, Optional, List
import json


@dataclass
class Move:
    """着法"""
    from_col: int  # 起始列 0-8
    from_row: int  # 起始行 0-9
    to_col: int    # 目标列 0-8
    to_row: int    # 目标行 0-9

    def __post_init__(self):
        self.from_col = int(self.from_col)
        self.from_row = int(self.from_row)
        self.to_col = int(self.to_col)
        self.to_row = int(self.to_row)

    def is_valid(self) -> bool:
        """检查着法坐标是否有效"""
        return (0 <= self.from_col <= 8 and 0 <= self.from_row <= 9 and
                0 <= self.to_col <= 8 and 0 <= self.to_row <= 9)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Move):
            return False
        return (self.from_col == other.from_col and
                self.from_row == other.from_row and
                self.to_col == other.to_col and
                self.to_row == other.to_row)

    def __hash__(self) -> int:
        return hash((self.from_col, self.from_row, self.to_col, self.to_row))

    def __repr__(self) -> str:
        return f"Move({self.from_col},{self.from_row}->{self.to_col},{self.to_row})"

    def encode(self) -> int:
        """将着法编码为整数 (0-2084)
        
        编码方式: encoded = from * 90 + to
        from = from_col + from_row * 9
        to = to_col + to_row * 9
        """
        from_idx = self.from_col + self.from_row * 9
        to_idx = self.to_col + self.to_row * 9
        return from_idx + to_idx * 90

    @classmethod
    def decode(cls, encoded: int) -> "Move":
        """从编码解码着法"""
        to_idx = encoded // 90
        from_idx = encoded % 90
        return cls(
            from_col=from_idx % 9,
            from_row=from_idx // 9,
            to_col=to_idx % 9,
            to_row=to_idx // 9,
        )


# ============ HTTP 统一响应格式 ============

@dataclass
class Response:
    """HTTP 统一响应"""
    code: int
    message: str
    data: Any = None

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result

    def to_json(self) -> str:
        """转换为 JSON"""
        return json.dumps(self.to_dict())


def success_response(data: Any = None) -> Response:
    """创建成功响应"""
    return Response(code=0, message="ok", data=data)


def error_response(code: int, message: str, detail: str = "") -> Response:
    """创建错误响应"""
    return Response(code=code, message=message, data={"detail": detail} if detail else None)


# ============ WebSocket 消息结构 ============

@dataclass
class WSMessage:
    """WebSocket 消息基类"""
    type: str


@dataclass
class MoveMessage:
    """走棋消息"""
    type: str = "move"
    move: Optional[Move] = None


@dataclass
class ResignMessage:
    """认输消息"""
    type: str = "resign"


@dataclass
class DrawReqMessage:
    """请求和棋消息"""
    type: str = "draw_req"


@dataclass
class DrawAnsMessage:
    """和棋应答消息"""
    type: str = "draw_ans"
    accept: bool = False


@dataclass
class StateSyncMessage:
    """状态同步消息"""
    type: str = "state_sync"
    board: Optional[List[List[int]]] = None
    turn: int = 0  # 0=红, 1=黑
    red_time: int = 0
    black_time: int = 0
    room_id: str = ""
    your_color: int = 0


@dataclass
class OpponentMoveMessage:
    """对手走棋消息"""
    type: str = "opponent_move"
    move: Optional[Move] = None
    red_time: int = 0
    black_time: int = 0


@dataclass
class GameStartMessage:
    """游戏开始消息"""
    type: str = "game_start"
    room_id: str = ""
    your_color: int = 0
    red_time: int = 0
    black_time: int = 0


@dataclass
class GameOverMessage:
    """游戏结束消息"""
    type: str = "game_over"
    result: str = ""
    reason: str = ""
    winner: int = -1  # -1=无, 0=红, 1=黑


@dataclass
class CheckMessage:
    """将军消息"""
    type: str = "check"
    by_piece: int = 0
    from_row: int = 0
    from_col: int = 0
    to_row: int = 0
    to_col: int = 0


@dataclass
class ErrorMessage:
    """错误消息"""
    type: str = "error"
    code: int = 0
    message: str = ""
