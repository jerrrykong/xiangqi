"""着法生成器 - 生成所有合法着法."""
from typing import Iterator
from dataclasses import dataclass

from shared.constants import (
    Color,
    PieceType,
    PIECE_EMPTY,
    PIECE_RED_KING, PIECE_BLACK_KING,
    PIECE_RED_ADVISOR, PIECE_BLACK_ADVISOR,
    PIECE_RED_BISHOP, PIECE_BLACK_BISHOP,
    PIECE_RED_KNIGHT, PIECE_BLACK_KNIGHT,
    PIECE_RED_ROOK, PIECE_BLACK_ROOK,
    PIECE_RED_CANNON, PIECE_BLACK_CANNON,
    PIECE_RED_PAWN, PIECE_BLACK_PAWN,
    BOARD_ROWS, BOARD_COLS,
    RED_PALACE_TOP, RED_PALACE_BOTTOM, RED_PALACE_LEFT, RED_PALACE_RIGHT,
    BLACK_PALACE_TOP, BLACK_PALACE_BOTTOM, BLACK_PALACE_LEFT, BLACK_PALACE_RIGHT,
    RIVER_ROW,
    get_color_from_piece, is_red_piece, is_black_piece,
)

from .piece import Board
from shared.protocol import Move


@dataclass
class LegalMove:
    """合法着法"""
    from_col: int
    from_row: int
    to_col: int
    to_row: int
    piece: int
    captured: int  # 被吃的棋子编码，负数表示空位
    move_type: str  # 'move', 'capture', 'check'
    
    def to_move(self) -> Move:
        """转换为 Move 对象"""
        return Move(self.from_col, self.from_row, self.to_col, self.to_row)


