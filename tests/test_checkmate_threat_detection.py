"""
测试 AI 是否能检测到黑方 炮１平６ 的杀棋威胁并生成合理应手。

局面 FEN: 2bak1b2/4a4/c7r/N7p/9/9/P5r1P/R3BC3/4A1n2/3A1KB2 r - - 0 1

红方走棋。黑方威胁 炮(0,2)→(5,2)，利用红炮(5,7)作炮架将军红帅(5,9)。
红帅逃路受限，黑马(6,8)可攻红帅逃路(4,9)，构成严重威胁。

用户报告: AI 走了 炮四平三 (cannon from col5 to col6)，未发现杀棋。
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'game-service'))

from chess.piece import Board, fen_to_board, board_to_fen
from chess.move_generator import MoveGenerator
from chess.win_checker import WinChecker
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


def move_str(move) -> str:
    return f"{chr(ord('a')+move.from_col)}{move.from_row}→{chr(ord('a')+move.to_col)}{move.to_row}"


FEN = "2bak1b2/4a4/c7r/N7p/9/9/P5r1P/R3BC3/4A1n2/3A1KB2 r - - 0 1"


# ============================================================
# TEST 1: 解析局面并分析黑方杀棋威胁
# ============================================================
def test_threat_analysis():
    """
    阶段 1: 解析 FEN 局面，分析黑方 炮１平６ 杀棋威胁
    
    黑方威胁: 炮(0,2)→(5,2) 平到红帅(5,9)的正上方
              利用红炮(5,7)作炮架，将军红帅
              
    验证: 如果红方不应对（随便走一步非防御棋），黑方是否能完成将杀？
    """
    print("=" * 60)
    print("TEST 1: 局面分析与杀棋威胁验证")
    print("=" * 60)

    board = fen_to_board(FEN)
    print("当前局面 (红先, Red to move):")
    print_board(board)

    # 验证棋子位置
    assert board.get(0, 2) == PIECE_BLACK_CANNON, f"黑炮应在(0,2), 实际为{board.get(0,2)}"
    assert board.get(5, 9) == PIECE_RED_KING, f"红帅应在(5,9), 实际为{board.get(5,9)}"
    assert board.get(5, 7) == PIECE_RED_CANNON, f"红炮应在(5,7), 实际为{board.get(5,7)}"
    assert board.get(6, 8) == PIECE_BLACK_KNIGHT, f"黑马应在(6,8), 实际为{board.get(6,8)}"
    print("✓ 棋子位置验证通过")

    # --- 模拟黑方杀棋威胁: 炮(0,2)→(5,2) ---
    print("\n--- 模拟黑方杀棋威胁: 炮 a2→f2 (炮１平６) ---")
    threat_board = board.clone()
    # 执行黑炮平中
    cannon_piece = threat_board.get(0, 2)
    threat_board.set(0, 2, PIECE_EMPTY)
    threat_board.set(5, 2, cannon_piece)

    print("黑方走 炮a2→f2 后局面:")
    print_board(threat_board)

    wc = WinChecker(threat_board)
    black_is_exposed = wc.is_king_exposed(Color.RED)
    red_has_legal = wc.has_legal_moves(Color.RED)
    red_is_mate = wc.is_checkmate(Color.RED)

    print(f"红帅被将军? {black_is_exposed}")
    print(f"红方有合法着法? {red_has_legal}")
    print(f"红方被将死? {red_is_mate}")

    # 详细分析红帅的逃路
    if black_is_exposed:
        print("\n红帅逃路分析:")
        # 红帅在(5,9)，可逃到 palace (col 3-5, row 7-9) 的空位
        king_positions = [(3,9), (4,9), (3,8), (5,8), (4,8)]
        for col, row in king_positions:
            if 3 <= col <= 5 and 7 <= row <= 9:
                piece_at = threat_board.get(col, row)
                if piece_at == PIECE_EMPTY:
                    # 模拟帅移到这里
                    test_b = threat_board.clone()
                    test_b.set(5, 9, PIECE_EMPTY)
                    test_b.set(col, row, PIECE_RED_KING)
                    wc2 = WinChecker(test_b)
                    is_safe = not wc2.is_king_exposed(Color.RED)
                    print(f"  ({col},{row}): 空位 → {'安全' if is_safe else '被攻击(不安全)'}")
                else:
                    char = PIECE_CHARS.get(piece_at, '?')
                    side = '红' if piece_at < 10 else '黑'
                    print(f"  ({col},{row}): 有{side}{char} → 无法移动")

    return black_is_exposed and not red_is_mate  # 应该被将军但未将死（因为还有其他防御手段）


# ============================================================
# TEST 2: 检查红方有哪些合法着法能防御杀棋
# ============================================================
def test_red_defenses():
    """
    阶段 2: 找出红方所有合法着法，并标记哪些能防御杀棋
    """
    print("\n" + "=" * 60)
    print("TEST 2: 红方防御着法分析")
    print("=" * 60)

    board = fen_to_board(FEN)
    mg = MoveGenerator(board)

    # 先找红方所有伪合法着法
    all_moves = list(mg.generate_all_moves(Color.RED))
    print(f"红方伪合法着法总数: {len(all_moves)}")

    # 过滤出真正合法的（红方走棋后帅不被将）
    legal_moves = []
    for move in all_moves:
        test_board = board.clone()
        piece = test_board.get(move.from_col, move.from_row)
        test_board.set(move.from_col, move.from_row, PIECE_EMPTY)
        test_board.set(move.to_col, move.to_row, piece)

        wc = WinChecker(test_board)
        if not wc.is_king_exposed(Color.RED):
            legal_moves.append(move)

    print(f"红方真正合法着法: {len(legal_moves)}")

    # 对每个合法着法，模拟黑方走 炮a2→f2，检查红方是否会被将死
    print("\n--- 红方应手 vs 黑方杀棋威胁 (炮a2→f2) ---")
    defending_moves = []
    losing_moves = []

    for move in legal_moves:
        # 红方走棋
        test_board = board.clone()
        piece = test_board.get(move.from_col, move.from_row)
        test_board.set(move.from_col, move.from_row, PIECE_EMPTY)
        test_board.set(move.to_col, move.to_row, piece)

        # 黑方走 炮a2→f2 杀棋
        # 找到黑炮的位置（可能因红方走棋而变了）
        black_cannon_positions = []
        for col in range(BOARD_COLS):
            for row in range(BOARD_ROWS):
                if test_board.get(col, row) == PIECE_BLACK_CANNON:
                    black_cannon_positions.append((col, row))

        # 模拟每个黑炮走 a2→f2 (如果还能走的话)
        # 原黑炮在(0,2)，如果红方走了会影响
        can_defend = True
        for bc_col, bc_row in black_cannon_positions:
            # 检查黑炮能否平到 f 路 (col=5)
            threat_board = test_board.clone()
            if threat_board.get(5, bc_row) == PIECE_EMPTY:
                threat_board.set(bc_col, bc_row, PIECE_EMPTY)
                threat_board.set(5, bc_row, PIECE_BLACK_CANNON)
                wc = WinChecker(threat_board)
                if wc.is_checkmate(Color.RED):
                    can_defend = False
                    break

        if can_defend:
            defending_moves.append(move)
        else:
            losing_moves.append(move)

    print(f"能防御杀棋的着法: {len(defending_moves)}")
    for m in defending_moves[:10]:
        print(f"  ✅ {move_str(m)}")
    if len(defending_moves) > 10:
        print(f"  ... 共 {len(defending_moves)} 个")

    print(f"\n会被将死的着法: {len(losing_moves)}")
    for m in losing_moves[:10]:
        print(f"  ❌ {move_str(m)}")
    if len(losing_moves) > 10:
        print(f"  ... 共 {len(losing_moves)} 个")

    return len(defending_moves) > 0


# ============================================================
# TEST 3: AI 搜索 - 是否正确检测杀棋并生成应手
# ============================================================
def test_ai_threat_detection():
    """
    阶段 3: AI 搜索此局面，检查:
    1. 是否检测到黑方杀棋威胁（评分是否反映危险）
    2. 是否选择了防御着法而非送吃着法
    3. 不应该选择 炮四平三 (炮(5,7)→(6,7)) 这种送杀着法
    """
    print("\n" + "=" * 60)
    print("TEST 3: AI 杀棋检测与应手生成")
    print("=" * 60)

    board = fen_to_board(FEN)

    # 找出会被将死的着法（作为对比）
    mg = MoveGenerator(board)
    all_moves = list(mg.generate_all_moves(Color.RED))
    legal_moves = []
    for move in all_moves:
        test_board = board.clone()
        piece = test_board.get(move.from_col, move.from_row)
        test_board.set(move.from_col, move.from_row, PIECE_EMPTY)
        test_board.set(move.to_col, move.to_row, piece)
        wc = WinChecker(test_board)
        if not wc.is_king_exposed(Color.RED):
            legal_moves.append(move)

    # 分类着法
    losing_to_threat = []
    defending = []
    for move in legal_moves:
        test_board = board.clone()
        piece = test_board.get(move.from_col, move.from_row)
        test_board.set(move.from_col, move.from_row, PIECE_EMPTY)
        test_board.set(move.to_col, move.to_row, piece)

        # 模拟黑方杀棋
        threat_board = test_board.clone()
        # 找黑炮
        for col in range(BOARD_COLS):
            for row in range(BOARD_ROWS):
                if threat_board.get(col, row) == PIECE_BLACK_CANNON:
                    if threat_board.get(5, row) == PIECE_EMPTY:
                        threat_board.set(col, row, PIECE_EMPTY)
                        threat_board.set(5, row, PIECE_BLACK_CANNON)
                        wc = WinChecker(threat_board)
                        if wc.is_checkmate(Color.RED):
                            losing_to_threat.append(move)
                        break
            else:
                continue
            break

    defending = [m for m in legal_moves if m not in losing_to_threat]

    print(f"红方合法着法: {len(legal_moves)}")
    print(f"  可防御: {len(defending)} 个")
    print(f"  被将死: {len(losing_to_threat)} 个")

    bad_move = "f7→g7"  # 炮四平三 在坐标上对应 (5,7)→(6,7)
    # Red notation: 四=col5, 三=col6
    print(f"\n用户报告的 AI 错误着法: {bad_move} (炮四平三)")
    print(f"检查此着法是否属于[被将死]类别...")

    is_bad_move_losing = False
    for m in losing_to_threat:
        if m.from_col == 5 and m.from_row == 7 and m.to_col == 6 and m.to_row == 7:
            is_bad_move_losing = True
            break

    if is_bad_move_losing:
        print(f"  ✅ 确认: {bad_move} 走完后黑方炮a2→f2 可将死红方")
    else:
        print(f"  ⚠️ 意外: {bad_move} 不在被将死列表中")
        # 手动验证
        test_board = board.clone()
        piece = test_board.get(5, 7)
        test_board.set(5, 7, PIECE_EMPTY)
        test_board.set(6, 7, piece)

        threat_board = test_board.clone()
        # 找黑炮
        for col in range(BOARD_COLS):
            for row in range(BOARD_ROWS):
                if threat_board.get(col, row) == PIECE_BLACK_CANNON:
                    if threat_board.get(5, row) == PIECE_EMPTY:
                        threat_board.set(col, row, PIECE_EMPTY)
                        threat_board.set(5, row, PIECE_BLACK_CANNON)
                        wc = WinChecker(threat_board)
                        is_mate = wc.is_checkmate(Color.RED)
                        is_exposed = wc.is_king_exposed(Color.RED)
                        print(f"  手动验证: is_king_exposed(Red)={is_exposed}, is_checkmate(Red)={is_mate}")

    # --- AI 搜索 ---
    print(f"\n--- AI 搜索 (深度 5, HARD, 最大 8000ms) ---")
    start = time.time()
    ai = ChessAI(depth=5, use_iterative_deepening=True, max_time_ms=8000)
    result = ai.best_move(board, Color.RED, depth=5, max_time_ms=8000)
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

    # 检查 AI 选择是否在防御列表中
    is_defending = any(
        ai_move.from_col == m.from_col and ai_move.from_row == m.from_row
        and ai_move.to_col == m.to_col and ai_move.to_row == m.to_row
        for m in defending
    )
    is_losing = any(
        ai_move.from_col == m.from_col and ai_move.from_row == m.from_row
        and ai_move.to_col == m.to_col and ai_move.to_row == m.to_row
        for m in losing_to_threat
    )
    is_same_bad_move = (ai_move.from_col == 5 and ai_move.from_row == 7
                        and ai_move.to_col == 6 and ai_move.to_row == 7)

    print(f"\n评估 AI 着法:")
    print(f"  是否防御着法? {is_defending}")
    print(f"  是否被将死者法? {is_losing}")
    print(f"  是否等于炮四平三? {is_same_bad_move}")

    if is_losing or is_same_bad_move:
        print(f"\n❌ FAIL: AI 仍然选择了送杀着法 {ai_str}!")
        print(f"   这意味着 AI 没有检测到黑方炮a2→f2的杀棋威胁")
        print(f"   建议: 检查 _is_king_attacked_by 和 quiescence 搜索是否正确覆盖此情况")
        return False
    elif is_defending:
        print(f"\n✅ PASS: AI 正确选择了防御着法 {ai_str}")
        return True
    else:
        print(f"\n⚠️ WARN: AI 选择了 {ai_str}，不在任何已知类别中")
        return None


# ============================================================
# TEST 4: 深度搜索测试（增加时间/深度看能否找到）
# ============================================================
def test_deeper_search():
    """
    阶段 4: 增加深度和时间进行搜索
    """
    print("\n" + "=" * 60)
    print("TEST 4: 深度搜索 - 深度 6, 15000ms")
    print("=" * 60)

    board = fen_to_board(FEN)

    start = time.time()
    ai = ChessAI(depth=6, use_iterative_deepening=True, max_time_ms=15000)
    result = ai.best_move(board, Color.RED, depth=6, max_time_ms=15000)
    elapsed = time.time() - start

    ai_move = result.move
    ai_str = move_str(ai_move) if ai_move else "None"
    print(f"AI 选择 : {ai_str}")
    print(f"评分    : {result.score:.0f}")
    print(f"深度    : {result.depth}")
    print(f"节点    : {result.nodes_searched}")
    print(f"耗时    : {result.time_ms:.0f}ms (实际 {elapsed:.2f}s)")
    print(f"将杀?   : {result.is_checkmate}")

    # 重新计算防御/送死者法
    board2 = fen_to_board(FEN)
    mg = MoveGenerator(board2)
    all_moves = list(mg.generate_all_moves(Color.RED))
    legal_moves = []
    for move in all_moves:
        test_board = board2.clone()
        piece = test_board.get(move.from_col, move.from_row)
        test_board.set(move.from_col, move.from_row, PIECE_EMPTY)
        test_board.set(move.to_col, move.to_row, piece)
        wc = WinChecker(test_board)
        if not wc.is_king_exposed(Color.RED):
            legal_moves.append(move)

    losing_to_threat = []
    defending = []
    for move in legal_moves:
        test_board = board2.clone()
        piece = test_board.get(move.from_col, move.from_row)
        test_board.set(move.from_col, move.from_row, PIECE_EMPTY)
        test_board.set(move.to_col, move.to_row, piece)

        for col in range(BOARD_COLS):
            for row in range(BOARD_ROWS):
                if test_board.get(col, row) == PIECE_BLACK_CANNON:
                    threat_board = test_board.clone()
                    if threat_board.get(5, row) == PIECE_EMPTY:
                        threat_board.set(col, row, PIECE_EMPTY)
                        threat_board.set(5, row, PIECE_BLACK_CANNON)
                        wc = WinChecker(threat_board)
                        if wc.is_checkmate(Color.RED):
                            losing_to_threat.append(move)
                        break
                    break
            else:
                continue
            break

    defending = [m for m in legal_moves if m not in losing_to_threat]

    if ai_move is None:
        print("❌ FAIL: AI 返回 None")
        return False

    is_defending = any(
        ai_move.from_col == m.from_col and ai_move.from_row == m.from_row
        and ai_move.to_col == m.to_col and ai_move.to_row == m.to_row
        for m in defending
    )
    is_losing = any(
        ai_move.from_col == m.from_col and ai_move.from_row == m.from_row
        and ai_move.to_col == m.to_col and ai_move.to_row == m.to_row
        for m in losing_to_threat
    )

    print(f"\n评估: 防御={is_defending}, 送杀={is_losing}")
    if is_losing:
        print("❌ FAIL: 深度搜索仍未检测到杀棋")
        return False
    elif is_defending:
        print("✅ PASS: 深度搜索正确选择了防御着法")
    else:
        print("⚠️ WARN: 着法不在已知类别中")

    return True


# ============================================================
# TEST 5: 多难度级别测试
# ============================================================
def test_all_difficulties():
    """
    阶段 5: 测试所有难度级别
    """
    print("\n" + "=" * 60)
    print("TEST 5: 各难度级别杀棋检测")
    print("=" * 60)

    board = fen_to_board(FEN)
    print()

    all_pass = True
    for diff in [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD, Difficulty.EXPERT]:
        start = time.time()
        move = get_ai_move(board, Color.RED, difficulty=diff, max_time_ms=8000)
        elapsed = time.time() - start

        if move is None:
            print(f"  {diff.name:8s}: ❌ 返回 None ({elapsed:.1f}s)")
            all_pass = False
            continue

        mstr = move_str(move)
        is_bad = (move.from_col == 5 and move.from_row == 7
                  and move.to_col == 6 and move.to_row == 7)
        status = "❌ 送杀" if is_bad else "⚠️ (需验证)"
        print(f"  {diff.name:8s}: {mstr}  {status} ({elapsed:.1f}s)")
        if is_bad:
            all_pass = False

    return all_pass


if __name__ == '__main__':
    results = [
        ('局面分析与威胁验证', test_threat_analysis()),
        ('红方防御着法分析', test_red_defenses()),
        ('AI 杀棋检测与应手', test_ai_threat_detection()),
        ('深度搜索测试', test_deeper_search()),
        ('多难度级别测试', test_all_difficulties()),
    ]

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    for name, passed in results:
        if passed is True:
            status = "✅ PASS"
        elif passed is False:
            status = "❌ FAIL"
        else:
            status = "⚠️ WARN"
        print(f"  {name}: {status}")

    all_pass = all(r is True for r in results)
    print(f"\n总结果: {'✅ 全部通过' if all_pass else '❌ 存在失败，需修复'}")
    sys.exit(0 if all_pass else 1)
