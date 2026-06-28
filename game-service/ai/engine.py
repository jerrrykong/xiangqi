"""AI 搜索引擎 - 基于 Minimax + Alpha-Beta 剪枝 + MTD(f) 的中国象棋 AI."""
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
import time
import logging

from chess.constants import (
    Color,
    PieceType,
    BOARD_ROWS, BOARD_COLS,
    get_color_from_piece, get_piece_type_from_piece,
    Difficulty, DIFFICULTY_SIMULATIONS,
)
from chess.move import Move

from chess.piece import Board
from chess.move_generator import MoveGenerator, LegalMove
from chess.move_validator import MoveValidator
from chess.win_checker import WinChecker
from chess.recorder import ZobristHasher


logger = logging.getLogger(__name__)


def _log(level: str, msg: str, **kwargs):
    """Structured logging helper."""
    parts = [msg]
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    log_msg = " | ".join(parts)
    getattr(logger, level)(log_msg)


# ==================== 局面评估 ====================

class MaterialTable:
    """棋子价值表 (用于静态评估)
    
    象棋 AI 评估函数 = 棋子价值 + 位置价值
    
    棋子基础价值 (绝对值，由 Evaluator._get_base_value 统一管理):
        兵/卒: 100 (过河后通过位置表加分，等效价值约 150-250)
        士/仕: 200
        象/相: 200
        马:    400
        炮:    450
        车:    900
        将/帅: 10000 (无法直接吃, 吃子时已胜利)
    """
    
    # 位置价值表 (兵/卒 - "row 0 = 黑方底线"视角，与其他表一致)
    # 表为对称设计 (关于 idx 4.5 中心对称)，因此红方反转/黑方不反转结果相同。
    # 兵过河后越深入对方阵地，威胁越大，加分递增。
    # 已合并原 _get_pawn_structure_bonus: 过河(+20) + 中路列(+10)
    #   idx 3 = 兵初始位置 (红兵 row 6 / 黑卒 row 3)
    #   idx 4 = 河口 (未过河但临河)
    #   idx 5 = 刚过河
    #   idx 6/7/8 = 过河中段 (递增)
    #   idx 9 = 对方底线 (最致命)
    PAWN_POSITIONAL: List[List[int]] = [
        [ 70, 100, 120, 150, 180, 150, 120, 100,  70],  # idx 0 = 对方底线 (最致命)
        [ 40,  60,  90, 120, 130, 120,  90,  60,  40],  # idx 1 = 过河更深入
        [ 30,  40,  70, 100, 110, 100,  70,  40,  30],  # idx 2 = 过河深入
        [ 20,  30,  50,  80,  90,  80,  50,  30,  20],  # idx 3 = 过河中段
        [ 20,  20,  40,  60,  70,  60,  40,  20,  20],  # idx 4 = 刚过河
        [  0,   0,  10,  25,  30,  25,  10,   0,   0],  # idx 5 = 河口
        [  0,   0,   0,  10,  10,  10,   0,   0,   0],  # idx 6 = 初始位置
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],  # idx 7 (兵不可达)
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],  # idx 8 (兵不可达)
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],  # idx 9 (兵不可达)
    ]

    @classmethod
    def get_pawn_positional(cls, col: int, row: int, color: Color) -> float:
        """获取兵/卒的位置价值

        表为 "row 0 = 黑方底线" 视角，对称设计。
        - 红方视角: idx = BOARD_ROWS - 1 - row
        - 黑方视角: idx = row
        """
        return float(cls.PAWN_POSITIONAL[row if color == Color.RED else BOARD_ROWS - 1 - row][col])
    
    # 马位置价值 (10行，与棋盘一一对应)
    # 已合并原 _get_knight_activity_bonus (+10 中央区 col 2-6, row 2-7)
    # 已合并原 _get_original_knight_bonus (-20 原位 col 1/7, row 9)
    KNIGHT_POSITIONAL: List[List[int]] = [
        [-8, -6,  2,  4,  6,  4,  2, -6, -8],  # row 0 = 黑方底线
        [-4,  4, 10, 12, 14, 12, 10,  4, -4],  # row 1
        [-2,  0, 12, 14, 14, 14, 12,  0, -2],  # row 2
        [-4,  2, 16, 18, 20, 18, 16,  2, -4],  # row 3
        [-4,  4, 18, 22, 22, 22, 18,  4, -4],  # row 4
        [-4,  6, 18, 20, 22, 20, 18,  6, -4],  # row 5
        [-4,  6, 16, 18, 18, 18, 16,  6, -4],  # row 6
        [-6, -4, 14, 16, 14, 16, 14, -4, -6],  # row 7
        [-8,-10,  6,  8,  6,  8,  6,-10, -8],  # row 8
        [-10,-28, -6, -4, -8, -4, -6,-28,-10],  # row 9 = 红方底线
    ]
    
    @classmethod
    def get_knight_positional(cls, col: int, row: int, color: Color) -> float:
        """获取马的位置价值
        
        表中 row=0 为黑方底线 (row 0), row=9 为红方底线 (row 9)。
        - 黑方视角: table[row]
        - 红方视角: table[BOARD_ROWS-1-row]
        """
        return float(cls.KNIGHT_POSITIONAL[row if color == Color.RED else BOARD_ROWS - 1 - row][col])

    # ——— 炮独立位置价值 (不同于车，炮需要炮架，偏好中路和对方阵地) ———
    # 红方视角, row 0 = 黑方底线, row 9 = 红方底线
    # 已合并原 _get_cannon_activity_bonus: 中路(+8 col 3-5) + 过河(+3 row 0-4)
    CANNON_POSITIONAL: List[List[int]] = [
        [  9,   7,   3,   1,  -1,   1,   3,   7,   9],  # row 0 = 黑方底线
        [  5,   5,   3,   7,   5,   7,   3,   5,   5],  # row 1
        [  7,   9,  11,  23,  25,  23,  11,   9,   7],  # row 2 (炮初始位置附近)
        [ 13,  17,  19,  31,  35,  31,  19,  17,  13],  # row 3 (过河炮)
        [ 15,  19,  21,  35,  39,  35,  21,  19,  15],  # row 4 (河口炮最佳)
        [ 12,  16,  18,  32,  36,  32,  18,  16,  12],  # row 5 (河口炮最佳)
        [ 10,  14,  16,  28,  32,  28,  16,  14,  10],  # row 6
        [  8,  10,  12,  24,  26,  24,  12,  10,   8],  # row 7 (红方初始炮位)
        [  6,   8,   8,  18,  20,  18,   8,   8,   6],  # row 8
        [  4,   6,   6,  16,  16,  16,   6,   6,   4],  # row 9 = 红方底线
    ]

    @classmethod
    def get_cannon_positional(cls, col: int, row: int, color: Color) -> float:
        """获取炮的位置价值"""
        return float(cls.CANNON_POSITIONAL[row if color == Color.RED else BOARD_ROWS - 1 - row][col])

    # ——— 车独立位置价值 (保留原有但提升精度) ———
    # 红方视角
    # 已合并原 _get_rook_activity_bonus: 中路(+10 col 3-5) + 过河(+5 row 0-4)
    ROOK_POSITIONAL_IMPROVED: List[List[int]] = [
        [19, 19, 17, 33, 31, 33, 17, 19, 19],  # row 0
        [21, 25, 23, 39, 41, 39, 23, 25, 21],  # row 1
        [17, 17, 17, 33, 33, 33, 17, 17, 17],  # row 2
        [17, 23, 21, 37, 37, 37, 21, 23, 17],  # row 3
        [17, 19, 17, 33, 33, 33, 17, 19, 17],  # row 4
        [12, 16, 14, 30, 30, 30, 14, 16, 12],  # row 5
        [ 6, 10,  8, 24, 24, 24,  8, 10,  6],  # row 6
        [ 4,  8,  6, 24, 22, 24,  6,  8,  4],  # row 7
        [ 8,  4,  8, 26, 18, 26,  8,  4,  8],  # row 8
        [-2, 10,  6, 24, 22, 24,  6, 10, -2],  # row 9 (底线车稍弱, 但通路车加分)
    ]

    @classmethod
    def get_rook_positional_improved(cls, col: int, row: int, color: Color) -> float:
        """获取车的改进位置价值"""
        return float(cls.ROOK_POSITIONAL_IMPROVED[row if color == Color.RED else BOARD_ROWS - 1 - row][col])

    # ——— 仕/士 位置价值 (仅九宫内有效) ———
    # 红方视角: row 7-9, col 3-5
    ADVISOR_POSITIONAL: List[List[int]] = [
        [0, 0, 0,  0,  0,  0, 0, 0, 0],  # row 0
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0, 20,  0, 20, 0, 0, 0],  # row 7 (红宫顶)
        [0, 0, 0,  0, 30,  0, 0, 0, 0],  # row 8 (红宫中间, 最佳防守)
        [0, 0, 0, 15,  0, 15, 0, 0, 0],  # row 9 (红方底线)
    ]

    @classmethod
    def get_advisor_positional(cls, col: int, row: int, color: Color) -> float:
        """获取仕/士的位置价值"""
        return float(cls.ADVISOR_POSITIONAL[row if color == Color.RED else BOARD_ROWS - 1 - row][col])

    # ——— 相/象 位置价值 (仅己方半场7个点有效) ———
    # 红方视角
    BISHOP_POSITIONAL: List[List[int]] = [
        [0, 0,  0,  0,  0,  0,  0, 0, 0],  # row 0
        [0, 0,  0,  0,  0,  0,  0, 0, 0],
        [0, 0,  0,  0,  0,  0,  0, 0, 0],
        [0, 0,  0,  0,  0,  0,  0, 0, 0],
        [0, 0,  0,  0,  0,  0,  0, 0, 0],
        [0, 0, 20,  0,  0,  0, 20, 0, 0],  # row 5 (红方河沿)
        [0, 0,  0,  0,  0,  0,  0, 0, 0],
        [0, 0,  0,  0, 25,  0,  0, 0, 0],  # row 7
        [0, 0,  0,  0,  0,  0,  0, 0, 0],
        [0, 0, 10,  0,  0,  0, 10, 0, 0],  # row 9 (红方底线)
    ]

    @classmethod
    def get_bishop_positional(cls, col: int, row: int, color: Color) -> float:
        """获取相/象的位置价值"""
        return float(cls.BISHOP_POSITIONAL[row if color == Color.RED else BOARD_ROWS - 1 - row][col])

    # ——— 帅/将 位置价值 (仅九宫内有效) ———
    # 红方视角: row 7-9, col 3-5
    KING_POSITIONAL: List[List[int]] = [
        [0, 0, 0,  0,  0,  0, 0, 0, 0],  # row 0
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  0,  0,  0, 0, 0, 0],
        [0, 0, 0,  5, 10,  5, 0, 0, 0],  # row 7 (红宫顶, 不推荐)
        [0, 0, 0,  8, 15,  8, 0, 0, 0],  # row 8 (红宫一层, 较安全)
        [0, 0, 0, 10, 20, 10, 0, 0, 0],  # row 9 (红方底线, 默认安全)
    ]

    @classmethod
    def get_king_positional(cls, col: int, row: int, color: Color) -> float:
        """获取帅/将的位置价值"""
        return float(cls.KING_POSITIONAL[row if color == Color.RED else BOARD_ROWS - 1 - row][col])


