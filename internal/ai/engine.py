"""AI 搜索引擎 - 基于 Minimax + Alpha-Beta 剪枝的传统象棋 AI."""
from dataclasses import dataclass
from typing import Optional, List, Tuple, Callable, Dict
import time
import copy
import logging

from shared.constants import (
    Color,
    PieceType,
    PIECE_EMPTY,
    PIECE_RED_KING, PIECE_RED_ADVISOR, PIECE_RED_BISHOP, PIECE_RED_KNIGHT,
    PIECE_RED_ROOK, PIECE_RED_CANNON, PIECE_RED_PAWN,
    PIECE_BLACK_KING, PIECE_BLACK_ADVISOR, PIECE_BLACK_BISHOP, PIECE_BLACK_KNIGHT,
    PIECE_BLACK_ROOK, PIECE_BLACK_CANNON, PIECE_BLACK_PAWN,
    BOARD_ROWS, BOARD_COLS,
    get_color_from_piece, get_piece_type_from_piece,
    Difficulty, DIFFICULTY_SIMULATIONS,
)
from shared.protocol import Move

from ..chess.piece import Board
from ..chess.move_generator import MoveGenerator, LegalMove
from ..chess.move_validator import MoveValidator
from ..chess.win_checker import WinChecker


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
    """
    
    # 基础价值 (绝对值)
    PIECE_VALUES: Dict[int, float] = {
        # 兵/卒: 未过河 100, 过河 150
        PIECE_RED_PAWN: 100,
        PIECE_BLACK_PAWN: 100,
        # 士/仕: 200
        PIECE_RED_ADVISOR: 200,
        PIECE_BLACK_ADVISOR: 200,
        # 象/相: 200 (不能过河)
        PIECE_RED_BISHOP: 200,
        PIECE_BLACK_BISHOP: 200,
        # 马: 400
        PIECE_RED_KNIGHT: 400,
        PIECE_BLACK_KNIGHT: 400,
        # 炮: 450
        PIECE_RED_CANNON: 450,
        PIECE_BLACK_CANNON: 450,
        # 车: 900
        PIECE_RED_ROOK: 900,
        PIECE_BLACK_ROOK: 900,
        # 将/帅: 10000 (无法直接吃, 吃子时已胜利)
        PIECE_RED_KING: 10000,
        PIECE_BLACK_KING: 00,
    }
    
    # 位置价值表 (兵/卒 - 红方视角)
    # 正数表示对红方有利的位置
    PAWN_POSITIONAL: List[List[int]] = [
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],
        [100, 100, 100, 100, 100, 100, 100, 100, 100],  # 过河兵 +100
        [  0,   0,  50,  80, 100,  80,  50,   0,   0],  # 河口兵 +50~100
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],
        [  0,   0,   0,   0,   0,   0,   0,   0,   0],
    ]
    
    # 位置价值表 (黑方视角, 即红方的镜像)
    @classmethod
    def get_pawn_positional(cls, col: int, row: int, color: Color) -> float:
        """获取兵/卒的位置价值
        
        Args:
            col, row: 棋子位置
            color: 棋子颜色
            
        Returns:
            位置价值
        """
        if color == Color.RED:
            return float(cls.PAWN_POSITIONAL[row][col])
        else:
            # 黑方视角, row 翻转
            return float(cls.PAWN_POSITIONAL[BOARD_ROWS - 1 - row][col])
    
    # 车/炮位置价值
    ROOK_POSITIONAL: List[List[int]] = [
        [14, 14, 12, 18, 16, 18, 12, 14, 14],
        [16, 20, 18, 24, 26, 24, 18, 20, 16],
        [12, 12, 12, 18, 18, 18, 12, 12, 12],
        [12, 18, 16, 22, 22, 22, 16, 18, 12],
        [12, 14, 12, 18, 18, 18, 12, 14, 12],
        [12, 16, 14, 20, 20, 20, 14, 16, 12],
        [ 6, 10,  8, 14, 14, 14,  8, 10,  6],
        [ 4,  8,  6, 14, 12, 14,  6,  8,  4],
        [ 8,  4,  8, 16,  8, 16,  8,  4,  8],
        [ 0,  0, -2,  8,  6,  8, -2,  0,  0],
    ]
    
    @classmethod
    def get_rook_positional(cls, col: int, row: int, color: Color) -> float:
        """获取车/炮的位置价值
        
        表中 row=0 为黑方底线 (row 0), row=9 为红方底线 (row 9)。
        - 黑方视角: table[row]
        - 红方视角: table[BOARD_ROWS-1-row]
        """
        if color == Color.RED:
            idx = BOARD_ROWS - 1 - row
        else:
            idx = row
        return float(cls.ROOK_POSITIONAL[idx][col])
    
    # 马位置价值 (10行，与棋盘一一对应)
    KNIGHT_POSITIONAL: List[List[int]] = [
        [-8, -6, -8, -6, -4, -6, -8, -6, -8],  # row 0 = 黑方底线
        [-4,  4,  0,  2,  4,  2,  0,  4, -4],  # row 1
        [-2,  0,  2,  4,  4,  4,  2,  0, -2],  # row 2 (补充完整)
        [-4,  2,  6,  8, 10,  8,  6,  2, -4],  # row 3
        [-4,  4,  8, 12, 12, 12,  8,  4, -4],  # row 4
        [-4,  6,  8, 10, 12, 10,  8,  6, -4],  # row 5
        [-4,  6,  6,  8,  8,  8,  6,  6, -4],  # row 6
        [-6, -4,  4,  6,  4,  6,  4, -4, -6],  # row 7
        [-8,-10, -4, -2, -4, -2, -4,-10, -8],  # row 8
        [-10, -8, -6, -4, -8, -4, -6, -8,-10],  # row 9 = 红方底线
    ]
    
    @classmethod
    def get_knight_positional(cls, col: int, row: int, color: Color) -> float:
        """获取马的位置价值
        
        表中 row=0 为黑方底线 (row 0), row=9 为红方底线 (row 9)。
        - 黑方视角: table[row]
        - 红方视角: table[BOARD_ROWS-1-row]
        """
        if color == Color.RED:
            idx = BOARD_ROWS - 1 - row  # row 9 → idx 0
        else:
            idx = row  # row 0 → idx 0
        return float(cls.KNIGHT_POSITIONAL[idx][col])


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
        
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                piece = board.get(col, row)
                if piece < 0:
                    continue
                
                color = get_color_from_piece(piece)
                ptype = get_piece_type_from_piece(piece)
                
                # 基础价值
                base = self._get_base_value(ptype)
                
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
        """获取棋子位置价值"""
        if ptype == PieceType.PAWN:
            return MaterialTable.get_pawn_positional(col, row, color)
        elif ptype in (PieceType.ROOK, PieceType.CANNON):
            return MaterialTable.get_rook_positional(col, row, color) * 0.5
        elif ptype == PieceType.KNIGHT:
            return MaterialTable.get_knight_positional(col, row, color)
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


class ChessAI:
    """中国象棋 AI
    
    使用 Minimax + Alpha-Beta 剪枝搜索算法
    
    优化策略:
    1. Alpha-Beta 剪枝
    2. 着法排序 (优先搜索吃子着法)
    3. 置换表 (可选)
    4. Killer 着法启发
    5. 迭代深化 (Iterative Deepening)
    """
    
    # 评估正向极值
    MATE_SCORE = 100000
    INFINITY = float('inf')
    
    def __init__(
        self,
        depth: int = 3,
        use_iterative_deepening: bool = True,
        max_time_ms: float = 5000,
    ):
        """初始化 AI
        
        Args:
            depth: 搜索深度 (默认为3层, 大约可思考 2-3 秒)
            use_iterative_deepening: 是否使用迭代深化
            max_time_ms: 最大思考时间(毫秒)
        """
        self.depth = depth
        self.use_iterative_deepening = use_iterative_deepening
        self.max_time_ms = max_time_ms
        
        self.evaluator = Evaluator()
        
        # 统计
        self.nodes_searched = 0
        self.max_depth_reached = 0
        self.search_time_ms = 0
        
        # 置换表 (可选, 简单实现)
        self._ttable: Dict[int, Tuple[float, int, Move]] = {}  # hash -> (score, depth, best_move)
        
        # Killer 着法 (每层最多2个)
        self._killer_moves: List[List[Move]] = [[] for _ in range(32)]
    
    def best_move(
        self, board: Board, turn: Color, depth: Optional[int] = None
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
        
        _log("info", "ai_search_start",
             turn=turn.value,
             search_depth=search_depth,
             max_time_ms=self.max_time_ms)
        
        # 重置统计
        self.nodes_searched = 0
        self.max_depth_reached = 0
        self._killer_moves = [[] for _ in range(32)]
        
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
        
        # 迭代深化搜索
        best_result = None
        
        if self.use_iterative_deepening:
            for d in range(1, search_depth + 1):
                result = self._search_at_depth(
                    board, turn, d, legal_moves, win_checker, start_time
                )
                if result is not None:
                    best_result = result
                    self.max_depth_reached = d
                    _log("debug", "ai_depth_complete",
                         depth=d,
                         best_score=result.score,
                         nodes=self.nodes_searched)
                
                # 检查是否超时
                elapsed = (time.time() - start_time) * 1000
                if elapsed > self.max_time_ms:
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
        sorted_moves = self._sort_moves(legal_moves, board, turn)
        
        best_move = sorted_moves[0].to_move()
        best_score = -self.INFINITY
        best_is_checkmate = False
        
        for lm in sorted_moves:
            move = lm.to_move()
            
            # 检查是否超时
            elapsed = (time.time() - start_time) * 1000
            if elapsed > self.max_time_ms:
                _log("debug", "ai_timeout_in_search",
                     depth=depth,
                     elapsed_ms=int(elapsed))
                return None
            
            # 模拟着法
            new_board = board.clone()
            piece = new_board.get(move.from_col, move.from_row)
            captured = new_board.get(move.to_col, move.to_row)
            new_board.set(move.to_col, move.to_row, piece)
            new_board.set(move.from_col, move.from_row, PIECE_EMPTY)
            
            # 检查送将（己方帅是否暴露）- 非法着法跳过
            new_win_checker = WinChecker(new_board)
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
                new_board,
                opponent,
                depth - 1,
                -self.INFINITY,
                self.INFINITY,
                start_time,
            )
            
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
    
    def _negamax(
        self,
        board: Board,
        turn: Color,
        depth: int,
        alpha: float,
        beta: float,
        start_time: float,
    ) -> float:
        """Negamax + Alpha-Beta 剪枝搜索
        
        简化版: 不使用置换表
        """
        # 检查深度或超时
        if depth <= 0:
            return self.evaluator.evaluate(board, turn)
        
        elapsed = (time.time() - start_time) * 1000
        if elapsed > self.max_time_ms:
            return 0  # 超时, 返回当前评估
        
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
        
        # 局面重复检测 (简化: 深度限制)
        if depth >= 4:
            # 简单重复检测
            pass
        
        # 排序着法
        sorted_moves = self._sort_moves(legal_moves, board, turn)
        
        # Alpha-Beta 剪枝
        best_score = -self.INFINITY
        
        for lm in sorted_moves:
            move = lm.to_move()
            
            # 模拟着法
            new_board = board.clone()
            piece = new_board.get(move.from_col, move.from_row)
            captured = new_board.get(move.to_col, move.to_row)
            new_board.set(move.to_col, move.to_row, piece)
            new_board.set(move.from_col, move.from_row, PIECE_EMPTY)
            
            # 检查送将（己方帅是否暴露）- 非法着法跳过
            new_win_checker = WinChecker(new_board)
            if new_win_checker.is_king_exposed(turn):
                continue
            
            # 检查将死
            game_over = new_win_checker.check_game_over(opponent)
            
            if game_over.is_over:
                if game_over.winner == turn:
                    return self.MATE_SCORE - (self.depth - depth)
                else:
                    # 对手将死
                    pass
            
            score = -self._negamax(
                new_board,
                opponent,
                depth - 1,
                -beta,
                -alpha,
                start_time,
            )
            
            self.nodes_searched += 1
            
            if score > best_score:
                best_score = score
            
            if best_score > alpha:
                alpha = best_score
            
            if alpha >= beta:
                # Beta 剪枝
                # 记录 Killer 着法
                self._add_killer_move(depth, move)
                break
        
        return best_score
    
    def _sort_moves(
        self, moves: List[LegalMove], board: Board, turn: Color
    ) -> List[LegalMove]:
        """着法排序 (Move Ordering)
        
        优先顺序:
        1. 吃子着法 (按吃子价值排序)
        2. Killer 着法
        3. 其他着法
        """
        def move_priority(m: LegalMove) -> Tuple[int, int]:
            priority = 0
            
            # 吃子着法优先
            if m.captured >= 0:
                captured_value = self.evaluator._get_base_value(
                    PieceType(m.captured % 10)
                )
                moving_value = self.evaluator._get_base_value(
                    PieceType(m.piece % 10)
                )
                # MVV-LVA: 吃大子优先
                priority = int(captured_value - moving_value * 0.5 + 10000)
            else:
                # Killer 着法
                for km in self._killer_moves[self.max_depth_reached]:
                    if km.from_col == m.from_col and km.from_row == m.from_row:
                        priority = 5000
                        break
            
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
    
    result = ai.best_move(board, turn)
    
    _log("info", "get_ai_move_result",
         move=f"{chr(ord('a') + result.move.from_col)}{result.move.from_row + 1}"
              f"{chr(ord('a') + result.move.to_col)}{result.move.to_row + 1}",
         score=result.score,
         time_ms=int(result.time_ms),
         nodes=result.nodes_searched,
         is_checkmate=result.is_checkmate)
    
    return result.move
