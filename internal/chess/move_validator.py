"""着法验证器 - 验证着法的合法性."""
from typing import Optional

from shared.constants import (
    Color,
    PIECE_EMPTY,
    get_color_from_piece,
)

from .piece import Board
from shared.protocol import Move
from .move_generator import MoveGenerator, LegalMove


class MoveValidator:
    """着法验证器
    
    验证着法是否合法:
    1. 格式合法性检查 (坐标范围)
    2. 棋子归属检查 (是否是自己的棋子)
    3. 移动规则检查 (是否符合棋子移动规则)
    4. 送将检测 (不能把自己送入将被吃的局面)
    """

    def __init__(self, board: Board):
        """初始化着法验证器
        
        Args:
            board: 棋盘对象
        """
        self.board = board
        self.move_generator = MoveGenerator(board)

    def is_valid(self, move: Move, color: Color) -> tuple[bool, Optional[str]]:
        """验证着法是否合法
        
        Args:
            move: 着法
            color: 当前玩家颜色
            
        Returns:
            (是否合法, 错误信息)
        """
        # 1. 检查坐标范围
        if not self._is_valid_coordinates(move):
            return False, "坐标超出范围"
        
        # 2. 检查起始位置是否有己方棋子
        if not self._is_own_piece(move.from_col, move.from_row, color):
            return False, "起始位置没有己方棋子"
        
        # 3. 检查目标位置是否可以移动
        if not self._can_move_to(move, color):
            return False, "目标位置不能移动"
        
        # 4. 检查移动规则
        if not self._is_valid_piece_move(move, color):
            return False, "不符合棋子移动规则"
        
        # 5. 检查是否会送将 (最关键)
        if self._is_self_check(move, color):
            return False, "送将: 移动后将被将军"
        
        return True, None

    def is_valid_legal_move(self, move: LegalMove, color: Color) -> tuple[bool, Optional[str]]:
        """验证 LegalMove 是否合法 (用于着法生成器生成的结果二次验证)
        
        Args:
            move: LegalMove 着法
            color: 当前玩家颜色
            
        Returns:
            (是否合法, 错误信息)
        """
        return self.is_valid(move.to_move(), color)

    def validate_and_execute(self, move: Move, color: Color) -> tuple[bool, Optional[str], Optional[Board]]:
        """验证着法并执行
        
        Args:
            move: 着法
            color: 当前玩家颜色
            
        Returns:
            (是否成功, 错误信息, 执行后的棋盘)
        """
        is_valid, error = self.is_valid(move, color)
        if not is_valid:
            return False, error, None
        
        # 执行着法
        new_board = self.board.clone()
        piece = new_board.get(move.from_col, move.from_row)
        new_board.set(move.to_col, move.to_row, piece)
        new_board.set(move.from_col, move.from_row, PIECE_EMPTY)
        
        return True, None, new_board

    def _is_valid_coordinates(self, move: Move) -> bool:
        """检查坐标是否有效"""
        return (0 <= move.from_col < 9 and 0 <= move.from_row < 10 and
                0 <= move.to_col < 9 and 0 <= move.to_row < 10)

    def _is_own_piece(self, col: int, row: int, color: Color) -> bool:
        """检查起始位置是否有己方棋子"""
        piece = self.board.get(col, row)
        return piece >= 0 and get_color_from_piece(piece) == color

    def _can_move_to(self, move: Move, color: Color) -> bool:
        """检查目标位置是否可以移动"""
        target = self.board.get(move.to_col, move.to_row)
        # 空位可以移动，己方棋子不能移动到
        return target < 0 or get_color_from_piece(target) != color

    def _is_valid_piece_move(self, move: Move, color: Color) -> bool:
        """检查是否符合棋子移动规则"""
        piece = self.board.get(move.from_col, move.from_row)
        if piece < 0:
            return False
        
        # 使用着法生成器验证
        legal_moves = self.move_generator.generate_piece_moves(move.from_col, move.from_row)
        for lm in legal_moves:
            if lm.to_col == move.to_col and lm.to_row == move.to_row:
                return True
        
        return False

    def _is_self_check(self, move: Move, color: Color) -> bool:
        """检查移动后是否会送将"""
        # 模拟着法
        temp_board = self.board.clone()
        piece = temp_board.get(move.from_col, move.from_row)
        temp_board.set(move.to_col, move.to_row, piece)
        temp_board.set(move.from_col, move.from_row, PIECE_EMPTY)
        
        # 检查移动后己方将被是否被将军
        return self._is_king_exposed(temp_board, color)

    def _is_king_exposed(self, board: Board, color: Color) -> bool:
        """检查指定颜色的将/帅是否被将军（包括飞将检测）"""
        king_pos = board.find_king(color)
        if king_pos is None:
            return False
        
        king_col, king_row = king_pos
        opponent = Color.BLACK if color == Color.RED else Color.RED
        
        # 检查飞将：将帅同列且中间无棋子阻隔
        opponent_king_pos = board.find_king(opponent)
        if opponent_king_pos is not None:
            opp_col, opp_row = opponent_king_pos
            if opp_col == king_col:
                min_row = min(king_row, opp_row)
                max_row = max(king_row, opp_row)
                blocked = False
                for r in range(min_row + 1, max_row):
                    if board.get(king_col, r) >= 0:
                        blocked = True
                        break
                if not blocked:
                    return True
        
        # 检查所有对方棋子是否能吃到将/帅
        for row in range(10):
            for col in range(9):
                piece = board.get(col, row)
                if piece >= 0 and get_color_from_piece(piece) == opponent:
                    temp_gen = MoveGenerator(board)
                    piece_moves = temp_gen.generate_piece_moves(col, row)
                    for pm in piece_moves:
                        if pm.to_col == king_col and pm.to_row == king_row:
                            return True
        
        return False

    def get_error_message(self, move: Move, color: Color) -> str:
        """获取着法的错误信息"""
        _, error = self.is_valid(move, color)
        return error or "着法合法"


def validate_move(board: Board, move: Move, color: Color) -> tuple[bool, Optional[str]]:
    """便捷函数: 验证着法"""
    validator = MoveValidator(board)
    return validator.is_valid(move, color)


def validate_and_execute(board: Board, move: Move, color: Color) -> tuple[bool, Optional[str], Optional[Board]]:
    """便捷函数: 验证并执行着法"""
    validator = MoveValidator(board)
    return validator.validate_and_execute(move, color)
