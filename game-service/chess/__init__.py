"""Chinese Chess (Xiangqi) core game logic."""
from .constants import (
    Color,
    PieceType,
    PIECE_EMPTY,
    PIECE_RED_KING, PIECE_RED_ADVISOR, PIECE_RED_BISHOP, PIECE_RED_KNIGHT,
    PIECE_RED_ROOK, PIECE_RED_CANNON, PIECE_RED_PAWN,
    PIECE_BLACK_KING, PIECE_BLACK_ADVISOR, PIECE_BLACK_BISHOP, PIECE_BLACK_KNIGHT,
    PIECE_BLACK_ROOK, PIECE_BLACK_CANNON, PIECE_BLACK_PAWN,
    Difficulty,
    GameResult,
    WinReason,
)
from .move import Move
from .piece import (
    Board,
    Piece,
    EMPTY_PIECE,
    create_initial_board,
    board_from_array,
    board_to_fen,
)
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
from .game import (
    ChessGame,
    GamePhase,
    GameState,
    MoveRecord,
)
from .recorder import (
    GameRecorder,
    ZobristHasher,
    RepetitionState,
)

__version__ = "0.2.0"

__all__ = [
    # Constants
    "Color",
    "PieceType",
    "PIECE_EMPTY",
    "PIECE_RED_KING", "PIECE_RED_ADVISOR", "PIECE_RED_BISHOP", "PIECE_RED_KNIGHT",
    "PIECE_RED_ROOK", "PIECE_RED_CANNON", "PIECE_RED_PAWN",
    "PIECE_BLACK_KING", "PIECE_BLACK_ADVISOR", "PIECE_BLACK_BISHOP", "PIECE_BLACK_KNIGHT",
    "PIECE_BLACK_ROOK", "PIECE_BLACK_CANNON", "PIECE_BLACK_PAWN",
    "Difficulty",
    "GameResult",
    "WinReason",
    # Move
    "Move",
    # Piece and Board
    "Board",
    "Piece",
    "EMPTY_PIECE",
    "create_initial_board",
    "board_from_array",
    "board_to_fen",
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
    # Game State Machine
    "ChessGame",
    "GamePhase",
    "GameState",
    "MoveRecord",
    # Recorder
    "GameRecorder",
    "ZobristHasher",
    "RepetitionState",
]
