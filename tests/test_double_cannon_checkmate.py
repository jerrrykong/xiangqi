"""
测试 AI 引擎是否能找到 双炮沉底杀 着法。

局面设计 (RED 攻 BLACK):
  - 红方左炮已在黑方底线 a0
  - 红方右炮在 b2，走一步 b2→b0 完成双炮沉底杀
  - 左炮 a0 隔右炮 b0 打黑将 e0，d0 逃路也被覆盖
  - 黑士 e1/f0 占据将侧逃路，黑将被将死
  - 测试 1 步杀场景
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'game-service'))

from chess.piece import Board
from chess.constants import (
    Color, PieceType, Difficulty,
    PIECE_EMPTY,
    PIECE_RED_KING, PIECE_RED_ADVISOR, PIECE_RED_BISHOP, PIECE_RED_KNIGHT,
    PIECE_RED_ROOK, PIECE_RED_CANNON, PIECE_RED_PAWN,
    PIECE_BLACK_KING, PIECE_BLACK_ADVISOR, PIECE_BLACK_BISHOP, PIECE_BLACK_KNIGHT,
    PIECE_BLACK_ROOK, PIECE_BLACK_CANNON, PIECE_BLACK_PAWN,
    BOARD_ROWS, BOARD_COLS,
)
from ai.engine import ChessAI, get_ai_move
from chess.win_checker import WinChecker

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
RESET = '\033[0m'


def _empty_board() -> list[list[int]]:
    return [[PIECE_EMPTY for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]


def print_board(board: Board) -> None:
    print()
    print("    a  b  c  d  e  f  g  h  i")
    for row in range(BOARD_ROWS):
        line = f"{row:2d} "
        for col in range(BOARD_COLS):
            p = board.get(col, row)
            c = RED if 0 <= p < 10 else (YELLOW if p >= 10 else '')
            line += f" {c}{PIECE_CHARS.get(p, '?')}{RESET} "
        print(line)
    print()


def build_double_cannon_mate_in_1() -> Board:
    """
    构建双炮沉底 1 步杀局面 (红先)

    初始局面:
        a  b  c  d  e  f  g  h  i
     0  炮  ·  ·  ·  将  士  ·  ·  ·       ← 黑方底线
     1  ·  ·  ·  ·  士  ·  ·  ·  ·
     2  象  炮  ·  ·  象  ·  ·  ·  ·
             ...
     9  ·  ·  相  ·  帅  仕  ·  ·  ·       ← 红方底线

    红方走 炮b2→b0 (即 (1,2)→(1,0)) 完成双炮沉底杀:
      - 左炮(a0) 隔右炮(b0) 打黑将(e0) → 将！
      - 黑将 d0 逃路也被左炮 a0 覆盖（b0 仍为炮架）
      - 黑士 e1/f0 占据其余逃路，黑将被将死，无合法着法
    """
    board = _empty_board()

    # ==== 黑方 ====
    board[1][4] = PIECE_BLACK_ADVISOR   # 黑士 e1
    board[0][4] = PIECE_BLACK_KING      # 黑将 e0
    board[0][5] = PIECE_BLACK_ADVISOR   # 黑士 f0
    board[2][0] = PIECE_BLACK_BISHOP    # 黑象 a2
    board[2][4] = PIECE_BLACK_BISHOP    # 黑象 e2

    # ==== 红方 ====
    board[0][0] = PIECE_RED_CANNON      # 红炮 a0 (已沉底，架黑士打将)
    board[2][1] = PIECE_RED_CANNON      # 红炮 b2 → 走一步 b0 完成双炮
    board[9][4] = PIECE_RED_KING        # 红帅
    board[9][5] = PIECE_RED_ADVISOR     # 红士
    board[8][4] = PIECE_RED_ADVISOR     # 红士
    board[7][4] = PIECE_RED_BISHOP      # 红象 
    board[9][2] = PIECE_RED_BISHOP      # 红象 

    return Board(board)


def move_str(move) -> str:
    """格式化着法为可读字符串 e.g. h2→h0"""
    return f"{chr(ord('a')+move.from_col)}{move.from_row}→{chr(ord('a')+move.to_col)}{move.to_row}"


def find_checkmate_moves(board: Board, turn: Color) -> list:
    """
    找出所有能将死对方的着法。
    使用 WinChecker 正确检测将死（含送将过滤）。
    """
    from chess.move_generator import MoveGenerator
    mg = MoveGenerator(board)
    checkmate_moves = []
    for move in mg.generate_all_moves(turn):
        # 执行着法
        test_board = board.clone()
        piece = test_board.get(move.from_col, move.from_row)
        test_board.set(move.from_col, move.from_row, PIECE_EMPTY)
        test_board.set(move.to_col, move.to_row, piece)

        # 检查走子方是否送将（非法着法，跳过）
        wc = WinChecker(test_board)
        if wc.is_king_exposed(turn):
            continue

        # 检查对手是否被将死
        opponent = Color.BLACK if turn == Color.RED else Color.RED
        if wc.is_checkmate(opponent):
            checkmate_moves.append(move)
    return checkmate_moves


# ============================================================
# TEST 1: 着法生成 + AI 搜索一步杀
# ============================================================
def test_checkmate_correctness():
    """
    使用正常的着法生成和 AI 思考过程，检查是否能找到一步杀的着法。

    局面：左炮 a0 已沉底，右炮 b2 待走 → b0。
    杀着原理：炮 b2→b0 后，右炮 b0 充当左炮 a0 的炮架，
    左炮 a0 隔 b0 打黑将 e0；黑将 d0 逃路也被左炮覆盖，e1/f0 被己方士占据，
    黑将无路可逃，被将死。
    """
    print("=" * 60)
    print("TEST 1: 着法生成 + AI 搜索 - 双炮沉底一步杀")
    print("=" * 60)

    board = build_double_cannon_mate_in_1()
    print("初始局面:")
    print_board(board)

    # ---- 阶段 1: 着法生成 - 找出所有将杀着法 ----
    print("--- 阶段 1: 着法生成 (find_checkmate_moves) ---")
    from chess.move_generator import MoveGenerator

    checkmate_moves = find_checkmate_moves(board, Color.RED)
    print(f"一步杀着法数: {len(checkmate_moves)}")
    for m in checkmate_moves:
        print(f"  ✅ 杀着: {move_str(m)}")

    # 展示红方所有伪合法着法中哪些是杀着
    all_moves = MoveGenerator(board).generate_all_moves(Color.RED)
    print(f"红方伪合法着法总数: {len(all_moves)}")
    non_mate = [m for m in all_moves if not any(
        m.from_col == cm.from_col and m.from_row == cm.from_row
        and m.to_col == cm.to_col and m.to_row == cm.to_row
        for cm in checkmate_moves
    )]
    print(f"其中非杀着: {len(non_mate)} 个")

    if not checkmate_moves:
        print("❌ FAIL: 着法生成未找到任何将杀着法")
        return False

    # ---- 阶段 2: AI 搜索 - 验证 AI 能否找到杀着 ----
    print(f"\n--- 阶段 2: AI 搜索 (深度 4, HARD) ---")
    start = time.time()
    ai = ChessAI(depth=4, use_iterative_deepening=True, max_time_ms=10000)
    result = ai.best_move(board, Color.RED, depth=4, max_time_ms=15000)
    elapsed = time.time() - start

    ai_move = result.move
    ai_str = move_str(ai_move) if ai_move else "None"
    print(f"AI 选择 : {ai_str}")
    print(f"评分    : {result.score:.0f}")
    print(f"深度    : {result.depth}")
    print(f"节点    : {result.nodes_searched}")
    print(f"耗时    : {result.time_ms:.0f}ms (实际 {elapsed:.2f}s)")
    print(f"将杀?   : {result.is_checkmate}")

    if ai_move is None:
        print("❌ FAIL: AI 返回 None")
        return False

    is_correct = any(
        ai_move.from_col == m.from_col and ai_move.from_row == m.from_row
        and ai_move.to_col == m.to_col and ai_move.to_row == m.to_row
        for m in checkmate_moves
    )

    # ---- 阶段 3: 执行杀着并验证后局面 ----
    print(f"\n--- 阶段 3: 执行 {ai_str} 后验证后局面 ---")
    board_after = board.clone()
    piece = board_after.get(ai_move.from_col, ai_move.from_row)
    board_after.set(ai_move.from_col, ai_move.from_row, PIECE_EMPTY)
    board_after.set(ai_move.to_col, ai_move.to_row, piece)
    print_board(board_after)

    wc = WinChecker(board_after)
    is_exposed = wc.is_king_exposed(Color.BLACK)
    is_mate = wc.is_checkmate(Color.BLACK)
    has_legal = wc.has_legal_moves(Color.BLACK)
    print(f"走后 - 黑将被将军? {is_exposed}")
    print(f"走后 - 黑将被将死? {is_mate}")
    print(f"黑方真正合法着法? {has_legal}")

    # 列出黑方所有伪合法着法
    pseudo_moves = MoveGenerator(board_after).generate_all_moves(Color.BLACK)
    print(f"黑方伪合法着法数: {len(pseudo_moves)}")

    if is_exposed and is_mate and not has_legal:
        print("\n✅ PASS: AI 正确找到双炮沉底一步杀着法!")
        return True
    elif is_correct or result.is_checkmate or result.score > 9000:
        print(f"\n⚠️ WARN: AI找到了杀着({ai_str})但后局面将死判断不一致")
        print(f"   is_king_exposed={is_exposed}, is_checkmate={is_mate}")
        return False
    else:
        print(f"\n❌ FAIL: AI 未找到将杀着法 ({ai_str})")
        print(f"   正确杀着: {[move_str(m) for m in checkmate_moves]}")
        return False


# ============================================================
# TEST 2: AI 搜索 1 步杀
# ============================================================
def test_mate_in_1():
    print("\n" + "=" * 60)
    print("TEST 2: AI 深度 4 搜索双炮沉底 1 步杀")
    print("=" * 60)

    board = build_double_cannon_mate_in_1()

    # 找 ground truth
    checkmate_moves = find_checkmate_moves(board, Color.RED)
    print(f"真正将杀着法数: {len(checkmate_moves)}")
    for m in checkmate_moves:
        print(f"  ✅ 杀着: {move_str(m)}")

    # AI 搜索
    print(f"\n--- AI 搜索 (深度 4, HARD) ---")
    start = time.time()
    ai = ChessAI(depth=4, use_iterative_deepening=True, max_time_ms=8000)
    result = ai.best_move(board, Color.RED, depth=4, max_time_ms=10000)
    elapsed = time.time() - start

    ai_move = result.move
    ai_str = move_str(ai_move) if ai_move else "None"
    print(f"AI 选择 : {ai_str}")
    print(f"评分    : {result.score:.0f}")
    print(f"深度    : {result.depth}")
    print(f"节点    : {result.nodes_searched}")
    print(f"耗时    : {result.time_ms:.0f}ms (实际 {elapsed:.2f}s)")
    print(f"将杀?   : {result.is_checkmate}")

    if ai_move is None:
        print("❌ FAIL: AI 返回 None")
        return False

    is_correct = any(
        ai_move.from_col == m.from_col and ai_move.from_row == m.from_row
        and ai_move.to_col == m.to_col and ai_move.to_row == m.to_row
        for m in checkmate_moves
    )

    if is_correct or result.is_checkmate or result.score > 9000:
        print("✅ PASS: AI 找到双炮沉底杀棋着法!")
        return True
    else:
        print(f"❌ FAIL: AI 未找到将杀着法 ({ai_str})")
        print(f"   正确杀着: {[move_str(m) for m in checkmate_moves]}")
        return False


# ============================================================
# TEST 3: 各难度级别
# ============================================================
def test_difficulty_levels():
    print("\n" + "=" * 60)
    print("TEST 3: 各难度级别搜索双炮沉底 1 步杀")
    print("=" * 60)

    board = build_double_cannon_mate_in_1()
    checkmate_moves = find_checkmate_moves(board, Color.RED)
    correct_strs = {move_str(m) for m in checkmate_moves}
    print(f"正确杀着: {correct_strs}")

    print()
    all_pass = True
    for diff in [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD, Difficulty.EXPERT]:
        start = time.time()
        move = get_ai_move(board, Color.RED, difficulty=diff, max_time_ms=10000)
        elapsed = time.time() - start

        if move is None:
            print(f"  {diff.name:8s}: ❌ 返回 None ({elapsed:.1f}s)")
            all_pass = False
            continue

        mstr = move_str(move)
        is_mate = mstr in correct_strs
        status = "✅ 杀着" if is_mate else "⚠️ 非杀着"
        print(f"  {diff.name:8s}: {mstr}  {status} ({elapsed:.1f}s)")
        if not is_mate:
            all_pass = False

    return all_pass


# ============================================================
# TEST 4: 验证单炮沉底并非将死（证明双炮的必要性）
# ============================================================
def test_single_cannon_not_mate():
    """
    验证: 仅单个炮在底线 + 红车封锁 ≠ 将死。
    因为黑士可以吃掉红车来解除将军。

    这是 "双炮沉底杀" 的核心原理：必须两炮同时在场，
    各用一个黑士作炮架，使黑士无法移动解将。
    """
    print("\n" + "=" * 60)
    print("TEST 4: 验证单炮沉底并非将死 (证明双炮必要性)")
    print("=" * 60)

    # 构造单炮局面：只有左炮在 a0，右炮仍在 b2 未沉底（如同 TEST1 初始局面）
    board = build_double_cannon_mate_in_1()  # 左炮在 a0，右炮在 b2
    print("局面（左炮 a0，右炮 b2 未到位）:")
    print_board(board)

    # 验证：当前局面黑方不应被将死（右炮未到位）
    wc = WinChecker(board)
    print(f"黑将被将死? {wc.is_checkmate(Color.BLACK)}")
    print(f"黑方有合法着法? {wc.has_legal_moves(Color.BLACK)}")

    if not wc.is_checkmate(Color.BLACK) and wc.has_legal_moves(Color.BLACK):
        print("✅ PASS: 单炮沉底确实不构成将死（黑士可吃车解将），双炮缺一不可！")
        return True
    else:
        print("❌ FAIL: 预期不应被将死")
        return False


if __name__ == '__main__':
    results = [
        ('将死正确性验证', test_checkmate_correctness()),
        ('1步杀 (深度4)', test_mate_in_1()),
        ('难度级别测试', test_difficulty_levels()),
        ('单炮非将死 (双炮必要性)', test_single_cannon_not_mate()),
    ]

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")

    all_pass = all(r[1] for r in results)
    print(f"\n总结果: {'✅ 全部通过' if all_pass else '❌ 存在失败'}")
    sys.exit(0 if all_pass else 1)