@dataclass
class Evaluator:
    """局面评估器
    
    评估函数 = Σ(棋子价值 + 位置价值) - Σ(对方棋子价值 + 位置价值)
    
    正值 = 红方优势
    负值 = 黑方优势
    """
    
    def evaluate(self, board: Board, turn: Color) -> float:
        """评估局面
        
        Args:
            board: 棋盘
            turn: 当前回合 (用于确定评估方向)
            
        Returns:
            评估分数 (正值红优, 负值黑优)
        """
        red_score = 0.0
        black_score = 0.0

        # 基于局面剩余棋子数量调节马/炮的价值
        # 排除双方帅/将 (始终存在)
        total_pieces = 0
        for r in range(BOARD_ROWS):
            for c in range(BOARD_COLS):
                p = board.get(c, r)
                if p >= 0:
                    ptype = get_piece_type_from_piece(p)
                    if ptype != PieceType.KING:
                        total_pieces += 1

        # 经验值：开局/中局棋子数较多，max ~30 (两边除去王)
        MAX_PIECES = 30.0
        pieces_norm = max(0.0, min(MAX_PIECES, float(total_pieces)))

        # 马：在残局（棋子少）价值上升；最多 +50%
        knight_multiplier = 1.0 + 0.5 * ((MAX_PIECES - pieces_norm) / MAX_PIECES)

        # 炮：在子力较多时更有价值；最多 +50%
        cannon_multiplier = 1.0 + 0.5 * (pieces_norm / MAX_PIECES)

        # 对局阶段参数：phase 越接近 1 表示越靠近残局
        phase = (MAX_PIECES - pieces_norm) / MAX_PIECES
        self._phase = phase
        
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                piece = board.get(col, row)
                if piece < 0:
                    continue
                
                color = get_color_from_piece(piece)
                ptype = get_piece_type_from_piece(piece)
                
                # 基础价值
                base = self._get_base_value(ptype)
                # 根据剩余子力调整马/炮的基础价值
                if ptype == PieceType.KNIGHT:
                    base = base * knight_multiplier
                elif ptype == PieceType.CANNON:
                    base = base * cannon_multiplier
                
                # 位置价值
                positional = self._get_positional_value(col, row, ptype, color)
                
                total = base + positional
                
                if color == Color.RED:
                    red_score += total
                else:
                    black_score += total
        
        # 转换为红方视角
        raw_score = red_score - black_score
        
        # 如果当前回合是黑方, 取反
        if turn == Color.BLACK:
            raw_score = -raw_score
        
        return raw_score
    
    def _get_base_value(self, ptype: PieceType) -> float:
        """获取棋子基础价值"""
        values = {
            PieceType.PAWN: 100,
            PieceType.ADVISOR: 200,
            PieceType.BISHOP: 200,
            PieceType.KNIGHT: 400,
            PieceType.CANNON: 450,
            PieceType.ROOK: 900,
            PieceType.KING: 10000,
        }
        return float(values.get(ptype, 0))
    
    def _get_positional_value(
        self, col: int, row: int, ptype: PieceType, color: Color
    ) -> float:
        """获取棋子位置价值

        7类棋子各有独立位置表，参考 vliang-cpp 的设计理念。
        依据对局阶段调整权重：开局位置价值强，残局子力价值强。
        注：兵/车/炮/马的位置表中已包含原 activity_bonus，无需额外加成。
        """
        phase = getattr(self, '_phase', 0.0)
        opening_factor = 1.0 - phase

        if ptype == PieceType.PAWN:
            return MaterialTable.get_pawn_positional(col, row, color) * (1.0 + 0.3 * phase)
        elif ptype == PieceType.ROOK:
            return MaterialTable.get_rook_positional_improved(col, row, color) * (1.0 + 0.3 * opening_factor)
        elif ptype == PieceType.CANNON:
            return MaterialTable.get_cannon_positional(col, row, color) * (1.0 + 0.3 * opening_factor)
        elif ptype == PieceType.KNIGHT:
            return MaterialTable.get_knight_positional(col, row, color) * (1.0 + 0.4 * phase)
        elif ptype == PieceType.ADVISOR:
            return MaterialTable.get_advisor_positional(col, row, color) * (1.0 + 0.2 * phase)
        elif ptype == PieceType.BISHOP:
            return MaterialTable.get_bishop_positional(col, row, color) * (1.0 + 0.3 * phase)
        elif ptype == PieceType.KING:
            # 帅的位置价值固定，不应用阶段因子
            # (帅基础价值 10000 远大于位置价值 0-30，阶段因子对评估结果影响可忽略，
            #  且"残局帅应出击 vs 开局帅应固守"方向相反，单方向加成会引入偏差)
            return MaterialTable.get_king_positional(col, row, color)
        return 0.0


