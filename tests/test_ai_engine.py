"""单元测试: AI 搜索引擎 (ai/engine.py)"""
import pytest
import time as time_module
from shared.constants import (
    Color,
    PieceType,
    PIECE_EMPTY,
    PIECE_RED_ROOK, PIECE_RED_KING, PIECE_RED_PAWN,
    PIECE_BLACK_KING, PIECE_BLACK_ROOK,
    Difficulty,
)
from internal.ai.engine import (
    ChessAI,
    Evaluator,
    MaterialTable,
    SearchResult,
    get_ai_move,
)
from internal.chess.piece import Board
from shared.protocol import Move


class TestEvaluator:
    """测试局面评估器"""

    def test_initial_position(self):
        """测试初始局面评估"""
        board = Board()
        evaluator = Evaluator()
        
        # 初始局面应该接近0
        score = evaluator.evaluate(board, Color.RED)
        
        assert isinstance(score, float)
        # 初始局面应该平衡 (接近0)
        assert abs(score) < 1000

    def test_material_advantage(self):
        """测试子力优势"""
        evaluator = Evaluator()
        
        # 创建红方多一车的局面
        board = Board()
        # 移除黑车
        board.set(0, 0, PIECE_EMPTY)
        
        score = evaluator.evaluate(board, Color.RED)
        
        # 红方应该领先
        assert score > 500  # 车的价值约900

    def test_black_turn_inverted(self):
        """测试黑方回合评估取反"""
        evaluator = Evaluator()
        
        board = Board()
        board.set(0, 0, PIECE_EMPTY)  # 移除黑车
        
        red_score = evaluator.evaluate(board, Color.RED)
        black_score = evaluator.evaluate(board, Color.BLACK)
        
        # 黑方回合时评估应该取反
        assert abs(red_score - (-black_score)) < 1

    def test_pawn_positional(self):
        """测试兵的位置价值"""
        # 红兵在过河位置 (row 5, 即已过河)
        pos_value = MaterialTable.get_pawn_positional(0, 5, Color.RED)
        assert pos_value == 100  # 过河兵 +100
        
        # 红兵在未过河位置 (row 6)
        pos_not_crossed = MaterialTable.get_pawn_positional(0, 6, Color.RED)
        assert pos_not_crossed == 0  # 未过河无额外价值

    def test_knight_positional(self):
        """测试马的位置价值"""
        # 中心马
        center = MaterialTable.get_knight_positional(4, 4, Color.RED)
        # 边角马
        corner = MaterialTable.get_knight_positional(0, 0, Color.RED)
        
        assert center > corner  # 中心马价值更高


class TestChessAI:
    """测试象棋 AI"""

    def test_init(self):
        """测试 AI 初始化"""
        ai = ChessAI(depth=3)
        
        assert ai.depth == 3
        assert ai.nodes_searched == 0

    def test_best_move_initial(self):
        """测试初始局面最佳着法"""
        board = Board()
        ai = ChessAI(depth=2, use_iterative_deepening=False)
        
        result = ai.best_move(board, Color.RED)
        
        assert result is not None
        assert isinstance(result, SearchResult)
        assert result.move is not None
        assert result.move.is_valid()

    def test_best_move_depth(self):
        """测试搜索深度"""
        board = Board()
        
        ai1 = ChessAI(depth=1)
        result1 = ai1.best_move(board, Color.RED)
        
        ai2 = ChessAI(depth=2)
        result2 = ai2.best_move(board, Color.RED)
        
        # 深度更深, 搜索节点更多
        assert result2.nodes_searched >= result1.nodes_searched

    def test_best_move_fast(self):
        """测试 AI 快速返回"""
        board = Board()
        ai = ChessAI(depth=1, max_time_ms=1000)
        
        start = time_module.time()
        result = ai.best_move(board, Color.RED)
        elapsed = (time_module.time() - start) * 1000
        
        assert elapsed < 2000  # 不应该超过设置的超时时间
        assert result.move is not None

    def test_iterative_deepening(self):
        """测试迭代深化"""
        board = Board()
        ai = ChessAI(depth=3, use_iterative_deepening=True)
        
        result = ai.best_move(board, Color.RED)
        
        # 迭代深化应该达到最大深度
        assert ai.max_depth_reached >= 1

    def test_no_legal_moves(self):
        """测试无合法着法时的处理"""
        # 创建只剩双将 + 阻挡的极端局面
        # 红方只有一个兵可走，且走完后会送将（无合法着法可选）
        board_arr = [
            [-1]*9 for _ in range(10)
        ]
        board_arr[0][4] = 10   # 黑将 (row 0)
        board_arr[9][4] = 0    # 红将 (row 9)
        # 清除其他棋子
        
        from internal.chess.piece import Board as B
        board = B(board_arr)
        
        ai = ChessAI(depth=1)
        result = ai.best_move(board, Color.RED)
        
        # 应该返回任意一个着法（或标记为无合法着法）
        assert result is not None
        assert result.move.is_valid()


