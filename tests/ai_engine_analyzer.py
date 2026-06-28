"""
AI 引擎问题分析工具 - 可复用脚本
==============================

用法:
    # 基础用法：分析 FEN 局面 + AI 引擎行为
    python tests/ai_engine_analyzer.py \
        --fen "2bak1b2/4a4/c7r/N7p/9/9/P5r1P/R3BC3/4A1n2/3A1KB2 r - - 0 1" \
        --bad-move "f7->g7" \
        --good-move "f7->f8"

    # 也可以只输入 FEN 进行分析
    python tests/ai_engine_analyzer.py --fen "<FEN>"

    # 带用户报告中的威胁着法
    python tests/ai_engine_analyzer.py --fen "<FEN>" --threat-move "a2->f2"

工作流程:
    1. 解析 FEN → 棋盘
    2. 验证用户报告的"杀棋威胁"（是将军？是将死？还是送子？）
    3. 穷举当前走子方的所有合法着法，并分类
    4. 多深度/多难度运行 AI 引擎
    5. 对比 AI 输出 vs 用户指定的坏着/好着
    6. 输出结构化分析报告
"""
import sys
import os
import time
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'game-service'))

from chess.piece import Board, fen_to_board, board_to_fen
from chess.move_generator import MoveGenerator
from chess.win_checker import WinChecker
from chess.constants import (
    Color, Difficulty,
    PIECE_EMPTY,
    PIECE_RED_KING, PIECE_RED_ADVISOR, PIECE_RED_BISHOP, PIECE_RED_KNIGHT,
    PIECE_RED_ROOK, PIECE_RED_CANNON, PIECE_RED_PAWN,
    PIECE_BLACK_KING, PIECE_BLACK_ADVISOR, PIECE_BLACK_BISHOP, PIECE_BLACK_KNIGHT,
    PIECE_BLACK_ROOK, PIECE_BLACK_CANNON, PIECE_BLACK_PAWN,
    BOARD_ROWS, BOARD_COLS,
)
from ai.engine import ChessAI, get_ai_move

# ============================================================
# 常量 & 工具
# ============================================================

PIECE_CHARS = {
    PIECE_RED_KING: '帅', PIECE_RED_ADVISOR: '仕', PIECE_RED_BISHOP: '相',
    PIECE_RED_KNIGHT: '馬', PIECE_RED_ROOK: '車', PIECE_RED_CANNON: '炮',
    PIECE_RED_PAWN: '兵',
    PIECE_BLACK_KING: '将', PIECE_BLACK_ADVISOR: '士', PIECE_BLACK_BISHOP: '象',
    PIECE_BLACK_KNIGHT: '馬', PIECE_BLACK_ROOK: '車', PIECE_BLACK_CANNON: '砲',
    PIECE_BLACK_PAWN: '卒',
    PIECE_EMPTY: '·',
}

RED = '\033[31m'
YELLOW = '\033[33m'
GREEN = '\033[32m'
BOLD = '\033[1m'
RESET = '\033[0m'

SEP = "=" * 70
SEP2 = "-" * 70


def col_label(c: int) -> str:
    return chr(ord('a') + c)


def move_str(move) -> str:
    """格式化着法: e.g. f7→f8。支持 Move 对象或 (fc,fr,tc,tr) 元组"""
    if move is None:
        return "None"
    if isinstance(move, tuple):
        fc, fr, tc, tr = move
        return f"{col_label(fc)}{fr}→{col_label(tc)}{tr}"
    return f"{col_label(move.from_col)}{move.from_row}→{col_label(move.to_col)}{move.to_row}"


def parse_move_str(s: str):
    """解析着法字符串 e.g. 'f7->f8' 或 'f7→f8' → (from_col,from_row,to_col,to_row)"""
    import re
    m = re.match(r'([a-i])(\d+)\s*(?:->|→|=>)\s*([a-i])(\d+)', s.strip())
    if not m:
        return None
    return (ord(m.group(1)) - ord('a'), int(m.group(2)),
            ord(m.group(3)) - ord('a'), int(m.group(4)))


