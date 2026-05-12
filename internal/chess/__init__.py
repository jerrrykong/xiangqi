"""Chinese Chess (Xiangqi) core game logic."""
from .piece import (
    Board,
    Piece,
    EMPTY_PIECE,
    create_initial_board,
    board_from_array,
    board_to_fen,
    PIECE_EMPTY,
    PIECE_RED_KING, PIECE_RED_ADVISOR, PIECE_RED_BISHOP, PIECE_RED_KNIGHT,
    PIECE_RED_ROOK, PIECE_RED_CANNON, PIECE_RED_PAWN,
    PIECE_BLACK_KING, PIECE_BLACK_ADVISOR, PIECE_BLACK_BISHOP, PIECE_BLACK_KNIGHT,
    PIECE_BLACK_ROOK, PIECE_BLACK_CANNON, PIECE_BLACK_PAWN,
    Color,
    PieceType,
)
from shared.protocol import Move
from .move_generator import (
    MoveGenerator,
    LegalMove,
    generate_moves,
    generate_checking_moves,
    count_moves,
)
from .move_validator import (
    MoveValidator,
    validate_move,
    validate_and_execute,
)
from .win_checker import (
    WinChecker,
    GameOverResult,
    check_game_over,
    is_king_exposed,
    is_checkmate,
    is_stalemate,
)

__version__ = "0.1.0"

__all__ = [
    # Piece and Board
    "Board",
    "Piece",
    "Move",
    "EMPTY_PIECE",
    "create_initial_board",
    "board_from_array",
    "board_to_fen",
    "PIECE_EMPTY",
    "PIECE_RED_KING", "PIECE_RED_ADVISOR", "PIECE_RED_BISHOP", "PIECE_RED_KNIGHT",
    "PIECE_RED_ROOK", "PIECE_RED_CANNON", "PIECE_RED_PAWN",
    "PIECE_BLACK_KING", "PIECE_BLACK_ADVISOR", "PIECE_BLACK_BISHOP", "PIECE_BLACK_KNIGHT",
    "PIECE_BLACK_ROOK", "PIECE_BLACK_CANNON", "PIECE_BLACK_PAWN",
    "Color",
    "PieceType",
    # Move Generator
    "MoveGenerator",
    "LegalMove",
    "generate_moves",
    "generate_checking_moves",
    "count_moves",
    # Move Validator
    "MoveValidator",
    "validate_move",
    "validate_and_execute",
    # Win Checker
    "WinChecker",
    "GameOverResult",
    "check_game_over",
    "is_king_exposed",
    "is_checkmate",
    "is_stalemate",
]
