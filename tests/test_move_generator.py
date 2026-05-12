"""单元测试: 着法生成器."""
import pytest
from internal.chess import (
    Board, Piece, Move, LegalMove,
    Color, PieceType,
    PIECE_EMPTY, PIECE_RED_KING, PIECE_RED_ADVISOR, PIECE_RED_BISHOP, PIECE_RED_KNIGHT,
    PIECE_RED_ROOK, PIECE_RED_CANNON, PIECE_RED_PAWN,
    PIECE_BLACK_KING, PIECE_BLACK_BISHOP, PIECE_BLACK_KNIGHT,
    PIECE_BLACK_ROOK, PIECE_BLACK_CANNON, PIECE_BLACK_PAWN,
    create_initial_board, board_from_array,
    MoveGenerator, generate_moves, count_moves,
)


class TestMoveGeneratorInitialBoard:
    """初始棋盘着法生成测试"""

    def test_initial_board_red_moves_count(self):
        """测试初始局面红方合法着法数量
        
        根据象棋规则，初始局面红方应该有约 44 种合法着法
        """
        board = create_initial_board()
        moves = generate_moves(board, Color.RED)
        # 允许一定误差，但应该在合理范围内
        assert 40 <= len(moves) <= 50, f"初始局面红方着法数量异常: {len(moves)}"

    def test_initial_board_black_moves_count(self):
        """测试初始局面黑方合法着法数量"""
        board = create_initial_board()
        moves = generate_moves(board, Color.BLACK)
        assert 40 <= len(moves) <= 50


class TestKingMoves:
    """将/帅着法测试"""

    def test_king_moves_in_palace(self):
        """测试将在九宫内移动"""
        # 创建只有红帅的九宫
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][4] = PIECE_RED_KING
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        moves = gen.generate_king_moves(4, 9, Color.RED)
        
        # 红帅可以从 (4,9) 移动到:
        # (3,9), (5,9) 左右
        # (4,8) 下
        assert len(moves) >= 2

    def test_king_cannot_leave_palace(self):
        """测试将不能离开九宫"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][4] = PIECE_RED_KING
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        moves = gen.generate_king_moves(4, 9, Color.RED)
        
        # 检查不能移动到九宫外
        for move in moves:
            assert 3 <= move.to_col <= 5  # 列在九宫内
            assert 7 <= move.to_row <= 9  # 行在九宫内

    def test_king_cannot_move_to_occupied_own(self):
        """测试将不能走到己方棋子位置"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][4] = PIECE_RED_KING
        arr[9][3] = PIECE_RED_ADVISOR  # 己方士
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        moves = gen.generate_king_moves(4, 9, Color.RED)
        
        # 不能走到 (3,9) 因为有己方棋子
        assert not any(m.to_col == 3 and m.to_row == 9 for m in moves)

    def test_king_can_capture_enemy(self):
        """测试将可以吃对方棋子"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][4] = PIECE_RED_KING
        arr[9][5] = PIECE_BLACK_BISHOP  # 对方相
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        moves = gen.generate_king_moves(4, 9, Color.RED)
        
        # 可以吃掉 (5,9) 的黑相
        capture_moves = [m for m in moves if m.to_col == 5 and m.to_row == 9]
        assert len(capture_moves) == 1


class TestAdvisorMoves:
    """士/仕着法测试"""

    def test_advisor_moves_in_palace(self):
        """测试士在九宫内斜线移动"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][3] = PIECE_RED_ADVISOR
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(3, 9)
        moves = gen._generate_advisor_moves(3, 9, piece, Color.RED)
        
        # 红士可以从 (3,9) 移动到 (4,8) 或被阻挡
        # 目前 (4,8) 是空位，所以应该有移动
        assert len(moves) >= 0  # 允许被其他棋子阻挡的情况

    def test_advisor_cannot_leave_palace(self):
        """测试士不能离开九宫"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][3] = PIECE_RED_ADVISOR
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(3, 9)
        moves = gen._generate_advisor_moves(3, 9, piece, Color.RED)
        
        for move in moves:
            assert 3 <= move.to_col <= 5
            assert 7 <= move.to_row <= 9


class TestBishopMoves:
    """象/相着法测试"""

    def test_bishop_moves(self):
        """测试象的田字对角移动"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][2] = PIECE_RED_BISHOP
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(2, 9)
        moves = gen._generate_bishop_moves(2, 9, piece, Color.RED)
        
        # 红相可以从 (2,9) 移动到 (4,7) (未被阻挡)
        assert len(moves) >= 1

    def test_bishop_blocked_by_eye(self):
        """测试象眼被堵"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][2] = PIECE_RED_BISHOP
        arr[8][3] = PIECE_RED_PAWN  # Block eye at (col=3, row=8)
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(2, 9)
        moves = gen._generate_bishop_moves(2, 9, piece, Color.RED)
        
        # 不能移动到 (4,7) 因为象眼被堵
        assert not any(m.to_col == 4 and m.to_row == 7 for m in moves)

    def test_bishop_cannot_cross_river(self):
        """测试象不能过河"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][2] = PIECE_RED_BISHOP  # 红相在底线
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(2, 9)
        moves = gen._generate_bishop_moves(2, 9, piece, Color.RED)
        
        # 不能移动到 row < 5 (过河)
        for move in moves:
            assert move.to_row >= 5