class MoveGenerator:
    """着法生成器
    
    为每种棋子生成所有合法着法，考虑：
    - 棋子移动规则
    - 棋盘边界
    - 九宫限制 (将/帅/士)
    - 象的限制 (塞象眼)
    - 马的限制 (蹩马腿)
    - 兵的过河限制
    """

    def __init__(self, board: Board):
        """初始化着法生成器
        
        Args:
            board: 棋盘对象
        """
        self.board = board

    def generate_all_moves(self, color: Color, include_checks: bool = False) -> list[LegalMove]:
        """生成指定颜色的所有合法着法
        
        Args:
            color: 棋子颜色
            include_checks: 是否包含将军着的法
            
        Returns:
            合法着法列表
        """
        moves = []
        
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                piece = self.board.get(col, row)
                if piece >= 0 and get_color_from_piece(piece) == color:
                    piece_moves = self.generate_piece_moves(col, row, include_checks)
                    moves.extend(piece_moves)
        
        return moves

    def generate_piece_moves(self, col: int, row: int, include_checks: bool = False) -> list[LegalMove]:
        """生成指定位置棋子的所有合法着法
        
        Args:
            col: 列
            row: 行
            include_checks: 是否只返回将军着的法
            
        Returns:
            合法着法列表
        """
        piece = self.board.get(col, row)
        if piece < 0:
            return []
        
        piece_type = PieceType(piece % 10)
        color = get_color_from_piece(piece)
        
        generators = {
            PieceType.KING: self._generate_king_moves,
            PieceType.ADVISOR: self._generate_advisor_moves,
            PieceType.BISHOP: self._generate_bishop_moves,
            PieceType.KNIGHT: self._generate_knight_moves,
            PieceType.ROOK: self._generate_rook_moves,
            PieceType.CANNON: self._generate_cannon_moves,
            PieceType.PAWN: self._generate_pawn_moves,
        }
        
        generator = generators.get(piece_type)
        if generator:
            return generator(col, row, piece, color)
        return []

    def _generate_king_moves(self, col: int, row: int, piece: int, color: Color) -> list[LegalMove]:
        """生成将/帅的着法
        
        将/帅只能在九宫内直线移动一格
        """
        moves = []
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # 上下左右
        
        for dcol, drow in directions:
            new_col, new_row = col + dcol, row + drow
            
            # 检查是否在九宫范围内
            if not self._is_in_palace(new_col, new_row, color):
                continue
            
            # 检查目标位置
            target = self.board.get(new_col, new_row)
            if target < 0 or get_color_from_piece(target) != color:
                moves.append(LegalMove(
                    from_col=col, from_row=row,
                    to_col=new_col, to_row=new_row,
                    piece=piece, captured=target,
                    move_type='capture' if target >= 0 else 'move'
                ))
        
        return moves

    def _generate_advisor_moves(self, col: int, row: int, piece: int, color: Color) -> list[LegalMove]:
        """生成士/仕的着法
        
        士/仕只能在九宫内斜线移动一格
        """
        moves = []
        directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]  # 四个斜方向
        
        for dcol, drow in directions:
            new_col, new_row = col + dcol, row + drow
            
            # 检查是否在九宫范围内
            if not self._is_in_palace(new_col, new_row, color):
                continue
            
            # 检查目标位置
            target = self.board.get(new_col, new_row)
            if target < 0 or get_color_from_piece(target) != color:
                moves.append(LegalMove(
                    from_col=col, from_row=row,
                    to_col=new_col, to_row=new_row,
                    piece=piece, captured=target,
                    move_type='capture' if target >= 0 else 'move'
                ))
        
        return moves

    def _generate_bishop_moves(self, col: int, row: int, piece: int, color: Color) -> list[LegalMove]:
        """生成象/相的着法
        
        象/相走田字对角，不能过河
        关键：塞象眼检测
        """
        moves = []
        directions = [(2, 2), (2, -2), (-2, 2), (-2, -2)]  # 田字对角
        block_directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]  # 象眼位置
        
        for i, (dcol, drow) in enumerate(directions):
            new_col, new_row = col + dcol, row + drow
            
            # 检查是否在棋盘内
            if not self.board.is_valid_pos(new_col, new_row):
                continue
            
            # 检查是否过河
            # 红象不能到 row <= RIVER_ROW (rows 0-4 为黑方半场)
            # 黑象不能到 row > RIVER_ROW (rows 5-9 为红方半场)
            if color == Color.RED and new_row <= RIVER_ROW:
                continue
            if color == Color.BLACK and new_row > RIVER_ROW:
                continue
            
            # 塞象眼检测
            block_col = col + block_directions[i][0]
            block_row = row + block_directions[i][1]
            if not self.board.is_empty(block_col, block_row):
                continue  # 象眼被堵
            
            # 检查目标位置
            target = self.board.get(new_col, new_row)
            if target < 0 or get_color_from_piece(target) != color:
                moves.append(LegalMove(
                    from_col=col, from_row=row,
                    to_col=new_col, to_row=new_row,
                    piece=piece, captured=target,
                    move_type='capture' if target >= 0 else 'move'
                ))
        
        return moves

    def _generate_knight_moves(self, col: int, row: int, piece: int, color: Color) -> list[LegalMove]:
        """生成马的着法
        
        马走日字
        关键：蹩马腿检测
        """
        moves = []
        # 马腿位置 (先跳的方向)
        leg_positions = [
            ((0, -1), (-1, -2)),   # 上，腿在上
            ((0, -1), (1, -2)),    # 上，腿在上
            ((0, 1), (-1, 2)),     # 下，腿在下
            ((0, 1), (1, 2)),      # 下，腿在下
            ((-1, 0), (-2, -1)),    # 左，腿在左
            ((-1, 0), (-2, 1)),    # 左，腿在左
            ((1, 0), (2, -1)),     # 右，腿在右
            ((1, 0), (2, 1)),      # 右，腿在右
        ]
        
        for (ldcol, ldrow), (dcol, drow) in leg_positions:
            leg_col, leg_row = col + ldcol, row + ldrow
            new_col, new_row = col + dcol, row + drow
            
            # 检查目标位置是否在棋盘内
            if not self.board.is_valid_pos(new_col, new_row):
                continue
            
            # 蹩马腿检测
            if not self.board.is_empty(leg_col, leg_row):
                continue
            
            # 检查目标位置
            target = self.board.get(new_col, new_row)
            if target < 0 or get_color_from_piece(target) != color:
                moves.append(LegalMove(
                    from_col=col, from_row=row,
                    to_col=new_col, to_row=new_row,
                    piece=piece, captured=target,
                    move_type='capture' if target >= 0 else 'move'
                ))
        
        return moves

    def _generate_rook_moves(self, col: int, row: int, piece: int, color: Color) -> list[LegalMove]:
        """生成车的着法
        
        车走直线任意距离
        """
        moves = []
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # 上下左右
        
        for dcol, drow in directions:
            cur_col, cur_row = col, row
            
            while True:
                cur_col += dcol
                cur_row += drow
                
                if not self.board.is_valid_pos(cur_col, cur_row):
                    break
                
                target = self.board.get(cur_col, cur_row)
                
                if target < 0:
                    # 空位，可以移动
                    moves.append(LegalMove(
                        from_col=col, from_row=row,
                        to_col=cur_col, to_row=cur_row,
                        piece=piece, captured=target,
                        move_type='move'
                    ))
                elif get_color_from_piece(target) != color:
                    # 对方棋子，可以吃
                    moves.append(LegalMove(
                        from_col=col, from_row=row,
                        to_col=cur_col, to_row=cur_row,
                        piece=piece, captured=target,
                        move_type='capture'
                    ))
                    break
                else:
                    # 己方棋子，阻挡
                    break
        
        return moves

    def _generate_cannon_moves(self, col: int, row: int, piece: int, color: Color) -> list[LegalMove]:
        """生成炮的着法
        
        炮走直线任意距离:
        - 不吃子时路径必须为空
        - 吃子时路径中必须恰好有一个炮架(对方的棋子)
        """
        moves = []
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # 上下左右
        
        for dcol, drow in directions:
            cur_col, cur_row = col, row
            jumped = False  # 是否已经跳过了一个棋子
            
            while True:
                cur_col += dcol
                cur_row += drow
                
                if not self.board.is_valid_pos(cur_col, cur_row):
                    break
                
                target = self.board.get(cur_col, cur_row)
                
                if not jumped:
                    if target < 0:
                        # 空位，可以移动
                        moves.append(LegalMove(
                            from_col=col, from_row=row,
                            to_col=cur_col, to_row=cur_row,
                            piece=piece, captured=target,
                            move_type='move'
                        ))
                    else:
                        # 有棋子，跳过它
                        jumped = True
                else:
                    # 已经跳过了一个棋子，现在只能吃子或停止
                    if target < 0:
                        continue  # 继续寻找炮架
                    elif get_color_from_piece(target) != color:
                        # 对方棋子，可以吃
                        moves.append(LegalMove(
                            from_col=col, from_row=row,
                            to_col=cur_col, to_row=cur_row,
                            piece=piece, captured=target,
                            move_type='capture'
                        ))
                        break
                    else:
                        # 己方棋子，阻挡
                        break
        
        return moves

    def _generate_pawn_moves(self, col: int, row: int, piece: int, color: Color) -> list[LegalMove]:
        """生成兵/卒的着法
        
        兵/卒:
        - 未过河只能前进 (红方向上, 黑方向下)
        - 过河后可以横移
        """
        moves = []
        
        if color == Color.RED:
            # 红兵: 向 row 减小的方向走 (向上)
            forward = -1
            
            # 前进一步
            new_row = row + forward
            if new_row >= 0:
                target = self.board.get(col, new_row)
                if target < 0 or get_color_from_piece(target) != color:
                    moves.append(LegalMove(
                        from_col=col, from_row=row,
                        to_col=col, to_row=new_row,
                        piece=piece, captured=target,
                        move_type='capture' if target >= 0 else 'move'
                    ))
            
            # 过河后可以横移 (row <= RIVER_ROW 因为红兵方向向下，row 4 已到对方地盘)
            if row <= RIVER_ROW:
                for dcol in [-1, 1]:
                    new_col = col + dcol
                    if 0 <= new_col < BOARD_COLS:
                        target = self.board.get(new_col, row)
                        if target < 0 or get_color_from_piece(target) != color:
                            moves.append(LegalMove(
                                from_col=col, from_row=row,
                                to_col=new_col, to_row=row,
                                piece=piece, captured=target,
                                move_type='capture' if target >= 0 else 'move'
                            ))
        
        else:  # BLACK
            # 黑卒: 向 row 增大的方向走 (向下)
            forward = 1
            
            # 前进一步
            new_row = row + forward
            if new_row < BOARD_ROWS:
                target = self.board.get(col, new_row)
                if target < 0 or get_color_from_piece(target) != color:
                    moves.append(LegalMove(
                        from_col=col, from_row=row,
                        to_col=col, to_row=new_row,
                        piece=piece, captured=target,
                        move_type='capture' if target >= 0 else 'move'
                    ))
            
            # 过河后可以横移
            if row > RIVER_ROW:
                for dcol in [-1, 1]:
                    new_col = col + dcol
                    if 0 <= new_col < BOARD_COLS:
                        target = self.board.get(new_col, row)
                        if target < 0 or get_color_from_piece(target) != color:
                            moves.append(LegalMove(
                                from_col=col, from_row=row,
                                to_col=new_col, to_row=row,
                                piece=piece, captured=target,
                                move_type='capture' if target >= 0 else 'move'
                            ))
        
        return moves

    def _is_in_palace(self, col: int, row: int, color: Color) -> bool:
        """检查坐标是否在九宫内"""
        if color == Color.RED:
            return (RED_PALACE_LEFT <= col <= RED_PALACE_RIGHT and
                    RED_PALACE_TOP <= row <= RED_PALACE_BOTTOM)
        else:
            return (BLACK_PALACE_LEFT <= col <= BLACK_PALACE_RIGHT and
                    BLACK_PALACE_TOP <= row <= BLACK_PALACE_BOTTOM)

    def generate_king_moves(self, col: int, row: int, color: Color) -> list[LegalMove]:
        """生成将/帅的着法 (公开方法)"""
        piece = self.board.get(col, row)
        return self._generate_king_moves(col, row, piece, color)

    def generate_checking_moves(self, color: Color) -> list[LegalMove]:
        """生成能够将军的着法"""
        all_moves = self.generate_all_moves(color, include_checks=True)
        checking_moves = []
        
        for move in all_moves:
            # 模拟着法
            temp_board = self.board.clone()
            temp_board.set(move.to_col, move.to_row, move.piece)
            temp_board.set(move.from_col, move.from_row, PIECE_EMPTY)
            
            # 检查是否将军
            opponent = Color.BLACK if color == Color.RED else Color.RED
            if self._is_king_exposed(temp_board, opponent):
                checking_moves.append(move)
        
        return checking_moves

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
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                piece = board.get(col, row)
                if piece >= 0 and get_color_from_piece(piece) == opponent:
                    temp_gen = MoveGenerator(board)
                    piece_moves = temp_gen.generate_piece_moves(col, row)
                    for pm in piece_moves:
                        if pm.to_col == king_col and pm.to_row == king_row:
                            return True
        
        return False


def generate_moves(board: Board, color: Color) -> list[LegalMove]:
    """便捷函数: 生成所有合法着法"""
    return MoveGenerator(board).generate_all_moves(color)


def generate_checking_moves(board: Board, color: Color) -> list[LegalMove]:
    """便捷函数: 生成能够将军的着法"""
    return MoveGenerator(board).generate_checking_moves(color)


def count_moves(board: Board, color: Color) -> int:
    """便捷函数: 统计合法着法数量"""
    return len(generate_moves(board, color))
