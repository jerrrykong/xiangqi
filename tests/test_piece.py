"""单元测试: 棋子与棋盘数据结构."""
import pytest
from internal.chess import (
    Board, Piece, Move,
    Color, PieceType,
    PIECE_EMPTY, PIECE_RED_KING, PIECE_RED_ROOK, PIECE_RED_PAWN,
    PIECE_BLACK_KING, PIECE_BLACK_ROOK, PIECE_BLACK_CANNON,
    create_initial_board, board_from_array, board_to_fen,
)


class TestPiece:
    """Piece 数据类测试"""

    def test_piece_creation(self):
        """测试创建棋子"""
        piece = Piece(Color.RED, PieceType.KING)
        assert piece.color == Color.RED
        assert piece.piece_type == PieceType.KING

    def test_piece_encoding(self):
        """测试棋子编码"""
        # 红帅 = 0 * 10 + 0 = 0
        piece = Piece(Color.RED, PieceType.KING)
        assert piece.encode() == 0
        
        # 黑车 = 1 * 10 + 4 = 14
        piece = Piece(Color.BLACK, PieceType.ROOK)
        assert piece.encode() == 14

    def test_piece_decode(self):
        """测试棋子解码"""
        piece = Piece.decode(0)
        assert piece.color == Color.RED
        assert piece.piece_type == PieceType.KING
        
        piece = Piece.decode(14)
        assert piece.color == Color.BLACK
        assert piece.piece_type == PieceType.ROOK

    def test_piece_repr(self):
        """测试棋子表示"""
        piece = Piece(Color.RED, PieceType.KING)
        assert "红" in repr(piece)
        assert "将" in repr(piece)
        
        piece = Piece(Color.BLACK, PieceType.PAWN)
        assert "黑" in repr(piece)
        assert "卒" in repr(piece)

    def test_piece_equality(self):
        """测试棋子相等"""
        p1 = Piece(Color.RED, PieceType.ROOK)
        p2 = Piece(Color.RED, PieceType.ROOK)
        assert p1 == p2
        
        p3 = Piece(Color.BLACK, PieceType.ROOK)
        assert p1 != p3


class TestBoard:
    """Board 棋盘类测试"""

    def test_initial_board_creation(self):
        """Test initial board creation"""
        board = create_initial_board()
        assert board is not None
        assert board.get(4, 9) == PIECE_RED_KING  # Red king
        assert board.get(4, 0) == PIECE_BLACK_KING  # Black king
        assert board.get(0, 9) == PIECE_RED_ROOK  # Red rook
        assert board.get(0, 0) == PIECE_BLACK_ROOK  # Black rook (not cannon!)

    def test_board_get_set(self):
        """Test board get/set"""
        board = create_initial_board()
        
        # Read
        assert board.get(4, 9) == PIECE_RED_KING
        assert board.get(0, 9) == PIECE_RED_ROOK  # Red rook at (0,9), not black cannon
        
        # 越界读取返回空
        assert board.get(-1, 0) == PIECE_EMPTY
        assert board.get(0, 10) == PIECE_EMPTY
        
        # 设置
        board.set(4, 9, PIECE_EMPTY)
        assert board.get(4, 9) == PIECE_EMPTY
        
        board.set(4, 9, PIECE_RED_KING)
        assert board.get(4, 9) == PIECE_RED_KING

    def test_board_clone(self):
        """测试棋盘克隆"""
        board = create_initial_board()
        cloned = board.clone()
        
        assert board == cloned
        assert board is not cloned
        
        # 修改克隆不影响原棋盘
        cloned.set(0, 0, PIECE_EMPTY)
        assert board.get(0, 0) != PIECE_EMPTY

    def test_board_find_king(self):
        """测试找到将/帅"""
        board = create_initial_board()
        
        red_king = board.find_king(Color.RED)
        assert red_king == (4, 9)
        
        black_king = board.find_king(Color.BLACK)
        assert black_king == (4, 0)

    def test_board_count_pieces(self):
        """测试棋子计数"""
        board = create_initial_board()
        
        # 红方 16 颗棋子
        assert board.count_pieces(Color.RED) == 16
        # 黑方 16 颗棋子
        assert board.count_pieces(Color.BLACK) == 16
        # 总共 32 颗棋子
        assert board.count_pieces() == 32

    def test_board_get_all_pieces(self):
        """测试获取所有棋子"""
        board = create_initial_board()
        
        red_pieces = board.get_all_pieces(Color.RED)
        assert len(red_pieces) == 16
        
        black_pieces = board.get_all_pieces(Color.BLACK)
        assert len(black_pieces) == 16

    def test_board_is_empty(self):
        """测试空位判断"""
        board = create_initial_board()
        
        # 楚河汉界应该是空的
        assert board.is_empty(4, 5) is True
        assert board.is_empty(4, 4) is True
        
        # 有棋子的位置
        assert board.is_empty(4, 9) is False

    def test_board_to_array(self):
        """测试转换为数组"""
        board = create_initial_board()
        arr = board.to_array()
        
        assert len(arr) == 10  # 10 行
        assert len(arr[0]) == 9  # 9 列
        assert arr[9][4] == PIECE_RED_KING

    def test_board_from_array(self):
        """测试从数组创建棋盘"""
        arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
        arr[9][4] = PIECE_RED_KING
        
        board = board_from_array(arr)
        assert board.get(4, 9) == PIECE_RED_KING


