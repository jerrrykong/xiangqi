"""胜负判定器 - 检测游戏是否结束及胜者."""
from dataclasses import dataclass
from typing import Optional

from chess.constants import (
    Color,
    GameResult,
    WinReason,
)

from .piece import Board
from .move_generator import MoveGenerator
from .move_validator import MoveValidator


@dataclass
class GameOverResult:
    """游戏结束结果"""
    is_over: bool
    winner: Optional[int] = None  # 0=红方, 1=黑方, -1=无(和棋)
    result: Optional[str] = None
    reason: Optional[str] = None


class WinChecker:
    """胜负判定器
    
    检测以下游戏结束情况:
    1. 将死 (无合法着法且被将军)
    2. 困毙 (无合法着法但未被将军)
    3. 认输
    4. 超时
    5. 双方同意和棋
    6. 50回合无吃子 (可选规则)
    """

    def __init__(self, board: Board):
        """初始化胜负判定器
        
        Args:
            board: 棋盘对象
        """
        self.board = board
        self.move_generator = MoveGenerator(board)
        self.move_validator = MoveValidator(board)

    def check_game_over(self, color_to_move: Color) -> GameOverResult:
        """检查游戏是否结束
        
        Args:
            color_to_move: 当前应该移动的玩家颜色
            
        Returns:
            GameOverResult
        """
        # 检查是否有真正合法着法（过滤送将着法）
        if not self.has_legal_moves(color_to_move):
            if self.is_king_exposed(color_to_move):
                # 将死
                winner = Color.BLACK if color_to_move == Color.RED else Color.RED
                return GameOverResult(
                    is_over=True,
                    winner=winner,
                    result=GameResult.RED_WINS if winner == Color.RED else GameResult.BLACK_WINS,
                    reason=WinReason.CHECKMATE
                )
            else:
                # 困毙
                winner = Color.BLACK if color_to_move == Color.RED else Color.RED
                return GameOverResult(
                    is_over=True,
                    winner=winner,
                    result=GameResult.RED_WINS if winner == Color.RED else GameResult.BLACK_WINS,
                    reason=WinReason.STALEMATE
                )
        
        return GameOverResult(is_over=False)

    def is_king_exposed(self, color: Color) -> bool:
        """检查指定颜色的将/帅是否被将军
        
        包括飞将（将帅对面）检测
        
        Args:
            color: 棋子颜色
            
        Returns:
            True=被将军, False=安全
        """
        king_pos = self.board.find_king(color)
        if king_pos is None:
            return False
        
        king_col, king_row = king_pos
        opponent = Color.BLACK if color == Color.RED else Color.RED
        
        # 检查飞将：将帅同列且中间无棋子阻隔
        opponent_king_pos = self.board.find_king(opponent)
        if opponent_king_pos is not None:
            opp_col, opp_row = opponent_king_pos
            if opp_col == king_col:
                # 同列，检查中间是否有棋子
                min_row = min(king_row, opp_row)
                max_row = max(king_row, opp_row)
                blocked = False
                for r in range(min_row + 1, max_row):
                    if self.board.get(king_col, r) >= 0:
                        blocked = True
                        break
                if not blocked:
                    return True
        
        # 检查所有对方棋子是否能吃到将/帅
        for row in range(10):
            for col in range(9):
                piece = self.board.get(col, row)
                if piece >= 0 and (piece // 10) == opponent:
                    piece_moves = self.move_generator.generate_piece_moves(col, row)
                    for pm in piece_moves:
                        if pm.to_col == king_col and pm.to_row == king_row:
                            return True
        
        return False

    def has_legal_moves(self, color: Color) -> bool:
        """检查指定颜色是否有合法着法（过滤送将着法）
        
        Args:
            color: 棋子颜色
            
        Returns:
            True=有合法着法, False=无合法着法
        """
        pseudo_legal_moves = self.move_generator.generate_all_moves(color)
        for move in pseudo_legal_moves:
            is_valid, _ = self.move_validator.is_valid(move, color)
            if is_valid:
                return True
        return False

    def get_checking_pieces(self, color: Color) -> list[tuple[int, int, int]]:
        """获取正在将军的对方棋子
        
        Args:
            color: 被将军一方的颜色
            
        Returns:
            [(col, row, piece_encoding), ...]
        """
        checking = []
        opponent = Color.BLACK if color == Color.RED else Color.RED
        king_pos = self.board.find_king(color)
        
        if king_pos is None:
            return checking
        
        king_col, king_row = king_pos
        
        for row in range(10):
            for col in range(9):
                piece = self.board.get(col, row)
                if piece >= 0 and (piece // 10) == opponent:
                    piece_moves = self.move_generator.generate_piece_moves(col, row)
                    for pm in piece_moves:
                        if pm.to_col == king_col and pm.to_row == king_row:
                            checking.append((col, row, piece))
                            break
        
        return checking

    def is_checkmate(self, color: Color) -> bool:
        """检查是否是将死局面
        
        Args:
            color: 棋子颜色
            
        Returns:
            True=将死, False=未将死
        """
        return not self.has_legal_moves(color) and self.is_king_exposed(color)

    def is_stalemate(self, color: Color) -> bool:
        """检查是否是困毙局面 (非将死的无合法着法)
        
        Args:
            color: 棋子颜色
            
        Returns:
            True=困毙, False=未困毙
        """
        return not self.has_legal_moves(color) and not self.is_king_exposed(color)

    def would_be_check(self, from_col: int, from_row: int, to_col: int, to_row: int, color: Color) -> bool:
        """检查移动后是否会被将军
        
        Args:
            from_col, from_row: 起始位置
            to_col, to_row: 目标位置
            color: 移动方颜色
            
        Returns:
            True=会被将军, False=安全
        """
        from chess.move import Move
        move = Move(from_col, from_row, to_col, to_row)
        validator = MoveValidator(self.board)
        return validator._is_self_check(move, color)


def check_game_over(board: Board, color_to_move: Color) -> GameOverResult:
    """便捷函数: 检查游戏是否结束"""
    checker = WinChecker(board)
    return checker.check_game_over(color_to_move)


def is_king_exposed(board: Board, color: Color) -> bool:
    """便捷函数: 检查是否被将军"""
    checker = WinChecker(board)
    return checker.is_king_exposed(color)


def is_checkmate(board: Board, color: Color) -> bool:
    """便捷函数: 检查是否将死"""
    checker = WinChecker(board)
    return checker.is_checkmate(color)


def is_stalemate(board: Board, color: Color) -> bool:
    """便捷函数: 检查是否困毙"""
    checker = WinChecker(board)
    return checker.is_stalemate(color)
