"""游戏状态机 - 管理完整对局流程."""
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from enum import Enum
import copy

from chess.constants import (
    Color,
    PIECE_EMPTY,
    GameResult,
    WinReason,
    Difficulty,
    DIFFICULTY_SIMULATIONS,
    coord_to_notation,
    notation_to_coord,
    get_piece_name,
)
from chess.move import Move

from .piece import Board, board_to_fen
from .move_generator import MoveGenerator, LegalMove
from .move_validator import MoveValidator
from .win_checker import WinChecker, GameOverResult


class GamePhase(Enum):
    """游戏阶段"""
    NOT_STARTED = "not_started"
    PLAYING = "playing"
    RED_WINS = "red_wins"
    BLACK_WINS = "black_wins"
    DRAW = "draw"


@dataclass
class MoveRecord:
    """着法记录"""
    move: Move
    player: Color          # 执行着法的玩家
    piece: int             # 移动的棋子
    captured: int          # 吃掉的棋子 (负数=空位)
    board_before: list[list[int]]  # 着法前的棋盘
    board_after: list[list[int]]   # 着法后的棋盘
    notation: str = ""     # 记谱法 (如 "炮二平五")
    is_check: bool = False # 是否将军

    def __post_init__(self):
        if not self.notation:
            self.notation = self._generate_notation()

    def _generate_notation(self) -> str:
        """生成记谱法"""
        piece_name = get_piece_name(self.piece)
        from_not = coord_to_notation(self.move.from_col, self.move.from_row)
        to_not = coord_to_notation(self.move.to_col, self.move.to_row)
        if self.captured >= 0:
            return f"{piece_name}{from_not}吃{get_piece_name(self.captured)}"
        return f"{piece_name}{from_not}到{to_not}"


@dataclass
class GameState:
    """游戏状态快照 (用于断线重连)"""
    board: list[list[int]]
    turn: int           # 0=红方回合, 1=黑方回合
    phase: str
    move_count: int
    red_time: int       # 红方剩余时间(秒)
    black_time: int     # 黑方剩余时间(秒)
    room_id: str = ""
    red_player: str = ""   # 红方玩家ID
    black_player: str = ""  # 黑方玩家ID


