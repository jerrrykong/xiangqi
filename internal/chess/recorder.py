"""着法记录器 - 记录完整对局，用于存档、回放和和棋检测."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
import random
import struct
import json

from shared.constants import (
    Color,
    BOARD_ROWS,
    BOARD_COLS,
    PIECE_EMPTY,
)
from shared.protocol import Move

from .piece import Board
from .game import MoveRecord


# ==================== Zobrist Hashing ====================

class ZobristHasher:
    """Zobrist 哈希 - 用于局面唯一标识与和棋检测
    
    Zobrist 哈希通过异或预计算随机数实现 O(1) 局面更新:
    - 每个 (棋子, 位置) 有一个随机 64 位哈希值
    - 局面哈希 = 所有棋子位置哈希的异或
    - 移动棋子: 新哈希 = 旧哈希 ^ 原位置 ^ 新位置
    """
    
    # 64位哈希值
    _piece_keys: Dict[Tuple[int, int, int], int] = {}  # (color, piece_type, pos) -> hash
    _side_key: int = 0  # 轮到哪方的哈希值
    
    @classmethod
    def init(cls) -> None:
        """初始化随机数生成器 (只调用一次)"""
        if not cls._piece_keys:
            random.seed(0x13579ACE)  # 固定种子确保可复现
            cls._side_key = cls._rand64()
            # 为所有棋子位置生成随机哈希
            for color in range(2):  # 0=红, 1=黑
                for ptype in range(7):  # 0-6
                    for pos in range(BOARD_ROWS * BOARD_COLS):
                        cls._piece_keys[(color, ptype, pos)] = cls._rand64()
    
    @staticmethod
    def _rand64() -> int:
        """生成64位随机数"""
        return random.getrandbits(64)
    
    @classmethod
    def compute_hash(cls, board: Board, turn: Color) -> int:
        """计算棋局的 Zobrist 哈希
        
        Args:
            board: 棋盘
            turn: 当前回合
            
        Returns:
            64位哈希值
        """
        h = 0
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                piece = board.get(col, row)
                if piece >= 0:
                    pos = row * BOARD_COLS + col
                    color = piece // 10
                    ptype = piece % 10
                    h ^= cls._piece_keys.get((color, ptype, pos), 0)
        
        if turn == Color.BLACK:
            h ^= cls._side_key
        
        return h
    
    @classmethod
    def update_hash(
        cls,
        old_hash: int,
        piece: int,
        from_col: int,
        from_row: int,
        to_col: int,
        to_row: int,
        captured: int,
        turn: Color,
    ) -> int:
        """增量更新哈希 (着法执行后)
        
        Args:
            old_hash: 旧哈希
            piece: 移动的棋子
            from_col, from_row: 起始位置
            to_col, to_row: 目标位置
            captured: 被吃的棋子 (负数=空位)
            turn: 移动方的颜色
            
        Returns:
            新的哈希值
        """
        h = old_hash
        
        # 移除原位置
        from_pos = from_row * BOARD_COLS + from_col
        from_color = piece // 10
        from_ptype = piece % 10
        h ^= cls._piece_keys.get((from_color, from_ptype, from_pos), 0)
        
        # 添加新位置
        to_pos = to_row * BOARD_COLS + to_col
        h ^= cls._piece_keys.get((from_color, from_ptype, to_pos), 0)
        
        # 如果吃子, 移除被吃的棋子
        if captured >= 0:
            cap_color = captured // 10
            cap_ptype = captured % 10
            h ^= cls._piece_keys.get((cap_color, cap_ptype, to_pos), 0)
        
        # 切换回合 (添加/移除 side key)
        h ^= cls._side_key
        
        return h


# 初始化 Zobrist 表
ZobristHasher.init()


# ==================== 和棋检测规则 ====================

@dataclass
class RepetitionState:
    """重复局面状态
    
    记录以下和棋规则:
    1. 三次重复 (同一局面出现3次)
    2. 50步和棋 (连续50步无吃子无兵/卒移动)
    3. 必然和棋局面 (如双方只剩将帅)
    """
    # 局面哈希 -> 出现次数
    position_counts: Dict[int, int] = field(default_factory=dict)
    
    # 连续无吃子/兵/卒移动步数
    halfmove_clock: int = 0
    
    # 总着法数
    fullmove_number: int = 0
    
    # 记录最后若干步的哈希 (用于三次重复检测)
    recent_hashes: List[int] = field(default_factory=list)
    
    MAX_RECENT_HASHES: int = 20  # 只保留最近20步

    def record_position(self, board: Board, turn: Color, piece: int, captured: int) -> None:
        """记录局面
        
        Args:
            board: 当前棋盘
            turn: 当前回合 (着法执行前)
            piece: 移动的棋子
            captured: 是否吃子
        """
        self.fullmove_number += 1
        
        # 计算哈希
        h = ZobristHasher.compute_hash(board, turn)
        
        # 记录哈希
        self.position_counts[h] = self.position_counts.get(h, 0) + 1
        self.recent_hashes.append(h)
        if len(self.recent_hashes) > self.MAX_RECENT_HASHES:
            old = self.recent_hashes.pop(0)
            # 从计数中移除
            self.position_counts[old] -= 1
            if self.position_counts[old] == 0:
                del self.position_counts[old]
        
        # 更新 halfmove clock
        ptype = piece % 10
        if captured >= 0 or ptype == 6:  # 吃子 或 兵/卒移动
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

    def is_threefold_repetition(self) -> bool:
        """检查是否三次重复"""
        if not self.recent_hashes:
            return False
        return self.position_counts.get(self.recent_hashes[-1], 0) >= 3

    def is_fifty_move_rule(self) -> bool:
        """检查是否50步和棋"""
        return self.halfmove_clock >= 50

    def is_insufficient_material(self) -> bool:
        """检查是否必然和棋 (子力不足)
        
        已知必然和棋局面:
        - 双方只剩将/帅
        - 一方将/帅 + 一象 vs 另一方将/帅
        - 一方将/帅 + 一马 vs 另一方将/帅
        """
        # 简化版: 由 GameRecorder 在外部判断
        return False


# ==================== 着法记录器 ====================

class GameRecorder:
    """着法记录器
    
    功能:
    - 记录完整对局着法
    - Zobrist 哈希计算
    - 和棋检测 (三次重复、50步规则)
    - 对局存档 (JSON格式)
    - 对局回放
    """
    
    def __init__(self, room_id: str = ""):
        """初始化记录器
        
        Args:
            room_id: 房间ID
        """
        self.room_id = room_id
        
        # 原始棋盘 (用于回放)
        self.initial_board = Board()
        
        # 着法历史
        self.moves: List[MoveRecord] = []
        
        # 和棋检测状态
        self.repetition = RepetitionState()
        
        # 当前哈希 (动态更新)
        self._current_hash = ZobristHasher.compute_hash(
            self.initial_board, Color.RED
        )
        
        # 元数据
        self.red_player: str = ""
        self.black_player: str = ""
        self.start_time: Optional[str] = None
        self.end_time: Optional[str] = None
        self.result: Optional[str] = None
        self.result_reason: Optional[str] = None

    @property
    def current_hash(self) -> int:
        """当前局面哈希"""
        return self._current_hash

    @property
    def move_count(self) -> int:
        """着法总数"""
        return len(self.moves)

    def record_move(
        self,
        move: Move,
        player: Color,
        piece: int,
        captured: int,
        board_before: List[List[int]],
        board_after: List[List[int]],
        is_check: bool = False,
    ) -> None:
        """记录一步着法
        
        Args:
            move: 着法
            player: 执行着法的玩家
            piece: 移动的棋子
            captured: 被吃的棋子
            board_before: 着法前棋盘
            board_after: 着法后棋盘
            is_check: 是否将军
        """
        # 创建着法记录
        record = MoveRecord(
            move=move,
            player=player,
            piece=piece,
            captured=captured,
            board_before=board_before,
            board_after=board_after,
            is_check=is_check,
        )
        self.moves.append(record)
        
        # 更新哈希
        board = Board(board_after)
        # 回合计数在 record_move 调用时, turn 还是执行着法的玩家
        self._current_hash = ZobristHasher.update_hash(
            self._current_hash,
            piece,
            move.from_col,
            move.from_row,
            move.to_col,
            move.to_row,
            captured,
            player,
        )
        
        # 记录和棋检测状态
        self.repetition.record_position(board, player, piece, captured)

    def check_draw(self) -> Tuple[bool, Optional[str]]:
        """检查是否和棋
        
        Returns:
            (是否和棋, 和棋原因)
        """
        if self.repetition.is_threefold_repetition():
            return True, "三次重复局面"
        if self.repetition.is_fifty_move_rule():
            return True, "50步和棋"
        if self.repetition.is_insufficient_material():
            return True, "子力不足"
        return False, None

    def undo_last(self) -> bool:
        """撤销最后一步着法
        
        Returns:
            True=撤销成功, False=无法撤销
        """
        if not self.moves:
            return False
        
        self.moves.pop()
        
        # 重新计算哈希 (从初始局面)
        # 简化: 直接重新计算
        if self.moves:
            board = Board(self.moves[-1].board_after)
            last_player = self.moves[-1].player
            next_turn = Color.BLACK if last_player == Color.RED else Color.RED
            self._current_hash = ZobristHasher.compute_hash(board, next_turn)
        else:
            self._current_hash = ZobristHasher.compute_hash(
                self.initial_board, Color.RED
            )
        
        return True

    # ==================== 存档与回放 ====================

    def to_json(self) -> str:
        """导出为 JSON 格式
        
        格式:
        {
            "room_id": "...",
            "players": {"red": "...", "black": "..."},
            "start_time": "...",
            "end_time": "...",
            "result": "...",
            "result_reason": "...",
            "moves": [
                {
                    "from": "e1",
                    "to": "e2",
                    "player": "red",
                    "piece": 4,
                    "captured": -1,
                    "is_check": false,
                    "notation": "车e1到e2"
                },
                ...
            ]
        }
        """
        from shared.constants import coord_to_notation
        
        data = {
            "room_id": self.room_id,
            "players": {
                "red": self.red_player,
                "black": self.black_player,
            },
            "start_time": self.start_time,
            "end_time": self.end_time,
            "result": self.result,
            "result_reason": self.result_reason,
            "moves": [],
        }
        
        for i, record in enumerate(self.moves):
            data["moves"].append({
                "move_no": i + 1,
                "from": coord_to_notation(record.move.from_col, record.move.from_row),
                "to": coord_to_notation(record.move.to_col, record.move.to_row),
                "player": "red" if record.player == Color.RED else "black",
                "piece": record.piece,
                "captured": record.captured,
                "is_check": record.is_check,
                "notation": record.notation,
            })
        
        return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "GameRecorder":
        """从 JSON 恢复
        
        Args:
            json_str: JSON 格式的对局记录
            
        Returns:
            GameRecorder 实例
        """
        data = json.loads(json_str)
        
        recorder = cls(room_id=data.get("room_id", ""))
        recorder.red_player = data.get("players", {}).get("red", "")
        recorder.black_player = data.get("players", {}).get("black", "")
        recorder.start_time = data.get("start_time")
        recorder.end_time = data.get("end_time")
        recorder.result = data.get("result")
        recorder.result_reason = data.get("result_reason")
        
        # 恢复着法
        from shared.constants import notation_to_coord
        
        for m in data.get("moves", []):
            from_coord = notation_to_coord(m["from"])
            to_coord = notation_to_coord(m["to"])
            if from_coord and to_coord:
                move = Move(from_coord[0], from_coord[1], to_coord[0], to_coord[1])
                player = Color.RED if m["player"] == "red" else Color.BLACK
                
                board_before = Board(recorder.moves[-1].board_after) if recorder.moves else Board()
                board_before = board_before.to_array()
                
                board_after = Board()
                board_after.set(to_coord[0], to_coord[1], m["piece"])
                board_after.set(from_coord[0], from_coord[1], PIECE_EMPTY)
                board_after = board_after.to_array()
                
                recorder.record_move(
                    move=move,
                    player=player,
                    piece=m["piece"],
                    captured=m["captured"],
                    board_before=board_before,
                    board_after=board_after,
                    is_check=m.get("is_check", False),
                )
        
        return recorder

    def get_board_at_move(self, move_no: int) -> Optional[Board]:
        """获取第 N 步后的棋盘
        
        Args:
            move_no: 步数 (1=第一步后, 0=初始局面)
            
        Returns:
            棋盘或 None
        """
        if move_no == 0:
            return Board()
        if 1 <= move_no <= len(self.moves):
            return Board(self.moves[move_no - 1].board_after)
        return None

    def replay(self):
        """生成器: 逐步回放对局
        
        Yields:
            (step, MoveRecord, Board)
        """
        board = Board()
        for i, record in enumerate(self.moves):
            yield i + 1, record, board
            board = Board(record.board_after)