# ==================== AI 搜索引擎 ====================

@dataclass
class SearchResult:
    """搜索结果"""
    move: Move
    score: float
    nodes_searched: int
    time_ms: float
    depth: int
    is_checkmate: bool = False


@dataclass
class TTEntry:
    score: float
    depth: int
    flag: str  # 'exact', 'lower', 'upper'
    best_move: Optional[Move] = None


class ChessAI:
    """中国象棋 AI
    
    使用 Minimax + Alpha-Beta 剪枝 + MTD(f) 搜索算法
    
    优化策略:
    1. Alpha-Beta 剪枝 + Null-Move 剪枝
    2. 着法排序 (MVV-LVA + Killer + History Heuristic)
    3. 置换表 (Zobrist 哈希键值)
    4. MTD(f) 零窗口搜索 (深度 ≥ 3)
    5. 迭代深化 (Iterative Deepening)
    6. 7类棋子独立位置价值表
    7. 静态清算搜索 (含将军场景全着法保护)
    """
    
    # 评估正向极值
    MATE_SCORE = 100000
    INFINITY = float('inf')
    # 清算搜索最大深度: 防止 perpetual check 导致无限递归
    MAX_QDEPTH = 8
    # Null-move reduction steps
    NULL_MOVE_REDUCTION = 2
    # MTD(f) 收敛最大迭代次数
    MTDF_MAX_ITERATIONS = 15
    
    def __init__(
        self,
        depth: int = 3,
        use_iterative_deepening: bool = True,
        max_time_ms: float = 5000,
        use_mtdf: bool = True,
    ):
        """初始化 AI
        
        Args:
            depth: 搜索深度 (默认为3层, 大约可思考 2-3 秒)
            use_iterative_deepening: 是否使用迭代深化
            max_time_ms: 最大思考时间(毫秒)
            use_mtdf: 是否使用 MTD(f) 搜索 (深度 >= 3 时生效)
        """
        self.depth = depth
        self.use_iterative_deepening = use_iterative_deepening
        self.max_time_ms = max_time_ms
        self.use_mtdf = use_mtdf
        
        self.evaluator = Evaluator()
        
        # 统计
        self.nodes_searched = 0
        self.max_depth_reached = 0
        self.search_time_ms = 0
        
        # 置换表 (Zobrist 哈希键值 + 深度)
        self._ttable: dict[tuple[int, int], TTEntry] = {}
        self._time_start = 0.0
        self._time_limit_ms = max_time_ms
        self._time_up = False
        self._history_heuristic: Dict[Move, int] = {}
        
        # Killer 着法 (每层最多2个)
        self._killer_moves: List[List[Move]] = [[] for _ in range(32)]

        # 搜索路径局面重复追踪 (Zobrist 哈希值 → 出现次数)
        self._search_rep_counts: Dict[int, int] = {}
        self._search_rep_threshold: int = 3
    
    def best_move(
        self, board: Board, turn: Color, depth: Optional[int] = None, max_time_ms: Optional[float] = None
    ) -> SearchResult:
        """计算最佳着法
        
        Args:
            board: 当前棋盘
            turn: AI 的颜色
            depth: 搜索深度 (None=使用默认深度)
            
        Returns:
            SearchResult 最佳着法
        """
        start_time = time.time()
        
        search_depth = depth if depth is not None else self.depth
        
        if max_time_ms is not None:
            self._time_limit_ms = max_time_ms
        else:
            self._time_limit_ms = self.max_time_ms

        _log("info", "ai_search_start",
             turn=turn.value,
             search_depth=search_depth,
             max_time_ms=self._time_limit_ms)
        
        # 重置统计
        self.nodes_searched = 0
        self.max_depth_reached = 0
        self._killer_moves = [[] for _ in range(32)]
        self._ttable = {}
        self._history_heuristic = {}
        self._pv_move = None
        self._time_start = start_time
        self._time_up = False

        # 重置局面重复追踪
        self._search_rep_counts = {}
        
        move_generator = MoveGenerator(board)
        win_checker = WinChecker(board)
        
        # 生成所有伪合法着法并过滤送将着法
        pseudo_moves = move_generator.generate_all_moves(turn)
        move_validator = MoveValidator(board)
        legal_moves = [m for m in pseudo_moves if not move_validator._is_self_check(m.to_move(), turn)]
        _log("debug", "ai_legal_moves_generated",
             pseudo_count=len(pseudo_moves),
             legal_count=len(legal_moves))
        
        if not legal_moves:
            # 无合法着法
            _log("warning", "ai_no_legal_moves",
                 turn=turn.value)
            return SearchResult(
                move=Move(0, 0, 0, 0),
                score=-self.MATE_SCORE,
                nodes_searched=0,
                time_ms=0,
                depth=0,
                is_checkmate=True,
            )
        
        # 迭代深化搜索 (含 MTD(f) 优化)
        best_result = None
        
        if self.use_iterative_deepening:
            prev_score = 0
            for d in range(1, search_depth + 1):
                # 深度 >= 3 且启用 MTD(f) 时，使用 MTD(f) 找分数 + 窄窗口确认
                if self.use_mtdf and d >= 3:
                    result = self._mtdf_search_at_depth(
                        board, turn, d, legal_moves, win_checker, start_time,
                        prev_score=prev_score,
                    )
                else:
                    result = self._search_at_depth(
                        board, turn, d, legal_moves, win_checker, start_time
                    )
                if result is not None:
                    best_result = result
                    self.max_depth_reached = d
                    prev_score = result.score
                    _log("debug", "ai_depth_complete",
                         depth=d,
                         best_score=result.score,
                         nodes=self.nodes_searched,
                         method="mtdf" if (self.use_mtdf and d >= 3) else "ab")
                    # 已找到将杀着法，无需继续加深搜索
                    if result.is_checkmate and abs(result.score) >= self.MATE_SCORE - 1000:
                        _log("info", "ai_checkmate_found_early_stop",
                             depth=d,
                             score=result.score)
                        break
                # 检查是否超时
                elapsed = (time.time() - start_time) * 1000
                if elapsed > self._time_limit_ms:
                    _log("debug", "ai_timeout_at_depth",
                         depth=d,
                         elapsed_ms=int(elapsed))
                    break
        else:
            best_result = self._search_at_depth(
                board, turn, search_depth, legal_moves, win_checker, start_time
            )
            self.max_depth_reached = search_depth
        
        if best_result is None:
            # 默认选择第一个着法
            _log("warning", "ai_search_fallback",
                 move_count=len(legal_moves))
            best_move = legal_moves[0].to_move()
            score = self.evaluator.evaluate(board, turn)
            best_result = SearchResult(
                move=best_move,
                score=score,
                nodes_searched=self.nodes_searched,
                time_ms=(time.time() - start_time) * 1000,
                depth=self.max_depth_reached,
            )
        
        self.search_time_ms = (time.time() - start_time) * 1000
        best_result.time_ms = self.search_time_ms
        best_result.nodes_searched = self.nodes_searched
        
        _log("info", "ai_search_complete",
             move_from=f"{chr(ord('a') + best_result.move.from_col)}{best_result.move.from_row + 1}",
             move_to=f"{chr(ord('a') + best_result.move.to_col)}{best_result.move.to_row + 1}",
             score=best_result.score,
             nodes_searched=best_result.nodes_searched,
             depth_reached=self.max_depth_reached,
             time_ms=int(best_result.time_ms),
             is_checkmate=best_result.is_checkmate)
        
        return best_result
    
    def _search_at_depth(
        self,
        board: Board,
        turn: Color,
        depth: int,
        legal_moves: List[LegalMove],
        win_checker: WinChecker,
        start_time: float,
    ) -> Optional[SearchResult]:
        """在指定深度搜索最佳着法
        
        Returns:
            SearchResult 或 None (如果超时)
        """
        opponent = Color.BLACK if turn == Color.RED else Color.RED
        
        # 排序着法
        sorted_moves = self._sort_moves(legal_moves, board, turn, depth)
        
        best_move = sorted_moves[0].to_move()
        best_score = -self.INFINITY
        best_is_checkmate = False
        
        for lm in sorted_moves:
            if self._is_time_up():
                break
            move = lm.to_move()
            captured = board.make_move(move)
            try:
                # 检查送将（己方帅是否暴露）- 非法着法跳过
                new_win_checker = WinChecker(board)
                if new_win_checker.is_king_exposed(turn):
                    continue

                # 检查是否将死对手
                game_over = new_win_checker.check_game_over(opponent)
                if game_over.is_over:
                    # 吃子获胜
                    self.nodes_searched += 1
                    _log("debug", "ai_checkmate_found",
                         depth=depth,
                         move=f"{chr(ord('a') + move.from_col)}{move.from_row + 1}"
                              f"{chr(ord('a') + move.to_col)}{move.to_row + 1}",
                         captured=captured)
                    return SearchResult(
                        move=move,
                        score=self.MATE_SCORE,
                        nodes_searched=self.nodes_searched,
                        time_ms=0,
                        depth=depth,
                        is_checkmate=True,
                    )

                # Alpha-Beta 搜索
                score = -self._negamax(
                    board,
                    opponent,
                    depth - 1,
                    -self.INFINITY,
                    self.INFINITY,
                    start_time,
                )
            finally:
                board.unmake_move(move, captured)
            
                self.nodes_searched += 1
            
            if score > best_score:
                best_score = score
                best_move = move
                if abs(score) >= self.MATE_SCORE - 1000:
                    best_is_checkmate = True
        
        return SearchResult(
            move=best_move,
            score=best_score,
            nodes_searched=self.nodes_searched,
            time_ms=0,
            depth=depth,
            is_checkmate=best_is_checkmate,
        )
    
    def _mtdf_search_at_depth(
        self,
        board: Board,
        turn: Color,
        depth: int,
        legal_moves: List[LegalMove],
        win_checker: WinChecker,
        start_time: float,
        prev_score: float = 0,
    ) -> Optional[SearchResult]:
        """MTD(f) 搜索: 零窗口收敛找到精确分数，再窄窗口搜索最佳着法
        
        MTD(f) 通过反复调用零窗口 Alpha-Beta [beta-1, beta] 来逼近真实值，
        通常比全窗口搜索减少 10-30% 节点访问量。
        
        Args:
            prev_score: 上一深度的分数，用作初始猜测
        
        Returns:
            SearchResult 或 None (超时)
        """
        opponent = Color.BLACK if turn == Color.RED else Color.RED

        # 1. 初始猜测 (利用上一深度结果)
        guess = prev_score if prev_score else self.evaluator.evaluate(board, turn)

        lower_bound = -self.INFINITY
        upper_bound = self.INFINITY

        _safe_int = lambda v, sentinel: int(v) if v != float('inf') and v != float('-inf') else sentinel

        _log("debug", "mtdf_start",
             depth=depth,
             initial_guess=_safe_int(guess, 0))

        iteration = 0
        while lower_bound < upper_bound and iteration < self.MTDF_MAX_ITERATIONS:
            if self._is_time_up():
                _log("debug", "mtdf_timeout",
                     iteration=iteration,
                     lower=_safe_int(lower_bound, -99999),
                     upper=_safe_int(upper_bound, 99999))
                break

            beta_window = guess + 1 if guess == lower_bound else guess

            # 零窗口搜索: [beta-1, beta]
            score = self._negamax(board, turn, depth, beta_window - 1, beta_window, start_time)

            if score < beta_window:
                upper_bound = score
            else:
                lower_bound = score

            guess = score
            iteration += 1

        _log("debug", "mtdf_converged",
             iterations=iteration,
             final_score=_safe_int(lower_bound, 0),
             lower=_safe_int(lower_bound, -99999),
             upper=_safe_int(upper_bound, 99999))

        # 2. 收敛后，用窄窗口搜索确认最佳着法
        # 使用 [score - 100, score + 100] 作为 aspiration window
        final_alpha = lower_bound - 100
        final_beta = upper_bound + 100

        sorted_moves = self._sort_moves(legal_moves, board, turn, depth)

        best_move_m = sorted_moves[0].to_move()
        best_score = -self.INFINITY
        best_is_checkmate = False

        for lm in sorted_moves:
            if self._is_time_up():
                break
            move = lm.to_move()
            captured = board.make_move(move)
            try:
                new_win_checker = WinChecker(board)
                if new_win_checker.is_king_exposed(turn):
                    continue

                game_over = new_win_checker.check_game_over(opponent)
                if game_over.is_over:
                    self.nodes_searched += 1
                    return SearchResult(
                        move=move, score=self.MATE_SCORE,
                        nodes_searched=self.nodes_searched, time_ms=0,
                        depth=depth, is_checkmate=True,
                    )

                score = -self._negamax(
                    board, opponent, depth - 1,
                    -final_beta, -final_alpha, start_time,
                )
            finally:
                board.unmake_move(move, captured)
            self.nodes_searched += 1

            if score > best_score:
                best_score = score
                best_move_m = move
                if abs(score) >= self.MATE_SCORE - 1000:
                    best_is_checkmate = True

                # 窗口调整: 如果超出预期范围，重新搜索
                if score >= final_beta:
                    final_beta = score + 100
                if score <= final_alpha:
                    final_alpha = score - 100

        if best_score <= -self.INFINITY + 1:
            return None

        return SearchResult(
            move=best_move_m,
            score=best_score,
            nodes_searched=self.nodes_searched,
            time_ms=0,
            depth=depth,
            is_checkmate=best_is_checkmate,
        )

    def _negamax(
        self,
        board: Board,
        turn: Color,
        depth: int,
        alpha: float,
        beta: float,
        start_time: float,
    ) -> float:
        """Negamax + Alpha-Beta 剪枝搜索"""
        # 检查深度或超时
        if depth <= 0:
            return self._quiescence(board, turn, alpha, beta, 0)

        if self._is_time_up():
            return alpha

        # Zobrist 哈希键值 (含局面 + 行棋方)
        zhash = ZobristHasher.compute_hash(board, turn)
        tt_key = (zhash, depth)
        tt_entry = self._ttable.get(tt_key)
        if tt_entry is not None:
            if tt_entry.depth >= depth:
                if tt_entry.best_move is not None:
                    self._pv_move = tt_entry.best_move
                if tt_entry.flag == "exact":
                    return tt_entry.score
                elif tt_entry.flag == "lower":
                    alpha = max(alpha, tt_entry.score)
                elif tt_entry.flag == "upper":
                    beta = min(beta, tt_entry.score)
                if alpha >= beta:
                    return tt_entry.score

        move_generator = MoveGenerator(board)
        win_checker = WinChecker(board)
        pseudo_moves = move_generator.generate_all_moves(turn)
        # 过滤送将着法
        move_validator = MoveValidator(board)
        legal_moves = [m for m in pseudo_moves if not move_validator._is_self_check(m.to_move(), turn)]
        opponent = Color.BLACK if turn == Color.RED else Color.RED

        # 无合法着法（所有着法均送将 → 被将死或困毙）
        if not legal_moves:
            if win_checker.is_king_exposed(turn):
                # 将死
                return -self.MATE_SCORE + (self.depth - depth)
            else:
                # 困毙
                return -self.MATE_SCORE // 2

        # 局面重复检测: Zobrist 哈希追踪 → 三次重复视为和棋
        rep_count = self._search_rep_counts.get(zhash, 0) + 1
        if rep_count >= self._search_rep_threshold:
            return 0.0

        self._search_rep_counts[zhash] = rep_count
        result = self.__negamax_body(
            board, turn, depth, alpha, beta, start_time,
            move_generator, win_checker, legal_moves, opponent, tt_key,
        )
        self._search_rep_counts[zhash] -= 1
        if self._search_rep_counts[zhash] <= 0:
            del self._search_rep_counts[zhash]
        return result

    def __negamax_body(
        self,
        board: Board,
        turn: Color,
        depth: int,
        alpha: float,
        beta: float,
        start_time: float,
        move_generator: MoveGenerator,
        win_checker: WinChecker,
        legal_moves: list,
        opponent: Color,
        tt_key: tuple,
    ) -> float:
        """Negamax 搜索体 (不含局面重复追踪的包装部分)。"""
        # Null-move 剪枝 (保守策略):
        # 仅在较大深度、非将军并且非明显残局时尝试。使用 R = NULL_MOVE_REDUCTION。
        try_null_move = False
        if depth >= 4:
            try_null_move = True
        if try_null_move:
            # 避免在将军或残局中使用 null-move
            if not win_checker.is_king_exposed(turn):
                # 简单判断是否为残局: 子力很少时禁用 null-move
                non_king_pieces = 0
                for r in range(BOARD_ROWS):
                    for c in range(BOARD_COLS):
                        p = board.get(c, r)
                        if p >= 0:
                            ptype = get_piece_type_from_piece(p)
                            if ptype != PieceType.KING:
                                non_king_pieces += 1
                # 如果子力较少(<=6)视作残局, 不使用 null-move
                if non_king_pieces > 6:
                    R = self.NULL_MOVE_REDUCTION
                    # 进行 reduced-depth null-move 搜索
                    null_depth = depth - 1 - R
                    if null_depth > 0:
                        score = -self._negamax(
                            board,
                            opponent,
                            null_depth,
                            -beta,
                            -beta + 1,
                            start_time,
                        )
                        if score >= beta:
                            return score

        # 排序着法
        sorted_moves = self._sort_moves(legal_moves, board, turn, depth)

        # Alpha-Beta 剪枝
        best_score = -self.INFINITY
        best_move = sorted_moves[0].to_move()

        alpha_orig = alpha
        for lm in sorted_moves:
            if self._is_time_up():
                break
            move = lm.to_move()
            captured = board.make_move(move)
            try:
                # 检查送将（己方帅是否暴露）- 非法着法跳过
                new_win_checker = WinChecker(board)
                if new_win_checker.is_king_exposed(turn):
                    continue

                # 检查将死
                game_over = new_win_checker.check_game_over(opponent)
                if game_over.is_over:
                    if game_over.winner == turn:
                        return self.MATE_SCORE - (self.depth - depth)
                    else:
                        pass

                score = -self._negamax(
                    board,
                    opponent,
                    depth - 1,
                    -beta,
                    -alpha,
                    start_time,
                )
            finally:
                board.unmake_move(move, captured)
            self.nodes_searched += 1

            if score > best_score:
                best_score = score
                best_move = move

            if best_score > alpha:
                alpha = best_score

            if alpha >= beta:
                # Beta 剪枝
                self._add_killer_move(depth, move)
                self._add_history_heuristic(depth, move)
                break

        self._store_transposition(tt_key, best_score, depth, alpha_orig, beta, best_move)
        # Defensive: if best_score is still -inf, all moves were skipped (all self-checks
        # or timed out). Log warning for debugging and return the evaluation instead.
        if best_score == -self.INFINITY:
            _log("warning", "ai_negamax_all_moves_filtered",
                 turn=turn.value,
                 depth=depth,
                 legal_moves_count=len(legal_moves),
                 sorted_moves_count=len(sorted_moves))
            return self.evaluator.evaluate(board, turn)
        return best_score

    def _quiescence(
        self,
        board: Board,
        turn: Color,
        alpha: float,
        beta: float,
        qdepth: int = 0,
    ) -> float:
        """静态清算搜索，扩展吃子及将军着法直到局面安静。

        关键优化:
        - 未被将军时: 扩展吃子着法 + 将军着法，防止地平线效应导致漏杀
        - 被将军时: 保留全部合法着法 (借鉴 vliang-cpp)，避免误判
        - qdepth 硬限制防止双方互相将军时无限递归
        """
        # 硬深度限制: 防止 perpetual check 导致的无限递归
        if qdepth >= self.MAX_QDEPTH:
            return self.evaluator.evaluate(board, turn)

        if self._is_time_up():
            return self.evaluator.evaluate(board, turn)

        stand_pat = self.evaluator.evaluate(board, turn)

        # 检查当前是否被将军
        win_checker = WinChecker(board)
        is_in_check = win_checker.is_king_exposed(turn)

        if not is_in_check:
            # 未被将军: 扩展吃子着法 + 将军着法
            # Delta cutoff
            MAX_CAPTURE_VALUE = 900.0
            if stand_pat + MAX_CAPTURE_VALUE < alpha:
                return alpha
            if stand_pat >= beta:
                return stand_pat
            if alpha < stand_pat:
                alpha = stand_pat

            search_moves = self._generate_quiescence_moves(board, turn)
            if not search_moves:
                return stand_pat
        else:
            # 被将军: 必须找到逃避着法，保留全部合法着法
            # 生成全部合法着法
            move_generator = MoveGenerator(board)
            pseudo_moves = move_generator.generate_all_moves(turn)
            move_validator = MoveValidator(board)
            search_moves = [m for m in pseudo_moves
                          if not move_validator._is_self_check(m.to_move(), turn)]
            if not search_moves:
                # 无逃避着法 → 被将死
                return -self.MATE_SCORE + 10

            # 排序: 吃子优先 + MVV-LVA
            search_moves = self._sort_moves(search_moves, board, turn, 0)

        for lm in search_moves:
            if self._is_time_up():
                break
            move = lm.to_move()
            captured = board.make_move(move)
            try:
                opponent = Color.BLACK if turn == Color.RED else Color.RED
                score = -self._quiescence(board, opponent, -beta, -alpha, qdepth + 1)
            finally:
                board.unmake_move(move, captured)
            self.nodes_searched += 1
            if score >= beta:
                return score
            if score > alpha:
                alpha = score

        return alpha

    def _generate_capture_moves(self, board: Board, color: Color) -> List[LegalMove]:
        """生成所有吃子着法，按 MVV-LVA 排序。"""
        generator = MoveGenerator(board)
        moves = generator.generate_all_moves(color)
        capture_moves = [m for m in moves if m.captured >= 0]
        return sorted(
            capture_moves,
            key=lambda m: (
                self.evaluator._get_base_value(PieceType(m.captured % 10)) -
                self.evaluator._get_base_value(PieceType(m.piece % 10)) * 0.5,
                0,
            ),
            reverse=True,
        )

    @staticmethod
    def _could_check(
        piece_type: PieceType,
        to_col: int, to_row: int,
        king_col: int, king_row: int,
    ) -> bool:
        """快速启发式: 移动到的目标位置是否可能将军？

        基于棋子类型与目标位置的几何关系做 O(1) 预判。
        允许假阳性但杜绝假阴性，漏判会导致漏杀。

        Args:
            piece_type: 移动棋子的类型
            to_col, to_row: 棋子目标位置
            king_col, king_row: 对方将/帅位置
        """
        if piece_type == PieceType.ROOK or piece_type == PieceType.CANNON:
            return to_col == king_col or to_row == king_row
        elif piece_type == PieceType.KNIGHT:
            dc = abs(to_col - king_col)
            dr = abs(to_row - king_row)
            return (dc == 2 and dr == 1) or (dc == 1 and dr == 2)
        elif piece_type == PieceType.PAWN:
            return abs(to_col - king_col) + abs(to_row - king_row) <= 1
        elif piece_type == PieceType.KING:
            return to_col == king_col
        else:
            return abs(to_col - king_col) + abs(to_row - king_row) <= 1

    @staticmethod
    def _is_king_attacked_by(
        board: Board,
        attacker_color: Color,
        king_col: int,
        king_row: int,
    ) -> bool:
        """检查 (king_col,king_row) 处的将/帅是否被 attacker_color 方攻击。

        关键优化: 只检查攻击方己方棋子能否攻击将/帅，使用
        MoveGenerator.can_attack 定向检测，避免全盘扫描和全量着法生成。

        复杂度: O(攻击方棋子数 × 路径长度) ≈ O(己方棋子) << O(90+对方着法)

        Args:
            board: 当前棋盘 (make_move 之后的状态)
            attacker_color: 攻击方颜色 (刚走完棋的一方)
            king_col, king_row: 被攻击方将/帅位置

        Returns:
            True 表示 king 被攻击
        """
        gen = MoveGenerator(board)

        # 1) 检查攻击方所有棋子能否直接攻击将/帅
        attacker_pieces = board.get_all_pieces(attacker_color)
        for col, row, _ in attacker_pieces:
            if gen.can_attack(col, row, king_col, king_row):
                return True

        # 2) 飞将检测: 双方将帅同列且中间无棋子
        opponent = Color.BLACK if attacker_color == Color.RED else Color.RED
        attacker_king_pos = board.find_king(attacker_color)
        opponent_king_pos = board.find_king(opponent)
        if attacker_king_pos is not None and opponent_king_pos is not None:
            ak_col, ak_row = attacker_king_pos
            ok_col, ok_row = opponent_king_pos
            if ak_col == ok_col:
                min_r, max_r = min(ak_row, ok_row), max(ak_row, ok_row)
                blocked = any(
                    board.get(ak_col, r) >= 0
                    for r in range(min_r + 1, max_r)
                )
                if not blocked:
                    return True

        return False

    def _generate_quiescence_moves(self, board: Board, color: Color) -> List[LegalMove]:
        """生成清算搜索的候选着法：吃子着法 + 将军着法。

        防止地平线效应: 仅扩展吃子着法会漏掉非吃子的将军威胁。
        通过包含将军着法，引擎能在清算搜索中看到更深层的杀棋威胁。

        性能优化:
        - _could_check 预筛: O(1) 排除明显不可将军的着法
        - _is_king_attacked_by: 仅查己方棋子，O(己方棋子) 替代 O(全盘)
          的 is_king_exposed，消除每节点 O(n²) 开销
        """
        generator = MoveGenerator(board)
        moves = generator.generate_all_moves(color)
        opponent = Color.BLACK if color == Color.RED else Color.RED

        # 预取对方将/帅位置用于筛选
        opponent_king = board.find_king(opponent)

        result: List[LegalMove] = []
        for m in moves:
            if m.captured >= 0:
                # 吃子着法: 高优先级
                result.append(m)
            elif opponent_king is not None:
                piece_type = PieceType(m.piece % 10)
                if not self._could_check(
                    piece_type, m.to_col, m.to_row,
                    opponent_king[0], opponent_king[1],
                ):
                    continue
                move = m.to_move()
                captured = board.make_move(move)
                try:
                    gives_check = self._is_king_attacked_by(
                        board, color, opponent_king[0], opponent_king[1],
                    )
                finally:
                    board.unmake_move(move, captured)
                if gives_check:
                    result.append(m)

        # 排序: 吃子按 MVV-LVA，将军着法排后面
        return sorted(
            result,
            key=lambda m: (
                self.evaluator._get_base_value(PieceType(m.captured % 10))
                if m.captured >= 0
                else 0,
            ),
            reverse=True,
        )

    def _store_transposition(
        self,
        key: tuple,
        score: float,
        depth: int,
        alpha: float,
        beta: float,
        best_move: Move,
    ) -> None:
        if self._is_time_up():
            return
        if score <= alpha:
            flag = "upper"
        elif score >= beta:
            flag = "lower"
        else:
            flag = "exact"
        self._ttable[key] = TTEntry(score=score, depth=depth, flag=flag, best_move=best_move)

    def _is_time_up(self) -> bool:
        if self._time_limit_ms <= 0:
            return False
        elapsed = (time.time() - self._time_start) * 1000
        if elapsed > self._time_limit_ms:
            self._time_up = True
        return self._time_up

    def _add_history_heuristic(self, depth: int, move: Move) -> None:
        self._history_heuristic[move] = self._history_heuristic.get(move, 0) + depth * depth

    def _is_bad_opening_exchange(self, move: LegalMove, turn: Color) -> bool:
        if move.captured < 0:
            return False
        moving_type = PieceType(move.piece % 10)
        captured_type = PieceType(move.captured % 10)
        if moving_type != PieceType.CANNON or captured_type != PieceType.KNIGHT:
            return False
        if turn == Color.RED and move.to_row == 0 and move.to_col in (1, 7):
            return True
        if turn == Color.BLACK and move.to_row == BOARD_ROWS - 1 and move.to_col in (1, 7):
            return True
        return False
    
    def _sort_moves(
        self, moves: List[LegalMove], board: Board, turn: Color, depth: int
    ) -> List[LegalMove]:
        """着法排序 (Move Ordering)
        
        优先顺序:
        1. 将军着法（最高优先级，确保杀着优先评估）
        2. 吃子着法 (按吃子价值排序)
        3. Killer 着法 / PV 着法
        4. 历史启发性着法
        """
        opponent = Color.BLACK if turn == Color.RED else Color.RED

        # 预计算哪些着法是将军着法（使用克隆棋盘避免影响搜索状态）
        check_moves: Dict[Tuple[int, int, int, int], bool] = {}
        temp_board = board.clone()
        temp_wc = WinChecker(temp_board)
        for m in moves:
            captured = temp_board.make_move(m.to_move())
            try:
                gives_check = temp_wc.is_king_exposed(opponent)
                check_moves[(m.from_col, m.from_row, m.to_col, m.to_row)] = gives_check
            finally:
                temp_board.unmake_move(m.to_move(), captured)

        def move_priority(m: LegalMove) -> Tuple[int, int]:
            priority = 0
            move_key = (m.from_col, m.from_row, m.to_col, m.to_row)

            # 将军着法最高优先级
            if check_moves.get(move_key, False):
                priority += 30000

            # 吃子着法优先
            if m.captured >= 0:
                captured_value = self.evaluator._get_base_value(
                    PieceType(m.captured % 10)
                )
                moving_value = self.evaluator._get_base_value(
                    PieceType(m.piece % 10)
                )
                # MVV-LVA: 吃大子优先
                priority += int(captured_value - moving_value * 0.5 + 10000)
                if self._is_bad_opening_exchange(m, turn):
                    priority -= 6000
            else:
                # PV 着法优先
                if self._pv_move is not None and m.to_move() == self._pv_move:
                    priority += 20000
                # Killer 着法
                for km in self._killer_moves[depth]:
                    if km.from_col == m.from_col and km.from_row == m.from_row:
                        priority = max(priority, 5000)
                        break
                priority += self._history_heuristic.get(m.to_move(), 0)

            return (priority, 0)

        return sorted(moves, key=move_priority, reverse=True)
    
    def _add_killer_move(self, depth: int, move: Move) -> None:
        """添加 Killer 着法"""
        if 0 <= depth < len(self._killer_moves):
            killers = self._killer_moves[depth]
            if len(killers) < 2:
                if not any(
                    km.from_col == move.from_col and km.from_row == move.from_row
                    for km in killers
                ):
                    killers.append(move)


