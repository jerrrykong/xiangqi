"""Shared pytest fixtures."""
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def empty_board():
    """Empty board fixture"""
    from internal.chess import PIECE_EMPTY, board_from_array
    return board_from_array([[PIECE_EMPTY] * 9 for _ in range(10)])


@pytest.fixture
def initial_board():
    """Initial board fixture"""
    from internal.chess import create_initial_board
    return create_initial_board()


@pytest.fixture
def red_king_only_board():
    """Board with only red king"""
    from internal.chess import PIECE_EMPTY, PIECE_RED_KING, board_from_array
    arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
    arr[9][4] = PIECE_RED_KING
    return board_from_array(arr)


@pytest.fixture
def kings_only_board():
    """Board with only kings"""
    from internal.chess import PIECE_EMPTY, PIECE_RED_KING, PIECE_BLACK_KING, board_from_array
    arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
    arr[9][4] = PIECE_RED_KING
    arr[0][4] = PIECE_BLACK_KING
    return board_from_array(arr)


@pytest.fixture
def check_position_board():
    """Board in check position"""
    from internal.chess import PIECE_EMPTY, PIECE_RED_KING, PIECE_BLACK_ROOK, board_from_array
    arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
    arr[9][4] = PIECE_RED_KING
    arr[8][4] = PIECE_BLACK_ROOK  # Checking
    return board_from_array(arr)


@pytest.fixture
def simple_checkmate_board():
    """Simple checkmate position"""
    from internal.chess import PIECE_EMPTY, PIECE_RED_KING, PIECE_RED_ROOK, PIECE_RED_PAWN, PIECE_BLACK_ROOK, board_from_array
    arr = [[PIECE_EMPTY] * 9 for _ in range(10)]
    arr[9][4] = PIECE_RED_KING
    arr[8][3] = PIECE_BLACK_ROOK
    arr[8][5] = PIECE_BLACK_ROOK
    arr[9][3] = PIECE_RED_ROOK  # Block one side
    arr[9][5] = PIECE_RED_PAWN   # Block other side
    return board_from_array(arr)