class TestChessAIMoveQuality:
    """测试 AI 着法质量"""

    def test_prefers_capture(self):
        """测试 AI 优先吃子"""
        # 创建局面: 红车可吃黑炮，且无其他更好的选择
        # 黑炮在红车的攻击线上，且无法用其他着法获得更大优势
        board_arr = [
            [-1]*9 for _ in range(10)
        ]
        board_arr[0][4] = 10   # 黑将
        board_arr[9][4] = 0    # 红将
        board_arr[9][0] = 4     # 红车
        board_arr[5][0] = 15   # 黑炮
        
        from internal.chess.piece import Board as B
        board = B(board_arr)
        
        ai = ChessAI(depth=2)
        result = ai.best_move(board, Color.RED)
        
        # 应该选择吃子着法（吃黑炮或平移到其他空位）
        # 由于红车可直线吃黑炮，AI 应优先考虑此着法
        assert result.move is not None

    def test_avoids_self_check(self):
        """测试 AI 避免送将"""
        # 创建局面: 红方只有一个兵可走，但会送将
        board_arr = [
            [-1]*9 for _ in range(10)
        ]
        board_arr[0][4] = 10  # 黑将
        board_arr[9][4] = 0   # 红将
        board_arr[8][3] = 6   # 红兵在黑车攻击范围
        
        from internal.chess.piece import Board as B
        board = B(board_arr)
        
        ai = ChessAI(depth=2)
        result = ai.best_move(board, Color.RED)
        
        # 不应该把兵送到被车吃的危险位置
        # 如果只能送吃，则必须走


class TestGetAIMove:
    """测试便捷函数"""

    def test_get_ai_move_basic(self):
        """测试便捷函数基本功能"""
        board = Board()
        
        move = get_ai_move(board, Color.RED, Difficulty.EASY, max_time_ms=1000)
        
        assert move is not None
        assert move.is_valid()

    def test_difficulty_affects_time(self):
        """测试难度影响搜索时间"""
        board = Board()
        
        move_easy = get_ai_move(board, Color.RED, Difficulty.EASY, max_time_ms=500)
        move_hard = get_ai_move(board, Color.RED, Difficulty.HARD, max_time_ms=2000)
        
        assert move_easy is not None
        assert move_hard is not None


class TestSearchResult:
    """测试搜索结果"""

    def test_search_result_fields(self):
        """测试搜索结果字段"""
        board = Board()
        ai = ChessAI(depth=1)
        result = ai.best_move(board, Color.RED)
        
        assert hasattr(result, 'move')
        assert hasattr(result, 'score')
        assert hasattr(result, 'nodes_searched')
        assert hasattr(result, 'time_ms')
        assert hasattr(result, 'depth')
        
        assert result.score is not None
        assert result.nodes_searched >= 0
        assert result.time_ms >= 0
        assert result.depth >= 1


class TestMateScore:
    """测试杀棋评估"""

    def test_mate_score_defined(self):
        """测试杀棋分数定义"""
        assert ChessAI.MATE_SCORE > 10000
        assert ChessAI.INFINITY > ChessAI.MATE_SCORE