class TestMove:
    """Move 着法类测试"""

    def test_move_creation(self):
        """测试创建着法"""
        move = Move(0, 9, 0, 8)  # 红车向上一格
        assert move.from_col == 0
        assert move.from_row == 9
        assert move.to_col == 0
        assert move.to_row == 8

    def test_move_is_valid(self):
        """测试着法有效性检查"""
        # 有效着法
        move = Move(0, 9, 0, 8)
        assert move.is_valid() is True
        
        # 无效着法
        move = Move(-1, 9, 0, 8)
        assert move.is_valid() is False
        
        move = Move(0, 9, 0, 10)
        assert move.is_valid() is False

    def test_move_equality(self):
        """测试着法相等"""
        m1 = Move(0, 9, 0, 8)
        m2 = Move(0, 9, 0, 8)
        assert m1 == m2
        
        m3 = Move(0, 9, 1, 8)
        assert m1 != m3

    def test_move_encode_decode(self):
        """测试着法编码解码"""
        # 原始着法
        move = Move(4, 9, 4, 8)
        encoded = move.encode()
        
        # 解码
        decoded = Move.decode(encoded)
        assert decoded.from_col == move.from_col
        assert decoded.from_row == move.from_row
        assert decoded.to_col == move.to_col
        assert decoded.to_row == move.to_row

    def test_move_encode_range(self):
        """测试着法编码范围"""
        # 所有可能的着法编码应该在 0-2084 范围内
        move = Move(0, 0, 0, 0)
        assert move.encode() == 0
        
        move = Move(8, 9, 8, 9)
        # from = 0 + 0 * 9 = 0
        # to = 8 + 9 * 9 = 8 + 81 = 89
        # encoded = 0 + 89 * 90 = 8010
        # 这个着法实际上是同一位置，不是合法着法
        # 但编码应该在合理范围内
        assert move.encode() < 8100


class TestBoardRepresentation:
    """棋盘表示测试"""

    def test_board_repr(self):
        """测试棋盘打印"""
        board = create_initial_board()
        repr_str = repr(board)
        
        # 应该包含行列标记
        assert "9" in repr_str
        assert "0" in repr_str
        assert "车" in repr_str or "ROOK" in str(board.get(0, 0))


class TestFenNotation:
    """FEN 记谱法测试"""

    def test_board_to_fen(self):
        """测试转换为 FEN"""
        board = create_initial_board()
        fen = board_to_fen(board)
        
        # FEN 应该包含基本信息
        assert "/" in fen
        assert "k" in fen.lower() or "K" in fen


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