def print_board(board: Board) -> None:
    """彩色打印棋盘"""
    print()
    print("    a  b  c  d  e  f  g  h  i")
    for row in range(BOARD_ROWS):
        line = f"{row:2d} "
        for col in range(BOARD_COLS):
            p = board.get(col, row)
            c = RED if 0 < p < 10 else (YELLOW if p >= 10 else '')
            line += f" {c}{PIECE_CHARS.get(p, '?')}{RESET} "
        print(line)
    print()


def piece_name(piece_id: int) -> str:
    """返回棋子中文名（带颜色）"""
    side = '红' if 0 < piece_id < 10 else '黑'
    name = PIECE_CHARS.get(piece_id, '?')
    color = RED if side == '红' else YELLOW
    return f"{color}{side}{name}{RESET}"


# ============================================================
# 核心分析类
# ============================================================

class AIEngineAnalyzer:
    """AI 引擎问题分析器"""

    def __init__(self, fen: str, bad_move_str: str = None, good_move_str: str = None,
                 threat_move_str: str = None):
        self.fen = fen
        self.bad_move_str = bad_move_str
        self.good_move_str = good_move_str
        self.threat_move_str = threat_move_str

        # 解析着法
        self.bad_move = parse_move_str(bad_move_str) if bad_move_str else None
        self.good_move = parse_move_str(good_move_str) if good_move_str else None
        self.threat_move = parse_move_str(threat_move_str) if threat_move_str else None

        # 解析棋盘
        self.board = fen_to_board(fen)
        # 从 FEN 第二个字段提取走子方
        fen_parts = fen.split()
        if len(fen_parts) >= 2:
            turn_char = fen_parts[1].lower()
            self.turn_color = Color.RED if turn_char == 'r' else Color.BLACK
        else:
            self.turn_color = Color.RED  # 默认红方

        # AI 搜索结果缓存
        self.ai_results: dict = {}

    # ---- 阶段 1: 局面解析 ----
    def analyze_position(self):
        """打印并验证局面"""
        print(SEP)
        print(f"{BOLD}阶段 1: 局面解析{RESET}")
        print(SEP)
        print(f"FEN: {self.fen}")
        turn_name = '红方' if self.turn_color == Color.RED else '黑方'
        print(f"当前走子方: {turn_name}")
        print_board(self.board)

        # 基本统计
        red_count = sum(1 for c in range(BOARD_COLS) for r in range(BOARD_ROWS)
                        if 0 < self.board.get(c, r) < 10)
        black_count = sum(1 for c in range(BOARD_COLS) for r in range(BOARD_ROWS)
                          if self.board.get(c, r) >= 10)
        print(f"子力统计: 红方 {red_count} 子, 黑方 {black_count} 子")
        print()

    # ---- 阶段 2: 杀棋威胁验证 ----
    def verify_threat(self):
        """
        验证用户报告的威胁着法是否真的是将死/将军/送子。

        如果用户提供了 threat_move：
            - 在原始局面上执行 threat_move
            - 检查对手王是否被将/将死/可逃
        如果用户提供了 bad_move：
            - 在原始局面上执行 bad_move
            - 再执行用户暗示的威胁着法
            - 判断是否真的构成将死
        """
        print(SEP)
        print(f"{BOLD}阶段 2: 威胁验证{RESET}")
        print(SEP)

        if self.threat_move:
            self._verify_explicit_threat()
        elif self.bad_move:
            self._verify_implicit_threat()
        else:
            print("(未提供威胁着法，跳过此阶段)")
            print()

    def _verify_explicit_threat(self):
        """验证用户明确指定的威胁着法"""
        fc, fr, tc, tr = self.threat_move
        threat_board = self.board.clone()
        piece = threat_board.get(fc, fr)
        threat_board.set(fc, fr, PIECE_EMPTY)
        threat_board.set(tc, tr, piece)

        threat_name = f"{piece_name(piece)} {move_str(self.threat_move)}"
        print(f"用户声称的威胁着法: {threat_name}")
        print("执行威胁着法后局面:")
        print_board(threat_board)

        opponent = Color.BLACK if self.turn_color == Color.RED else Color.RED
        wc = WinChecker(threat_board)
        is_check = wc.is_king_exposed(self.turn_color)
        is_mate = wc.is_checkmate(self.turn_color)
        has_legal = wc.has_legal_moves(self.turn_color)

        print(f"  对手王被将军? {is_check}")
        print(f"  对手王被将死? {is_mate}")
        print(f"  对手有合法着法? {has_legal}")

        # 分析逃路
        if is_check:
            self._analyze_king_escapes(threat_board)

        # 结论
        if is_mate:
            print(f"\n  {BOLD}结论: 这是真正的将死！{RESET}")
        elif is_check:
            print(f"\n  {BOLD}结论: 是将军但非将死，对手有逃路{RESET}")
        else:
            print(f"\n  {BOLD}结论: 甚至不是将军，可能是送子或其他战术{RESET}")
        print()

    def _verify_implicit_threat(self):
        """当用户只给了 bad_move 时，尝试分析隐含威胁"""
        fc, fr, tc, tr = self.bad_move
        # 先走 bad_move
        bad_board = self.board.clone()
        piece = bad_board.get(fc, fr)
        bad_board.set(fc, fr, PIECE_EMPTY)
        bad_board.set(tc, tr, piece)

        print(f"AI 错误着法: {piece_name(piece)} {move_str(self.bad_move)}")
        print("走后局面:")
        print_board(bad_board)

        # 检查走完后的直接结果
        wc = WinChecker(bad_board)
        # 检查对手能否将军走子方
        opponent = Color.BLACK if self.turn_color == Color.RED else Color.RED

        # 找对手所有合法着法中能杀棋的
        mg = MoveGenerator(bad_board)
        threat_moves = []
        for m in mg.generate_all_moves(opponent):
            test = bad_board.clone()
            p = test.get(m.from_col, m.from_row)
            test.set(m.from_col, m.from_row, PIECE_EMPTY)
            test.set(m.to_col, m.to_row, p)
            wc2 = WinChecker(test)
            if not wc2.is_king_exposed(opponent):  # 对手不走送将
                if wc2.is_checkmate(self.turn_color):
                    threat_moves.append(m)

        if threat_moves:
            print(f"\n  {BOLD}走完 bad_move 后，对手有 {len(threat_moves)} 种方式将死走子方{RESET}")
            for m in threat_moves[:5]:
                print(f"    ❌ {piece_name(piece)} {move_str(m)}")
        else:
            # 不是杀，检查是否送子
            print(f"\n  走完 bad_move 后对手无法立即将死")
            # 简易评估：对手能否直接吃掉走的这个棋子
            piece_at_to = bad_board.get(tc, tr)
            opponent_captors = []
            for m2 in mg.generate_all_moves(opponent):
                if m2.to_col == tc and m2.to_row == tr:
                    opponent_captors.append(m2)
            if opponent_captors:
                print(f"  {BOLD}⚠️ 走子后本方可被对手吃掉!{RESET}")
                for m2 in opponent_captors:
                    captor = bad_board.get(m2.from_col, m2.from_row)
                    print(f"    对手 {piece_name(captor)} {move_str(m2)} 可吃{piece_name(piece_at_to)}")
        print()

    def _analyze_king_escapes(self, board: Board):
        """分析王的逃路"""
        king_pos = None
        for c in range(BOARD_COLS):
            for r in range(BOARD_ROWS):
                p = board.get(c, r)
                if (self.turn_color == Color.RED and p == PIECE_RED_KING) or \
                   (self.turn_color == Color.BLACK and p == PIECE_BLACK_KING):
                    king_pos = (c, r)
                    break

        if not king_pos:
            return

        kc, kr = king_pos
        palace = [(3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9),
                  (5, 7), (5, 8), (5, 9)]
        print(f"\n  王在 ({kc},{kr})，逃路分析:")
        for col, row in palace:
            if board.get(col, row) == PIECE_EMPTY:
                test = board.clone()
                king_piece = PIECE_RED_KING if self.turn_color == Color.RED else PIECE_BLACK_KING
                test.set(kc, kr, PIECE_EMPTY)
                test.set(col, row, king_piece)
                safe = not WinChecker(test).is_king_exposed(self.turn_color)
                print(f"    ({col},{row}): {'✅ 安全' if safe else '❌ 被攻击'}")
            elif (col, row) != (kc, kr):
                print(f"    ({col},{row}): 有棋子占用")

    # ---- 阶段 3: 合法着法分类 ----
    def classify_moves(self):
        """穷举所有合法着法并分类"""
        print(SEP)
        print(f"{BOLD}阶段 3: 着法分类{RESET}")
        print(SEP)

        mg = MoveGenerator(self.board)
        all_pseudo = list(mg.generate_all_moves(self.turn_color))

        # 过滤真正合法着法
        legal_moves = []
        illegal_moves = 0
        for m in all_pseudo:
            test = self.board.clone()
            p = test.get(m.from_col, m.from_row)
            test.set(m.from_col, m.from_row, PIECE_EMPTY)
            test.set(m.to_col, m.to_row, p)
            if not WinChecker(test).is_king_exposed(self.turn_color):
                legal_moves.append(m)
            else:
                illegal_moves += 1

        print(f"伪合法着法: {len(all_pseudo)} (其中 {illegal_moves} 个送将无效)")
        print(f"真正合法着法: {len(legal_moves)}")

        # 如果有威胁着法，分类为 能被将死/能防御
        if self.threat_move:
            losing = []
            defending = []
            fc, fr, tc, tr = self.threat_move
            for m in legal_moves:
                test = self.board.clone()
                p = test.get(m.from_col, m.from_row)
                test.set(m.from_col, m.from_row, PIECE_EMPTY)
                test.set(m.to_col, m.to_row, p)

                # 对手执行威胁
                threat = test.clone()
                # 找威胁棋子（可能因我方走棋而位置改变）
                for c in range(BOARD_COLS):
                    for r in range(BOARD_ROWS):
                        opp_piece = threat.get(c, r)
                        is_opp = (self.turn_color == Color.RED and opp_piece >= 10) or \
                                 (self.turn_color == Color.RED and opp_piece < 10)
                        # 简化：查找对手任意炮/车等能走到目标位置的
                        # 这里需要更精确的匹配，但不妨先用原始威胁棋子
                        pass

                # 如果威胁仍然有效（对手仍能将死）
                wc2 = WinChecker(test)
                if wc2.is_king_exposed(self.turn_color) and wc2.is_checkmate(self.turn_color):
                    losing.append(m)
                else:
                    defending.append(m)

            print(f"\n  ✅ 能防御: {len(defending)} 个")
            for m in defending[:10]:
                print(f"     {move_str(m)}")
            if len(defending) > 10:
                print(f"     ... 等 {len(defending)} 个")

            print(f"\n  ❌ 被将死: {len(losing)} 个")
            for m in losing[:10]:
                print(f"     {move_str(m)}")
            if len(losing) > 10:
                print(f"     ... 等 {len(losing)} 个")

            self.defending_moves = defending
            self.losing_moves = losing
        else:
            self.defending_moves = []
            self.losing_moves = []
            # 只打印前几个合法着法
            print(f"\n合法着法示例:")
            for m in legal_moves[:15]:
                print(f"  {move_str(m)}")
            if len(legal_moves) > 15:
                print(f"  ... 等 {len(legal_moves)} 个")

        self.legal_moves = legal_moves
        print()

    # ---- 阶段 4: AI 搜索引擎分析 ----
    def analyze_ai_engine(self, depths=None, time_ms_list=None):
        """
        多种配置运行 AI 引擎分析
        """
        print(SEP)
        print(f"{BOLD}阶段 4: AI 引擎搜索分析{RESET}")
        print(SEP)

        if depths is None:
            depths = [4, 5, 6]
        if time_ms_list is None:
            time_ms_list = [5000, 8000, 15000]

        # 确保 time_ms_list 长度匹配 depths
        if len(time_ms_list) < len(depths):
            time_ms_list = time_ms_list + [time_ms_list[-1]] * (len(depths) - len(time_ms_list))

        opponent = Color.BLACK if self.turn_color == Color.RED else Color.RED

        for depth, tms in zip(depths, time_ms_list):
            ai = ChessAI(depth=depth, use_iterative_deepening=True, max_time_ms=tms)
            start = time.time()
            result = ai.best_move(self.board.clone(), self.turn_color,
                                  depth=depth, max_time_ms=tms)
            elapsed = time.time() - start

            ai_move = result.move
            ai_str = move_str(ai_move) if ai_move else "None"

            # 分类 AI 的着法
            tag = self._classify_ai_move(ai_move)

            print(f"\n  深度={depth}, {tms}ms:")
            print(f"    着法  : {ai_str}")
            print(f"    评分  : {result.score:.0f}")
            print(f"    深度  : {result.depth}")
            print(f"    节点  : {result.nodes_searched}")
            print(f"    耗时  : {result.time_ms:.0f}ms (实际 {elapsed:.2f}s)")
            print(f"    将杀? : {result.is_checkmate}")
            print(f"    分类  : {tag}")

            self.ai_results[(depth, tms)] = {
                'move': ai_move,
                'move_str': ai_str,
                'score': result.score,
                'depth': result.depth,
                'nodes': result.nodes_searched,
                'time_ms': result.time_ms,
                'elapsed': elapsed,
                'is_checkmate': result.is_checkmate,
                'tag': tag,
            }

        # ---- 难度级别测试 ----
        print(f"\n  各难度级别 (max 8000ms):")
        for diff in [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD, Difficulty.EXPERT]:
            start = time.time()
            move = get_ai_move(self.board.clone(), self.turn_color,
                               difficulty=diff, max_time_ms=8000)
            elapsed = time.time() - start
            mstr = move_str(move) if move else "None"
            tag = self._classify_ai_move(move)
            print(f"    {diff.name:8s}: {mstr}  {tag} ({elapsed:.1f}s)")

        print()

    def _classify_ai_move(self, ai_move) -> str:
        """将 AI 着法分类标签"""
        if ai_move is None:
            return "❌ None"

        # 是否等于 bad_move
        if self.bad_move:
            bfc, bfr, btc, btr = self.bad_move
            if (ai_move.from_col == bfc and ai_move.from_row == bfr and
                    ai_move.to_col == btc and ai_move.to_row == btr):
                return "❌ 等于用户报告的坏着"

        # 是否等于 good_move
        if self.good_move:
            gfc, gfr, gtc, gtr = self.good_move
            if (ai_move.from_col == gfc and ai_move.from_row == gfr and
                    ai_move.to_col == gtc and ai_move.to_row == gtr):
                return "✅ 等于用户期望的好着"

        # 是否在防御列表 / 将被将死列表
        if hasattr(self, 'defending_moves'):
            for m in self.defending_moves:
                if (ai_move.from_col == m.from_col and ai_move.from_row == m.from_row and
                        ai_move.to_col == m.to_col and ai_move.to_row == m.to_row):
                    return "✅ 能防御威胁"
        if hasattr(self, 'losing_moves'):
            for m in self.losing_moves:
                if (ai_move.from_col == m.from_col and ai_move.from_row == m.from_row and
                        ai_move.to_col == m.to_col and ai_move.to_row == m.to_row):
                    return "❌ 被将死(漏杀)"

        # 是否合法
        if hasattr(self, 'legal_moves'):
            for m in self.legal_moves:
                if (ai_move.from_col == m.from_col and ai_move.from_row == m.from_row and
                        ai_move.to_col == m.to_col and ai_move.to_row == m.to_row):
                    return "✅ 合法着法"

        return "⚠️ 未分类"

    # ---- 总结报告 ----
    def summarize(self):
        """输出结构化分析报告"""
        print(SEP)
        print(f"{BOLD}分析总结{RESET}")
        print(SEP)

        lines = []

        # 1. 威胁验证结论
        if self.threat_move:
            lines.append(f"1. 用户报告的威胁着法 {move_str(self.threat_move)}:")
            # 这里需要在 verify_threat 中保存结论
            lines.append(f"   (详见阶段 2 输出)")

        # 2. AI 搜索结果
        if self.ai_results:
            lines.append(f"2. AI 引擎搜索结果 ({len(self.ai_results)} 种配置):")
            for (depth, tms), info in self.ai_results.items():
                tag_symbol = "✅" if info['tag'].startswith('✅') else \
                             ("❌" if info['tag'].startswith('❌') else "⚠️")
                lines.append(f"   深度{depth}/{tms}ms: {info['move_str']} "
                             f"score={info['score']:.0f} nodes={info['nodes']} "
                             f"{info['elapsed']:.1f}s {tag_symbol}")

        # 3. 问题根因分析
        if self.bad_move:
            lines.append(f"3. 用户报告的错误着法: {self.bad_move_str}")
            found_bad = False
            for (depth, tms), info in self.ai_results.items():
                if info['tag'].startswith('❌ 等于用户报告的坏着'):
                    lines.append(f"   ⚠️ 新引擎在 深度{depth}/{tms}ms 仍选择此坏着")
                    found_bad = True
            if not found_bad:
                lines.append(f"   ✅ 新引擎在所有配置下均未选择此坏着")

        if self.good_move:
            found_good = False
            for (depth, tms), info in self.ai_results.items():
                if info['tag'].startswith('✅ 等于用户期望的好着'):
                    lines.append(f"   ✅ 深度{depth}/{tms}ms 正确选择了期望好着: {self.good_move_str}")
                    found_good = True
            if not found_good:
                lines.append(f"   ⚠️ 所有配置下均未选择用户期望好着: {self.good_move_str}")

        for line in lines:
            print(f"  {line}")
        print()

    def run_full_analysis(self):
        """运行完整分析流程"""
        self.analyze_position()
        self.verify_threat()
        self.classify_moves()
        self.analyze_ai_engine()
        self.summarize()


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='AI 引擎问题分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整分析（含威胁着法、坏着、好着）
  python tests/ai_engine_analyzer.py \\
      --fen "2bak1b2/4a4/c7r/N7p/9/9/P5r1P/R3BC3/4A1n2/3A1KB2 r - - 0 1" \\
      --bad-move "f7->g7" \\
      --good-move "f7->f8" \\
      --threat-move "a2->f2"

  # 只分析 FEN + 坏着
  python tests/ai_engine_analyzer.py \\
      --fen "<FEN>" \\
      --bad-move "h2->h0"

  # 只分析 FEN（基础局面评估）
  python tests/ai_engine_analyzer.py --fen "<FEN>"
        """
    )
    parser.add_argument('--fen', required=True, help='局面的 FEN 字符串')
    parser.add_argument('--bad-move', default=None, help='AI 的错误着法，如 f7->g7')
    parser.add_argument('--good-move', default=None, help='期望的正确着法，如 f7->f8')
    parser.add_argument('--threat-move', default=None, help='对手的威胁/杀棋着法，如 a2->f2')
    parser.add_argument('--depths', default='4,5,6', help='搜索深度列表，逗号分隔 (默认: 4,5,6)')
    parser.add_argument('--times', default='5000,8000,15000',
                        help='时间限制列表(ms)，逗号分隔 (默认: 5000,8000,15000)')

    args = parser.parse_args()

    depths = [int(x.strip()) for x in args.depths.split(',')]
    times = [int(x.strip()) for x in args.times.split(',')]

    analyzer = AIEngineAnalyzer(
        fen=args.fen,
        bad_move_str=args.bad_move,
        good_move_str=args.good_move,
        threat_move_str=args.threat_move,
    )
    analyzer.analyze_position()
    analyzer.verify_threat()
    analyzer.classify_moves()
    analyzer.analyze_ai_engine(depths=depths, time_ms_list=times)
    analyzer.summarize()


if __name__ == '__main__':
    main()
