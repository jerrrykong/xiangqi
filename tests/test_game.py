"""单元测试: 游戏状态机 (game.py)"""
import pytest
from shared.constants import Color, PIECE_RED_ROOK, PIECE_RED_KING, PIECE_RED_PAWN, PIECE_BLACK_KING
from internal.chess.game import ChessGame, MoveRecord, GamePhase
from internal.chess.piece import Board
from shared.protocol import Move


class TestChessGameInit:
    """测试游戏初始化"""

    def test_initial_state(self):
        """测试初始状态"""
        game = ChessGame()
        assert game.phase == GamePhase.NOT_STARTED
        assert game.turn == Color.RED
        assert game.move_count == 0  # 尚未走棋
        assert not game.is_game_over
        assert game.history == []

    def test_default_board(self):
        """测试默认棋盘"""
        game = ChessGame()
        # 红车应该在 row=9, col=0
        assert game.board.get(0, 9) == PIECE_RED_ROOK
        # 黑将应该在 row=0, col=4
        assert game.board.get(4, 0) == PIECE_BLACK_KING

    def test_custom_players(self):
        """测试自定义玩家"""
        game = ChessGame(red_player="p1", black_player="p2")
        assert game.red_player == "p1"
        assert game.black_player == "p2"


class TestGameStart:
    """测试游戏开始"""

    def test_start_game(self):
        """测试开始游戏"""
        game = ChessGame()
        result = game.start()
        assert result is True
        assert game.phase == GamePhase.PLAYING

    def test_cannot_start_twice(self):
        """测试不能重复开始"""
        game = ChessGame()
        game.start()
        result = game.start()
        assert result is False
        assert game.phase == GamePhase.PLAYING


class TestMakeMove:
    """测试落子"""

    def test_simple_move(self):
        """测试简单落子: 红边兵前进"""
        game = ChessGame()
        game.start()
        
        # 红边兵从 (0, 6) 前进到 (0, 5)
        move = Move(from_col=0, from_row=6, to_col=0, to_row=5)
        success, error = game.make_move(move)
        
        assert success is True
        assert error == ""
        assert game.move_count == 1  # 已完成1步着法
        assert game.turn == Color.BLACK
        assert len(game.history) == 1

    def test_move_wrong_turn(self):
        """测试错误回合"""
        game = ChessGame()
        game.start()
        
        # 红方回合走黑方棋子 (错误)
        move = Move(from_col=0, from_row=0, to_col=0, to_row=1)  # 黑车
        success, error = game.make_move(move)
        
        assert success is False
        assert "没有己方棋子" in error or "起始位置" in error

    def test_move_invalid_coordinates(self):
        """测试无效坐标"""
        game = ChessGame()
        game.start()
        
        move = Move(from_col=0, from_row=0, to_col=9, to_row=9)  # 超出范围
        success, error = game.make_move(move)
        
        assert success is False

    def test_move_own_piece(self):
        """测试移动己方棋子"""
        game = ChessGame()
        game.start()
        
        # 红方回合尝试移动黑方棋子
        move = Move(from_col=4, from_row=0, to_col=4, to_row=1)  # 黑将
        success, error = game.make_move(move)
        
        assert success is False
        assert "没有己方棋子" in error or "起始位置" in error

    def test_not_started_error(self):
        """测试游戏未开始不能落子"""
        game = ChessGame()
        
        move = Move(from_col=0, from_row=6, to_col=0, to_row=5)
        success, error = game.make_move(move)
        
        assert success is False
        assert "尚未开始" in error

    def test_game_over_error(self):
        """测试游戏结束后不能落子"""
        game = ChessGame()
        game.start()
        
        # 强制结束游戏
        game.phase = GamePhase.RED_WINS
        
        move = Move(from_col=0, from_row=6, to_col=0, to_row=5)
        success, error = game.make_move(move)
        
        assert success is False
        assert "已结束" in error


class TestLegalMoves:
    """测试合法着法"""

    def test_get_legal_moves(self):
        """测试获取合法着法"""
        game = ChessGame()
        game.start()
        
        red_moves = game.get_legal_moves(Color.RED)
        assert len(red_moves) > 0
        
        # 红方合法着法数量应该合理 (约44-48步)
        # 车: 9+9=18, 炮: 9+9=18, 马: 2+2=4, 
        # 士: 2, 象: 2, 将: 1, 兵: 3+2=5
        # 总计约 50 步
        assert 40 <= len(red_moves) <= 60

    def test_pawn_cross_river(self):
        """测试兵过河"""
        game = ChessGame()
        game.start()
        
        # 红边兵前进 3 步到河口
        for i in range(3):
            game.make_move(Move(0, 6 - i, 0, 5 - i))
        
        # 此时兵已过河, 应该能横移
        game.make_move(Move(0, 3, 1, 3))  # 红边兵横移到 (1, 3)


