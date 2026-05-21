"""Game Service v2.0 - ELO Repository

Handles all database operations for elo_ratings and elo_history tables.
SQL strictly matches actual database schema.
"""

import logging
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


class EloRepository:
    """ELO ratings data access with asyncpg."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def create(self, user_id: int, rating: int = 1500) -> asyncpg.Record:
        """Create an ELO rating record for a user."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """INSERT INTO elo_ratings (user_id, rating, games_count)
                   VALUES ($1, $2, 0)
                   RETURNING *""",
                user_id, rating,
            )

    async def get_by_user_id(self, user_id: int) -> Optional[asyncpg.Record]:
        """Get ELO rating by user ID."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM elo_ratings WHERE user_id = $1", user_id,
            )

    async def update_rating(self, user_id: int, rating: int, games_count: int) -> Optional[asyncpg.Record]:
        """Update user's ELO rating and game count."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """UPDATE elo_ratings
                   SET rating = $2, games_count = $3, updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = $1
                   RETURNING *""",
                user_id, rating, games_count,
            )

    async def increment_games_count(self, user_id: int) -> None:
        """Increment user's games count."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE elo_ratings SET games_count = games_count + 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = $1",
                user_id,
            )

    async def get_rankings(self, page: int = 1, page_size: int = 20) -> tuple[list[asyncpg.Record], int]:
        """Get ELO rankings with user info. Returns (rankings, total_count)."""
        async with self._pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM elo_ratings")

            offset = (page - 1) * page_size
            rows = await conn.fetch(
                """SELECT elo_ratings.user_id, elo_ratings.rating,
                          elo_ratings.games_count,
                          users.username, users.nickname
                   FROM elo_ratings
                   LEFT JOIN users ON users.id = elo_ratings.user_id
                   ORDER BY elo_ratings.rating DESC
                   LIMIT $1 OFFSET $2""",
                page_size, offset,
            )

            return rows, total

    async def create_history(self, user_id: int, game_id: Optional[int],
                             rating: int, change: int) -> asyncpg.Record:
        """Create an ELO change history record."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """INSERT INTO elo_history (user_id, rating, change, game_id)
                   VALUES ($1, $2, $3, $4)
                   RETURNING *""",
                user_id, rating, change, game_id,
            )

    async def get_history(self, user_id: int, page: int = 1,
                          page_size: int = 20) -> tuple[list[asyncpg.Record], int]:
        """Get ELO change history for a user."""
        async with self._pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM elo_history WHERE user_id = $1", user_id,
            )

            offset = (page - 1) * page_size
            rows = await conn.fetch(
                """SELECT * FROM elo_history
                   WHERE user_id = $1
                   ORDER BY created_at DESC
                   LIMIT $2 OFFSET $3""",
                user_id, page_size, offset,
            )

            return rows, total

    async def get_or_create(self, user_id: int, rating: int = 1500) -> asyncpg.Record:
        """Get ELO rating or create if not exists."""
        record = await self.get_by_user_id(user_id)
        if record is None:
            record = await self.create(user_id, rating)
        return record