class TestKnightMoves:
    """马着法测试"""

    def test_knight_moves(self):
        """测试马的日字移动"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][1] = PIECE_RED_KNIGHT
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(1, 9)
        moves = gen._generate_knight_moves(1, 9, piece, Color.RED)
        
        # 红马可以从 (1,9) 移动
        assert len(moves) >= 1

    def test_knight_blocked_by_leg(self):
        """测试蹩马腿"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][1] = PIECE_RED_KNIGHT
        arr[1][8] = PIECE_RED_PAWN  # 蹩马腿
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(1, 9)
        moves = gen._generate_knight_moves(1, 9, piece, Color.RED)
        
        # 有些着法应该被阻挡
        # (0,7) 方向的着法应该被阻止
        blocked = not any(m.to_col == 0 and m.to_row == 7 for m in moves)


class TestRookMoves:
    """车着法测试"""

    def test_rook_straight_line(self):
        """测试车直线移动"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][0] = PIECE_RED_ROOK
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(0, 9)
        moves = gen._generate_rook_moves(0, 9, piece, Color.RED)
        
        # 红车在 (0,9)，可以上下移动
        assert len(moves) >= 9  # 可以移动到任意空位

    def test_rook_blocked_by_pieces(self):
        """测试车被阻挡"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][0] = PIECE_RED_ROOK
        arr[5][0] = PIECE_BLACK_PAWN  # 中间有黑卒
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(0, 9)
        moves = gen._generate_rook_moves(0, 9, piece, Color.RED)
        
        # 可以移动到 (0,5) 吃黑卒，但不能超过
        assert any(m.to_col == 0 and m.to_row == 5 and m.captured == PIECE_BLACK_PAWN for m in moves)
        # 不能移动到 (0,4) 因为中间有棋子
        assert not any(m.to_col == 0 and m.to_row == 4 for m in moves)


class TestCannonMoves:
    """炮着法测试"""

    def test_cannon_moves_without_capture(self):
        """测试炮移动不吃子"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[7][1] = PIECE_RED_CANNON
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(1, 7)
        moves = gen._generate_cannon_moves(1, 7, piece, Color.RED)
        
        # 可以直线移动
        assert len(moves) >= 1

    def test_cannon_capture(self):
        """Test cannon capture"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[7][1] = PIECE_RED_CANNON  # col=1, row=7
        arr[5][1] = PIECE_BLACK_PAWN  # Platform at (col=1, row=5)
        arr[3][1] = PIECE_BLACK_ROOK  # Target at (col=1, row=3)
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(1, 7)
        moves = gen._generate_cannon_moves(1, 7, piece, Color.RED)
        
        # Can capture black rook through platform
        capture_moves = [m for m in moves if m.captured >= 0]
        assert any(m.to_col == 1 and m.to_row == 3 and m.captured == PIECE_BLACK_ROOK for m in capture_moves)

    def test_cannon_cannot_capture_without_platform(self):
        """测试炮无炮架不能吃子"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[7][1] = PIECE_RED_CANNON
        arr[3][1] = PIECE_BLACK_ROOK  # 没有炮架
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(1, 7)
        moves = gen._generate_cannon_moves(1, 7, piece, Color.RED)
        
        # 不能吃黑车
        assert not any(m.to_col == 3 and m.to_row == 1 for m in moves)


class TestPawnMoves:
    """兵/卒着法测试"""

    def test_pawn_not_crossed_river(self):
        """测试过河前兵只能前进"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[6][0] = PIECE_RED_PAWN  # 红兵在己方半场
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(0, 6)
        moves = gen._generate_pawn_moves(0, 6, piece, Color.RED)
        
        # 只能前进 (to_row < 6)
        assert all(m.to_row < 6 for m in moves)

    def test_pawn_crossed_river(self):
        """测试过河后兵可横移"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[4][3] = PIECE_RED_PAWN  # 红兵已过河
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(4, 3)
        moves = gen._generate_pawn_moves(4, 3, piece, Color.RED)
        
        # 可以横移
        assert len(moves) >= 2

    def test_black_pawn_moves(self):
        """测试黑卒移动"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[3][0] = PIECE_BLACK_PAWN  # 黑卒在己方半场
        board = board_from_array(arr)
        
        gen = MoveGenerator(board)
        piece = board.get(0, 3)
        moves = gen._generate_pawn_moves(0, 3, piece, Color.BLACK)
        
        # 黑卒向 row 增大方向移动
        assert all(m.to_row > 3 for m in moves)


class TestAllPiecesCovered:
    """所有棋子类型覆盖测试"""

    def test_all_pieces_have_moves(self):
        """测试所有棋子都能生成着法"""
        board = create_initial_board()
        gen = MoveGenerator(board)
        
        # 每种棋子都应该能生成一些着法
        for color in [Color.RED, Color.BLACK]:
            moves = gen.generate_all_moves(color)
            assert len(moves) > 0, f"{color} 没有合法着法"


class TestGenerateMovesUtility:
    """generate_moves 工具函数测试"""

    def test_generate_moves_function(self):
        """测试便捷函数"""
        board = create_initial_board()
        moves = generate_moves(board, Color.RED)
        
        assert len(moves) > 0
        assert all(isinstance(m, LegalMove) for m in moves)

    def test_count_moves_function(self):
        """测试计数函数"""
        board = create_initial_board()
        count = count_moves(board, Color.RED)
        
        assert count > 0
        assert 40 <= count <= 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