class ChessGame:
    """中国象棋游戏状态机
    
    管理完整对局流程:
    - 回合交替 (红先黑后)
    - 着法执行与验证
    - 胜负判定
    - 着法历史记录
    - FEN 序列化
    - 悔棋功能
    """

    # 默认每步思考时间 (秒)
    DEFAULT_MOVE_TIME = 30
    # 默认总时间 (秒)
    DEFAULT_TOTAL_TIME = 600

    def __init__(
        self,
        room_id: str = "",
        red_player: str = "",
        black_player: str = "",
        total_time: int = DEFAULT_TOTAL_TIME,
        move_time: int = DEFAULT_MOVE_TIME,
    ):
        """初始化游戏
        
        Args:
            room_id: 房间ID
            red_player: 红方玩家ID
            black_player: 黑方玩家ID (人机对战时为空)
            total_time: 每方总时间(秒)
            move_time: 每步增加时间(秒)，用于步时制
        """
        self.room_id = room_id
        self.red_player = red_player
        self.black_player = black_player
        
        # 棋盘状态
        self.board = Board()
        self.turn = Color.RED  # 红先
        
        # 时间管理 (秒)
        self.red_time = total_time
        self.black_time = total_time
        self.move_time_increment = move_time
        
        # 着法历史
        self.history: List[MoveRecord] = []
        
        # 游戏阶段
        self.phase = GamePhase.NOT_STARTED
        
        # 游戏结果
        self.winner: Optional[Color] = None
        self.win_reason: Optional[str] = None
        self.game_result: Optional[str] = None
        
        # 辅助类
        self._board = Board()
        self._init_validators()

        # 着法计数器 (用于判定是否将军)
        self._last_move_was_check = False

        # === 局面重复与长将/长捉检测 ===
        # 局面 FEN 字符串 → 出现次数 (用于三次重复检测)
        self._initial_fen: str = board_to_fen(self._board, self.turn)
        self._position_counts: Dict[str, int] = {self._initial_fen: 1}
        # 连续将军计数 (按颜色)
        self._consecutive_checks_red: int = 0
        self._consecutive_checks_black: int = 0
        # 检测阈值: 同一局面出现 >= 此值启动检测
        self._REPETITION_THRESHOLD: int = 3
        self._PERPETUAL_CHECK_THRESHOLD: int = 3

    def _init_validators(self) -> None:
        """重新初始化验证器 (使用当前 _board)"""
        self.move_generator = MoveGenerator(self._board)
        self.move_validator = MoveValidator(self._board)
        self.win_checker = WinChecker(self._board)

    @property
    def board(self) -> Board:
        """获取棋盘"""
        return self._board

    @board.setter
    def board(self, value: Board) -> None:
        """设置棋盘并同步 validators"""
        self._board = value
        self._init_validators()

    # ==================== 回合管理 ====================

    @property
    def current_player(self) -> Color:
        """当前回合玩家"""
        return self.turn

    @property
    def move_count(self) -> int:
        """当前着法编号 (从0开始，即已完成着法数)"""
        return len(self.history)

    @property
    def is_game_over(self) -> bool:
        """游戏是否已结束"""
        return self.phase in (
            GamePhase.RED_WINS,
            GamePhase.BLACK_WINS,
            GamePhase.DRAW,
        )

    def start(self) -> bool:
        """开始游戏
        
        Returns:
            True=开始成功, False=游戏已开始或已结束
        """
        if self.phase != GamePhase.NOT_STARTED:
            return False
        self.phase = GamePhase.PLAYING
        # 重置局面重复检测状态
        self._initial_fen = board_to_fen(self._board, self.turn)
        self._position_counts = {self._initial_fen: 1}
        self._consecutive_checks_red = 0
        self._consecutive_checks_black = 0
        return True

    def switch_turn(self) -> None:
        """切换回合"""
        self.turn = Color.BLACK if self.turn == Color.RED else Color.RED

    # ==================== 着法执行 ====================

    def make_move(self, move: Move, player: Optional[Color] = None) -> Tuple[bool, str]:
        """执行着法
        
        Args:
            move: 着法
            player: 执行着法的玩家 (None=自动验证当前回合)
            
        Returns:
            (是否成功, 错误信息)
        """
        # 检查游戏是否已开始
        if self.phase == GamePhase.NOT_STARTED:
            return False, "游戏尚未开始"
        if self.is_game_over:
            return False, "游戏已结束"
        
        # 验证玩家
        current_player = player if player is not None else self.current_player
        if current_player != self.current_player:
            return False, f"现在轮到{('红' if self.current_player == Color.RED else '黑')}方"
        
        # 验证着法
        is_valid, error = self.move_validator.is_valid(move, current_player)
        if not is_valid:
            return False, error
        
        # 记录棋盘状态
        board_before = self.board.to_array()
        
        # 执行着法
        piece = self.board.get(move.from_col, move.from_row)
        captured = self.board.get(move.to_col, move.to_row)
        
        new_board = self.board.clone()
        new_board.set(move.to_col, move.to_row, piece)
        new_board.set(move.from_col, move.from_row, PIECE_EMPTY)
        
        # 检查是否将军
        self.board = new_board
        opponent = Color.BLACK if current_player == Color.RED else Color.RED
        is_check = self.win_checker.is_king_exposed(opponent)
        
        # 记录着法
        record = MoveRecord(
            move=move,
            player=current_player,
            piece=piece,
            captured=captured,
            board_before=board_before,
            board_after=self.board.to_array(),
            is_check=is_check,
        )
        self.history.append(record)
        
        # 更新辅助类
        self.move_generator = MoveGenerator(self.board)
        self.move_validator = MoveValidator(self.board)
        self.win_checker = WinChecker(self.board)
        self._last_move_was_check = is_check
        
        # 检查游戏结束
        game_over = self.win_checker.check_game_over(opponent)
        if game_over.is_over:
            self._handle_game_over(game_over)

        # 切换回合
        if not self.is_game_over:
            self.switch_turn()

        # 更新局面 FEN 并检测局面重复 / 长将 / 长捉
        if not self.is_game_over:
            current_fen = board_to_fen(self._board, self.turn)
            count = self._position_counts.get(current_fen, 0) + 1
            self._position_counts[current_fen] = count

            # 更新连续将军计数
            if is_check:
                if current_player == Color.RED:
                    self._consecutive_checks_red += 1
                    self._consecutive_checks_black = 0
                else:
                    self._consecutive_checks_black += 1
                    self._consecutive_checks_red = 0
            else:
                self._consecutive_checks_red = 0
                self._consecutive_checks_black = 0

            # 检测三次重复局面 / 长将
            if count >= self._REPETITION_THRESHOLD:
                rep_result = self._detect_repetition_violation(
                    is_check=is_check,
                    current_player=current_player,
                )
                if rep_result.is_over:
                    self._handle_game_over(rep_result)
        
        return True, ""

    def make_move_from_notation(
        self,
        from_notation: str,
        to_notation: str,
        player: Optional[Color] = None,
    ) -> Tuple[bool, str]:
        """从记谱法执行着法
        
        Args:
            from_notation: 起始位置记谱 (如 "e1")
            to_notation: 目标位置记谱 (如 "e2")
            player: 执行着法的玩家
        """
        from_coord = notation_to_coord(from_notation)
        to_coord = notation_to_coord(to_notation)
        
        if from_coord is None or to_coord is None:
            return False, "无效的记谱法"
        
        move = Move(from_coord[0], from_coord[1], to_coord[0], to_coord[1])
        return self.make_move(move, player)

    def get_legal_moves(self, color: Optional[Color] = None) -> List[LegalMove]:
        """获取当前合法着法
        
        Args:
            color: 棋子颜色 (None=当前回合玩家)
        """
        player = color if color is not None else self.current_player
        return self.move_generator.generate_all_moves(player)

    def get_checking_moves(self, color: Optional[Color] = None) -> List[LegalMove]:
        """获取能够将军的着法"""
        player = color if color is not None else self.current_player
        return self.move_generator.generate_checking_moves(player)

    # ==================== 胜负判定 ====================

    def _handle_game_over(self, result) -> None:
        """处理游戏结束"""
        if result.winner == Color.RED:
            self.phase = GamePhase.RED_WINS
            self.winner = Color.RED
            self.game_result = GameResult.RED_WINS
        elif result.winner == Color.BLACK:
            self.phase = GamePhase.BLACK_WINS
            self.winner = Color.BLACK
            self.game_result = GameResult.BLACK_WINS
        else:
            self.phase = GamePhase.DRAW
            self.winner = None
            self.game_result = GameResult.DRAW
        
        self.win_reason = result.reason

    def is_in_check(self, color: Optional[Color] = None) -> bool:
        """检查是否被将军"""
        player = color if color is not None else self.current_player
        opponent = Color.BLACK if player == Color.RED else Color.RED
        return self.win_checker.is_king_exposed(player)

    def is_checkmate(self, color: Optional[Color] = None) -> bool:
        """检查是否是将死"""
        player = color if color is not None else self.current_player
        return self.win_checker.is_checkmate(player)

    def is_stalemate(self, color: Optional[Color] = None) -> bool:
        """检查是否是困毙"""
        player = color if color is not None else self.current_player
        return self.win_checker.is_stalemate(player)

    # ==================== 重复局面 / 长将 / 长捉 ====================

    def _detect_repetition_violation(
        self, is_check: bool, current_player: Color,
    ) -> GameOverResult:
        """检测局面重复导致的违规或和棋。

        规则:
        1. 三次重复 + 长将 → 将军方判负
        2. 三次重复 + 长捉 → 捉子方判负
        3. 三次重复 (无长将/长捉) → 和棋

        Args:
            is_check: 当前着法是否将军
            current_player: 当前执行着法的玩家

        Returns:
            GameOverResult
        """
        # 长将: 连续将军 ≥ 阈值 且 同一局面出现 ≥ 阈值 → 将军方判负
        if is_check:
            if current_player == Color.RED and self._consecutive_checks_red >= self._PERPETUAL_CHECK_THRESHOLD:
                return GameOverResult(
                    is_over=True,
                    winner=Color.BLACK,
                    result=GameResult.BLACK_WINS,
                    reason=WinReason.PERPETUAL_CHECK,
                )
            elif current_player == Color.BLACK and self._consecutive_checks_black >= self._PERPETUAL_CHECK_THRESHOLD:
                return GameOverResult(
                    is_over=True,
                    winner=Color.RED,
                    result=GameResult.RED_WINS,
                    reason=WinReason.PERPETUAL_CHECK,
                )

        # TODO: 长捉检测 — 后续通过局面差异分析补充

        # 三次重复无违规 → 和棋
        return GameOverResult(
            is_over=True,
            winner=None,
            result=GameResult.DRAW,
            reason=WinReason.THREEFOLD_REPETITION,
        )

    def get_position_counts(self) -> Dict[str, int]:
        """返回当前局面 FEN 计数 (供调试/AI 查询)。"""
        return dict(self._position_counts)

    def get_current_fen_key(self) -> str:
        """返回当前局面的 FEN 键 (用于重复检测)。"""
        return board_to_fen(self._board, self.turn)

    # ==================== 悔棋功能 ====================

    def undo(self, times: int = 1) -> bool:
        """悔棋
        
        Args:
            times: 悔棋步数
            
        Returns:
            True=悔棋成功, False=无法悔棋
        """
        if len(self.history) < times:
            return False
        
        for _ in range(times):
            self.history.pop()
        
        # 恢复棋盘到最后一着后的状态，或初始状态
        if self.history:
            last_record = self.history[-1]
            self.board = Board(last_record.board_after)
            # 回合: 上一着的下一位
            self.turn = Color.BLACK if last_record.player == Color.RED else Color.RED
            self._last_move_was_check = last_record.is_check
        else:
            self.board = Board()
            self.turn = Color.RED
            self._last_move_was_check = False
        
        # 重建局面计数
        self._initial_fen = board_to_fen(self._board, self.turn)
        self._position_counts = {self._initial_fen: 1}
        self._consecutive_checks_red = 0
        self._consecutive_checks_black = 0

        # 从历史记录重建局面计数 (着法后的局面, 包含回合)
        for record in self.history:
            board_after_move = Board(record.board_after)
            next_turn = Color.BLACK if record.player == Color.RED else Color.RED
            fen_after = board_to_fen(board_after_move, next_turn)
            count = self._position_counts.get(fen_after, 0) + 1
            self._position_counts[fen_after] = count

            # 重建连续将军计数
            if record.is_check:
                if record.player == Color.RED:
                    self._consecutive_checks_red += 1
                    self._consecutive_checks_black = 0
                else:
                    self._consecutive_checks_black += 1
                    self._consecutive_checks_red = 0
            else:
                self._consecutive_checks_red = 0
                self._consecutive_checks_black = 0
        
        # 更新辅助类
        self.move_generator = MoveGenerator(self.board)
        self.move_validator = MoveValidator(self.board)
        self.win_checker = WinChecker(self.board)
        
        # 重置游戏阶段
        if self.is_game_over:
            self.phase = GamePhase.PLAYING
            self.winner = None
            self.win_reason = None
            self.game_result = None
        
        return True

    # ==================== 投降与和棋 ====================

    def resign(self, player: Color) -> bool:
        """投降
        
        Args:
            player: 投降的玩家
            
        Returns:
            True=投降成功, False=游戏已结束
        """
        if self.is_game_over or self.phase == GamePhase.NOT_STARTED:
            return False
        
        opponent = Color.BLACK if player == Color.RED else Color.RED
        if opponent == Color.RED:
            self.phase = GamePhase.RED_WINS
            self.game_result = GameResult.RED_RESIGN
        else:
            self.phase = GamePhase.BLACK_WINS
            self.game_result = GameResult.BLACK_RESIGN
        
        self.winner = opponent
        self.win_reason = WinReason.RESIGN
        return True

    def offer_draw(self, player: Color) -> None:
        """请求和棋 (记录状态，由外部处理响应)"""
        # 由外部 WebSocket 处理和棋请求/响应
        pass

    # ==================== 序列化 ====================

    def to_fen(self) -> str:
        """转换为 FEN 格式"""
        return board_to_fen(self.board, self.turn)

    def to_state(self) -> GameState:
        """获取游戏状态快照"""
        return GameState(
            board=self.board.to_array(),
            turn=0 if self.turn == Color.RED else 1,
            phase=self.phase.value,
            move_count=self.move_count,
            red_time=self.red_time,
            black_time=self.black_time,
            room_id=self.room_id,
            red_player=self.red_player,
            black_player=self.black_player,
        )

    def get_history_notation(self) -> List[str]:
        """获取着法历史 (记谱法格式)"""
        return [record.notation for record in self.history]

    def get_last_move(self) -> Optional[Move]:
        """获取最后一步着法"""
        if self.history:
            return self.history[-1].move
        return None

    def __repr__(self) -> str:
        """打印棋盘"""
        board_repr = repr(self.board)
        status = f"{'红' if self.turn == Color.RED else '黑'}方回合"
        if self.is_game_over:
            status = f"游戏结束: {self.game_result}"
        elif self.is_in_check():
            status += " (将军!)"
        return f"{board_repr}\n{status}\n着法数: {len(self.history)}"