class TestUndo:
    """测试悔棋"""

    def test_undo_basic(self):
        """测试基础悔棋"""
        game = ChessGame()
        game.start()
        
        # 红方走一步
        game.make_move(Move(0, 6, 0, 5))
        assert game.move_count == 1
        assert game.turn == Color.BLACK
        
        # 悔棋
        result = game.undo()
        assert result is True
        assert game.move_count == 0
        assert game.turn == Color.RED

    def test_undo_multiple(self):
        """测试多次悔棋"""
        game = ChessGame()
        game.start()
        
        game.make_move(Move(0, 6, 0, 5))  # 红
        game.make_move(Move(0, 3, 0, 4))  # 黑
        game.make_move(Move(8, 6, 8, 5))  # 红
        
        result = game.undo(times=2)
        assert result is True
        assert game.move_count == 1  # 还剩最后一步

    def test_undo_insufficient(self):
        """测试悔棋不足"""
        game = ChessGame()
        game.start()
        game.make_move(Move(0, 6, 0, 5))
        
        result = game.undo(times=5)  # 尝试悔棋5步
        assert result is False


class TestResign:
    """测试投降"""

    def test_resign_by_red(self):
        """测试红方投降"""
        game = ChessGame()
        game.start()
        
        game.resign(Color.RED)
        
        assert game.is_game_over
        assert game.phase == GamePhase.BLACK_WINS
        assert game.winner == Color.BLACK

    def test_resign_by_black(self):
        """测试黑方投降"""
        game = ChessGame()
        game.start()
        
        game.resign(Color.BLACK)
        
        assert game.is_game_over
        assert game.phase == GamePhase.RED_WINS


class TestSerialization:
    """测试序列化"""

    def test_to_fen(self):
        """测试 FEN 格式输出"""
        game = ChessGame()
        fen = game.to_fen()
        
        assert isinstance(fen, str)
        assert " " in fen  # FEN 格式包含空格

    def test_to_state(self):
        """测试状态快照"""
        game = ChessGame(room_id="test123")
        game.start()
        
        state = game.to_state()
        
        assert state.room_id == "test123"
        assert state.phase == "playing"
        assert state.move_count == 0  # 游戏未开始，无着法

    def test_get_history_notation(self):
        """测试着法历史"""
        game = ChessGame()
        game.start()
        
        game.make_move(Move(0, 6, 0, 5))
        game.make_move(Move(0, 3, 0, 4))
        
        notations = game.get_history_notation()
        assert len(notations) == 2


class TestBoardAfterMove:
    """测试落子后棋盘状态"""

    def test_piece_moved(self):
        """测试棋子移动到正确位置"""
        game = ChessGame()
        game.start()
        
        # 红边兵前进
        move = Move(0, 6, 0, 5)
        game.make_move(move)
        
        assert game.board.get(0, 5) == PIECE_RED_PAWN
        assert game.board.get(0, 6) < 0  # 原位置为空

    def test_capture(self):
        """测试吃子"""
        # 创建特殊局面: 黑卒在红兵前方一格 (row 5 vs row 6)
        # 注意：将帅放在不同列以避免飞将检测
        board_arr = [
            [-1]*9 for _ in range(10)
        ]
        board_arr[9][4] = 10   # 黑将 (row 9, col 4)
        board_arr[0][3] = 0    # 红将 (row 0, col 3) — 不同列避免飞将
        board_arr[5][0] = 16   # 黑卒 (row 5)
        board_arr[6][0] = 6    # 红兵 (row 6)
        
        from internal.chess.piece import Board as B
        
        game = ChessGame()
        game.board = B(board_arr)
        game.phase = GamePhase.PLAYING
        game.turn = Color.BLACK
        
        # 黑卒前进一格吃红兵 (row 5 → row 6)
        move = Move(0, 5, 0, 6)
        success, error = game.make_move(move)
        
        assert success is True, f"吃子失败: {error}"
        assert game.board.get(0, 5) < 0  # 原位置为空
        assert game.board.get(0, 6) == 16  # 黑卒移动到新位置


class TestCheckmateDetection:
    """测试将死检测"""

    def test_initial_not_checkmate(self):
        """测试初始局面不是将死"""
        game = ChessGame()
        game.start()
        
        assert not game.is_checkmate(Color.RED)
        assert not game.is_checkmate(Color.BLACK)

    def test_has_legal_moves_after_setup(self):
        """测试设置后有合法着法"""
        game = ChessGame()
        game.start()
        
        red_moves = game.get_legal_moves(Color.RED)
        assert len(red_moves) > 0
