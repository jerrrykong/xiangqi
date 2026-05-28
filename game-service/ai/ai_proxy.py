"""Game Service v2.0 - AI Proxy

Async wrapper for the synchronous ChessAI engine.
Uses asyncio.to_thread() to avoid blocking the event loop.
"""

import asyncio
import logging
import time
from typing import Optional

from chess.constants import Color, Difficulty
from chess.move import Move
from chess.piece import Board
from ai.engine import ChessAI
from ai.difficulty import get_difficulty_config, get_search_depth, get_max_time_ms

logger = logging.getLogger(__name__)


class AIProxy:
    """Async proxy for the ChessAI engine.

    Wraps the synchronous ChessAI.best_move() call in asyncio.to_thread()
    to prevent blocking the event loop during AI computation.
    """

    def __init__(self):
        self._ai = ChessAI()

    async def get_best_move(
        self,
        board: Board,
        current_turn: Color,
        difficulty: int = 3,
        max_time_ms: Optional[int] = None,
    ) -> Optional[Move]:
        """Get the best move from the AI engine asynchronously.

        Args:
            board: Current board state (2D list of piece encodings)
            current_turn: Current player color
            difficulty: Difficulty level (1-5)
            max_time_ms: Override max think time (None = use difficulty default)

        Returns:
            Move object or None if no move available
        """
        config = get_difficulty_config(difficulty)
        depth = config.depth
        time_limit = max_time_ms if max_time_ms is not None else config.max_time_ms

        start_time = time.time()
        logger.info(
            f"AI thinking: difficulty={difficulty}, depth={depth}, "
            f"time_limit={time_limit}ms, turn={current_turn}"
        )

        try:
            result = await asyncio.to_thread(
                self._ai.best_move,
                board=board,
                turn=current_turn,
                depth=depth,
                max_time_ms=time_limit,
            )
            # best_move returns SearchResult, extract the Move
            move = result.move if result else None
        except Exception as e:
            logger.error(f"AI engine error: {e}", exc_info=True)
            return None

        elapsed_ms = int((time.time() - start_time) * 1000)
        if move:
            logger.info(
                f"AI move: {move} (elapsed={elapsed_ms}ms, depth={depth})"
            )
        else:
            logger.warning(f"AI returned no move (elapsed={elapsed_ms}ms)")

        return move