# ==================== 便捷函数 ====================

def get_ai_move(
    board: Board,
    turn: Color,
    difficulty: Difficulty = Difficulty.MEDIUM,
    max_time_ms: float = 5000,
) -> Optional[Move]:
    """获取 AI 着法 (便捷函数)
    
    Args:
        board: 当前棋盘
        turn: AI 的颜色
        difficulty: AI 难度
        max_time_ms: 最大思考时间
        
    Returns:
        最佳着法
    """
    # 根据难度设置搜索深度
    depth_map = {
        Difficulty.EASY: 2,
        Difficulty.MEDIUM: 3,
        Difficulty.HARD: 4,
        Difficulty.EXPERT: 5,
        Difficulty.MASTER: 6,
    }
    
    depth = depth_map.get(difficulty, 3)
    if max_time_ms >= 5000 and difficulty in (
        Difficulty.HARD, Difficulty.EXPERT, Difficulty.MASTER
    ):
        depth += 1
    
    _log("info", "get_ai_move",
         difficulty=difficulty.value,
         depth=depth,
         max_time_ms=max_time_ms,
         turn=turn.value)
    
    ai = ChessAI(
        depth=depth,
        use_iterative_deepening=True,
        max_time_ms=max_time_ms,
    )
    
    result = ai.best_move(board, turn, depth=depth, max_time_ms=max_time_ms)
    
    _log("info", "get_ai_move_result",
         move=f"{chr(ord('a') + result.move.from_col)}{result.move.from_row + 1}"
              f"{chr(ord('a') + result.move.to_col)}{result.move.to_row + 1}",
         score=result.score,
         time_ms=int(result.time_ms),
         nodes=result.nodes_searched,
         is_checkmate=result.is_checkmate)
    
    return result.move
