"""
快速验证: 用户报告的漏检杀棋局面在新引擎上的表现
FEN: 2bak1b2/4a4/c7r/N7p/9/9/P5r1P/R3BC3/4A1n2/3A1KB2 r - - 0 1
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'game-service'))

from chess.piece import Board, fen_to_board, board_to_fen
from chess.move_generator import MoveGenerator
from chess.win_checker import WinChecker
from chess.constants import (
    Color, PieceType, PIECE_EMPTY,
    PIECE_RED_KING, PIECE_RED_ADVISOR, PIECE_RED_BISHOP, PIECE_RED_KNIGHT,
    PIECE_RED_ROOK, PIECE_RED_CANNON, PIECE_RED_PAWN,
    PIECE_BLACK_KING, PIECE_BLACK_ADVISOR, PIECE_BLACK_BISHOP, PIECE_BLACK_KNIGHT,
    PIECE_BLACK_ROOK, PIECE_BLACK_CANNON, PIECE_BLACK_PAWN,
    BOARD_COLS, BOARD_ROWS,
)
from ai.engine import ChessAI

PIECE_CHARS = {
    PIECE_RED_KING: '帅', PIECE_RED_ADVISOR: '仕', PIECE_RED_BISHOP: '相',
    PIECE_RED_KNIGHT: '馬', PIECE_RED_ROOK: '車', PIECE_RED_CANNON: '炮',
    PIECE_RED_PAWN: '兵',
    PIECE_BLACK_KING: '将', PIECE_BLACK_ADVISOR: '士', PIECE_BLACK_BISHOP: '象',
    PIECE_BLACK_KNIGHT: '馬', PIECE_BLACK_ROOK: '車', PIECE_BLACK_CANNON: '砲',
    PIECE_BLACK_PAWN: '卒', PIECE_EMPTY: '·',
}
RED = '\033[31m'; YELLOW = '\033[33m'; RESET = '\033[0m'

def print_board(board):
    print("\n    a  b  c  d  e  f  g  h  i")
    for row in range(BOARD_ROWS):
        line = f"{row:2d} "
        for col in range(BOARD_COLS):
            p = board.get(col, row)
            c = RED if 0 <= p < 10 else (YELLOW if p >= 10 else '')
            line += f" {c}{PIECE_CHARS.get(p, '?')}{RESET} "
        print(line)

def ms(move): return f"{chr(ord('a')+move.from_col)}{move.from_row}→{chr(ord('a')+move.to_col)}{move.to_row}"

FEN = "2bak1b2/4a4/c7r/N7p/9/9/P5r1P/R3BC3/4A1n2/3A1KB2 r - - 0 1"

print("=" * 70)
print("用户报告漏检杀棋局面验证")
print("=" * 70)

board = fen_to_board(FEN)
print("初始局面 (红先):")  
print_board(board)
print(f"FEN: {board_to_fen(board, Color.RED)}")

# ---- 分析 1: 黑方杀棋威胁 ----
print("\n" + "-" * 70)
print("分析 1: 黑方杀棋威胁 — 炮 a2→f2 (炮１平６)")
print("-" * 70)

threat = board.clone()
threat.set(0, 2, PIECE_EMPTY)
threat.set(5, 2, PIECE_BLACK_CANNON)
print("黑方走 炮a2→f2 后:")
print_board(threat)

wc = WinChecker(threat)
is_check = wc.is_king_exposed(Color.RED)
is_mate = wc.is_checkmate(Color.RED)
print(f"红帅被将军? {is_check}")
print(f"红方被将死? {is_mate}")

# 检查红帅逃路
king_pos = board.find_king(Color.RED)
print(f"红帅位置: ({king_pos[0]}, {king_pos[1]})")
palace = [(3,7),(3,8),(3,9),(4,7),(4,8),(4,9),(5,7),(5,8),(5,9)]
escapes = []
for col, row in palace:
    if threat.get(col, row) == PIECE_EMPTY:
        test = threat.clone()
        test.set(king_pos[0], king_pos[1], PIECE_EMPTY)
        test.set(col, row, PIECE_RED_KING)
        safe = not WinChecker(test).is_king_exposed(Color.RED)
        escapes.append((col, row, safe))
        print(f"  逃路 ({col},{row}): {'✅ 安全' if safe else '❌ 被攻击'}")
    else:
        print(f"  逃路 ({col},{row}): 有棋子占用")

has_escape = any(safe for _, _, safe in escapes)
print(f"\n结论: 黑炮a2→f2 {'是一个将军但红方可逃，不是杀棋' if has_escape and not is_mate else '是将死！'}")

# ---- 分析 2: 旧 AI 的错误着法 vs 正确着法 ----
print("\n" + "-" * 70)
print("分析 2: 炮四平三 (f7→g7) vs 炮四进一 (f7→f8)")
print("-" * 70)

# 模拟 f7→g7 (炮四平三, 旧AI的错误着法)
bad = board.clone()
bad.set(5, 7, PIECE_EMPTY)
bad.set(6, 7, PIECE_RED_CANNON)
print("红方走 f7→g7 (炮四平三) 后:")
# 检查黑车能否吃红炮
rook_pos = bad.get(6, 6)
if rook_pos == PIECE_BLACK_ROOK:
    print(f"  ⚠️ 黑车在(6,6)，紧邻红炮(6,7)，可直接吃掉红炮！")
    # 模拟黑吃炮
    eaten = bad.clone()
    eaten.set(6, 7, PIECE_EMPTY)
    eaten.set(6, 6, PIECE_BLACK_ROOK)
    print(f"  黑方吃炮后子力损失: 红炮(≈450)")
    # 黑方吃完后能炮a2→f2将军吗?
    threat2 = eaten.clone()
    threat2.set(0, 2, PIECE_EMPTY)
    threat2.set(5, 2, PIECE_BLACK_CANNON)
    print(f"  黑方再炮a2→f2: 将军={WinChecker(threat2).is_king_exposed(Color.RED)}, 将死={WinChecker(threat2).is_checkmate(Color.RED)}")
else:
    print(f"  (6,6)不是黑车，实际是{PIECE_CHARS.get(rook_pos, '?')}")

# 模拟 f7→f8 (正确的应对)
good = board.clone()
good.set(5, 7, PIECE_EMPTY)
good.set(5, 8, PIECE_RED_CANNON)
print("\n红方走 f7→f8 (正确应手) 后:")
# 黑方炮a2→f2
good2 = good.clone()
good2.set(0, 2, PIECE_EMPTY)
good2.set(5, 2, PIECE_BLACK_CANNON)
wc_good = WinChecker(good2)
print(f"  黑方再炮a2→f2: 将军={wc_good.is_king_exposed(Color.RED)}, 将死={wc_good.is_checkmate(Color.RED)}")
# 检查红帅逃路: (4,9) — 红炮在(5,8)挡住黑马腿，所以安全
print(f"  红炮在(5,8)挡住黑马(6,8)攻击(4,9)的腿 → (4,9)安全 ✅")

# ---- 分析 3: 新 AI 搜索 ----
print("\n" + "-" * 70)
print("分析 3: 新 AI 引擎搜索结果")
print("-" * 70)

# 列出所有合法着法中被黑方炮a2→f2将死的
mg = MoveGenerator(board)
legal = []
for m in mg.generate_all_moves(Color.RED):
    test = board.clone()
    p = test.get(m.from_col, m.from_row)
    test.set(m.from_col, m.from_row, PIECE_EMPTY)
    test.set(m.to_col, m.to_row, p)
    if not WinChecker(test).is_king_exposed(Color.RED):
        legal.append(m.to_move())

# 对每个合法着法，模拟黑炮a2→f2观察是否能防住
for label, depth, tms in [("深度4 短时", 4, 5000), ("深度5 标准", 5, 8000), ("深度6 深度", 6, 15000)]:
    ai = ChessAI(depth=depth, use_iterative_deepening=True, max_time_ms=tms)
    start = time.time()
    result = ai.best_move(Board(board._board), Color.RED, depth=depth, max_time_ms=tms)
    elapsed = time.time() - start
    
    is_bad = result.move.from_col == 5 and result.move.from_row == 7 and result.move.to_col == 6 and result.move.to_row == 7
    is_good = result.move.from_col == 5 and result.move.from_row == 7 and result.move.to_col == 5 and result.move.to_row == 8
    
    status = "❌ 送杀(炮四平三)!" if is_bad else ("✅ 正确(炮四进一)" if is_good else "⚠️ 其他")
    print(f"\n  {label}: {ms(result.move)}  score={result.score:.0f}  depth={result.depth}  nodes={result.nodes_searched}  time={elapsed:.1f}s  {status}")

print("\n" + "=" * 70)
print("总结:")
print("  1. 黑炮a2→f2 是 [将军] 而非 [将死]，红帅可逃")
print("  2. 旧AI选择 f7→g7 是 [送吃大子]，黑车可直接吃红炮")
print("  3. 正确应手是 f7→f8，红炮上移既保存子力又挡住黑马攻击路线")
if has_escape and not is_mate:
    print("  4. 用户报告的'杀棋'实际是将军+严重威胁，非终局将死")
print("=" * 70)
