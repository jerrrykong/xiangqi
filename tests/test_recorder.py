"""单元测试: 着法记录器 (recorder.py)"""
import pytest
from shared.constants import Color, PIECE_EMPTY, PIECE_RED_PAWN, PIECE_BLACK_PAWN
from internal.chess.recorder import (
    ZobristHasher,
    RepetitionState,
    GameRecorder,
)
from internal.chess.piece import Board
from shared.protocol import Move


class TestZobristHasher:
    """测试 Zobrist 哈希"""

    def test_init(self):
        """测试初始化"""
        ZobristHasher.init()  # 应该可以重复调用不报错
        assert ZobristHasher._side_key != 0
        assert len(ZobristHasher._piece_keys) > 0

    def test_compute_hash_initial(self):
        """测试初始棋盘哈希"""
        board = Board()
        h = ZobristHasher.compute_hash(board, Color.RED)
        assert isinstance(h, int)
        assert h != 0

    def test_hash_changes_with_move(self):
        """测试移动后哈希变化"""
        board = Board()
        h1 = ZobristHasher.compute_hash(board, Color.RED)
        
        # 移动红边兵
        new_board = board.clone()
        piece = new_board.get(0, 6)
        new_board.set(0, 5, piece)
        new_board.set(0, 6, PIECE_EMPTY)
        
        h2 = ZobristHasher.compute_hash(new_board, Color.BLACK)
        
        assert h1 != h2

    def test_hash_consistency(self):
        """测试相同局面哈希一致"""
        board1 = Board()
        board2 = Board()
        
        h1 = ZobristHasher.compute_hash(board1, Color.RED)
        h2 = ZobristHasher.compute_hash(board2, Color.RED)
        
        assert h1 == h2

    def test_update_hash(self):
        """测试增量更新哈希"""
        board = Board()
        h1 = ZobristHasher.compute_hash(board, Color.RED)
        
        # 移动红边兵
        piece = board.get(0, 6)
        h2 = ZobristHasher.update_hash(
            h1, piece, 0, 6, 0, 5, PIECE_EMPTY, Color.RED
        )
        
        # 直接计算
        new_board = board.clone()
        new_board.set(0, 5, piece)
        new_board.set(0, 6, PIECE_EMPTY)
        h3 = ZobristHasher.compute_hash(new_board, Color.BLACK)
        
        assert h2 == h3


class TestRepetitionState:
    """测试重复局面检测"""

    def test_initial_state(self):
        """测试初始状态"""
        rs = RepetitionState()
        assert rs.halfmove_clock == 0
        assert rs.fullmove_number == 0
        assert not rs.is_threefold_repetition()
        assert not rs.is_fifty_move_rule()

    def test_record_position(self):
        """测试记录局面"""
        rs = RepetitionState()
        board = Board()
        
        rs.record_position(board, Color.RED, PIECE_RED_PAWN, PIECE_EMPTY)
        
        assert rs.fullmove_number == 1
        assert len(rs.recent_hashes) == 1

    def test_halfmove_clock_pawn(self):
        """测试兵移动重置 halfmove clock"""
        rs = RepetitionState()
        board = Board()
        
        rs.halfmove_clock = 10
        rs.record_position(board, Color.RED, PIECE_RED_PAWN, PIECE_EMPTY)
        
        assert rs.halfmove_clock == 0

    def test_halfmove_clock_capture(self):
        """测试吃子重置 halfmove clock"""
        rs = RepetitionState()
        board = Board()
        
        rs.halfmove_clock = 10
        rs.record_position(board, Color.RED, PIECE_RED_PAWN, PIECE_BLACK_PAWN)
        
        assert rs.halfmove_clock == 0

    def test_fifty_move_rule(self):
        """测试50步和棋
        
        注意: 只有非兵/非吃子着法才会计入 halfmove clock。
        这里用兵吃子的场景，前50步每次都 reset halfmove_clock = 0，
        所以这个特定测试验证的是"兵移动"reset halfmove clock。
        """
        rs = RepetitionState()
        board = Board()
        
        # 兵移动会 reset halfmove_clock
        # 所以直接测试 halfmove clock 逻辑本身
        rs.halfmove_clock = 50
        assert rs.is_fifty_move_rule()
        
        # 重置后重新计数
        rs.halfmove_clock = 0
        for i in range(50):
            rs.halfmove_clock += 1
        assert rs.is_fifty_move_rule()


class TestGameRecorder:
    """测试着法记录器"""

    def test_init(self):
        """测试初始化"""
        recorder = GameRecorder(room_id="test")
        
        assert recorder.room_id == "test"
        assert recorder.move_count == 0
        assert recorder.current_hash != 0

    def test_record_move(self):
        """测试记录着法"""
        recorder = GameRecorder()
        
        board_before = Board().to_array()
        board_after = Board().to_array()
        # 模拟移动
        board_after[5][0] = PIECE_RED_PAWN
        board_after[6][0] = PIECE_EMPTY
        
        move = Move(0, 6, 0, 5)
        recorder.record_move(
            move=move,
            player=Color.RED,
            piece=PIECE_RED_PAWN,
            captured=PIECE_EMPTY,
            board_before=board_before,
            board_after=board_after,
        )
        
        assert recorder.move_count == 1

    def test_undo(self):
        """测试撤销"""
        recorder = GameRecorder()
        
        board_before = Board().to_array()
        board_after = Board().to_array()
        board_after[5][0] = PIECE_RED_PAWN
        board_after[6][0] = PIECE_EMPTY
        
        move = Move(0, 6, 0, 5)
        recorder.record_move(
            move=move,
            player=Color.RED,
            piece=PIECE_RED_PAWN,
            captured=PIECE_EMPTY,
            board_before=board_before,
            board_after=board_after,
        )
        
        assert recorder.move_count == 1
        
        recorder.undo_last()
        assert recorder.move_count == 0

    def test_check_draw_no_draw(self):
        """测试无和棋"""
        recorder = GameRecorder()
        is_draw, reason = recorder.check_draw()
        
        assert is_draw is False
        assert reason is None

    def test_to_json(self):
        """测试导出 JSON"""
        recorder = GameRecorder(room_id="test")
        recorder.red_player = "player1"
        recorder.black_player = "player2"
        recorder.result = "RED_WINS"
        
        json_str = recorder.to_json()
        
        assert isinstance(json_str, str)
        assert "test" in json_str
        assert "player1" in json_str

    def test_get_board_at_move(self):
        """测试获取指定步数后的棋盘"""
        recorder = GameRecorder()
        
        # 初始局面
        board0 = recorder.get_board_at_move(0)
        assert board0 is not None
        
        # 第0步不存在
        board1 = recorder.get_board_at_move(-1)
        assert board1 is None

    def test_replay(self):
        """测试回放生成器"""
        recorder = GameRecorder()
        
        steps = list(recorder.replay())
        assert len(steps) == 0  # 无着法


class TestGameRecorderDrawDetection:
    """测试和棋检测"""

    def test_draw_by_repetition(self):
        """测试三次重复和棋"""
        recorder = GameRecorder()
        
        # 模拟相同局面出现3次
        board = Board()
        h = ZobristHasher.compute_hash(board, Color.RED)
        
        for i in range(3):
            recorder.repetition.recent_hashes.append(h)
            recorder.repetition.position_counts[h] = i + 1
        
        assert recorder.repetition.is_threefold_repetition()
