"""Game Service v2.0 - Room & Game Repository

Handles database operations for rooms and game_history tables.
SQL strictly matches actual database schema.
"""

import logging
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)


class RoomRepository:
    """Rooms table data access with asyncpg."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def create(self, room_id: str, room_type: str, source: str = "manual",
                     created_by: int = 0, difficulty: Optional[int] = None) -> asyncpg.Record:
        """Create a new room. Returns the created room record."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """INSERT INTO rooms (id, type, source, status, created_by, difficulty)
                   VALUES ($1, $2, $3, 'waiting', $4, $5)
                   RETURNING *""",
                room_id, room_type, source, created_by, difficulty,
            )

    async def get_by_id(self, room_id: str) -> Optional[asyncpg.Record]:
        """Get room by ID."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM rooms WHERE id = $1", room_id,
            )

    async def get_by_id_with_users(self, room_id: str) -> Optional[asyncpg.Record]:
        """Get room by ID with player usernames."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """SELECT r.*,
                          ru.username as red_username, ru.nickname as red_nickname,
                          bu.username as black_username, bu.nickname as black_nickname
                   FROM rooms r
                   LEFT JOIN users ru ON ru.id = r.red_user_id
                   LEFT JOIN users bu ON bu.id = r.black_user_id
                   WHERE r.id = $1""",
                room_id,
            )

    async def update_status(self, room_id: str, status: str) -> None:
        """Update room status."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE rooms SET status = $1 WHERE id = $2", status, room_id,
            )

    async def join_room(self, room_id: str, user_id: int, side: str) -> None:
        """Add a player to the room on the specified side."""
        if side == "red":
            field = "red_user_id"
        else:
            field = "black_user_id"

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"UPDATE rooms SET {field} = $1 WHERE id = $2",
                user_id, room_id,
            )

    async def set_ready(self, room_id: str, side: str, ready: bool = True) -> None:
        """Set a player's ready status."""
        if side == "red":
            field = "red_ready"
        else:
            field = "black_ready"

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"UPDATE rooms SET {field} = $1 WHERE id = $2",
                ready, room_id,
            )

    async def start_game(self, room_id: str) -> None:
        """Mark room as playing with started_at timestamp."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE rooms SET status = 'playing', started_at = CURRENT_TIMESTAMP WHERE id = $1",
                room_id,
            )

    async def finish_game(self, room_id: str, winner: str, result: int) -> None:
        """Mark room as finished with result."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """UPDATE rooms
                   SET status = 'finished', winner = $2,
                       ended_at = CURRENT_TIMESTAMP
                   WHERE id = $1""",
                room_id, winner,
            )

    async def get_user_current_room(self, user_id: int) -> Optional[asyncpg.Record]:
        """Get the room a user is currently in (waiting/playing)."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """SELECT * FROM rooms
                   WHERE (red_user_id = $1 OR black_user_id = $1)
                     AND status IN ('waiting', 'playing')
                   LIMIT 1""",
                user_id,
            )

    async def get_waiting_rooms(self, page: int = 1, page_size: int = 20,
                                room_type: Optional[str] = None) -> tuple[list[asyncpg.Record], int]:
        """Get list of waiting rooms with player info."""
        async with self._pool.acquire() as conn:
            conditions = ["status = 'waiting'", "red_user_id IS NOT NULL"]
            params: list[Any] = []
            idx = 1

            if room_type:
                conditions.append(f"type = ${idx}")
                params.append(room_type)
                idx += 1

            where = f"WHERE {' AND '.join(conditions)}"

            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM rooms {where}", *params,
            )

            offset = (page - 1) * page_size
            rows = await conn.fetch(
                f"""SELECT r.*,
                           ru.username as red_username, ru.nickname as red_nickname
                    FROM rooms r
                    LEFT JOIN users ru ON ru.id = r.red_user_id
                    {where}
                    ORDER BY r.created_at DESC
                    LIMIT ${idx} OFFSET ${idx + 1}""",
                *params, page_size, offset,
            )

            return rows, total

    async def leave_room(self, room_id: str, user_id: int) -> None:
        """Handle a player leaving the room.

        Red player leaving → delete room.
        Black player leaving → set black_user_id to NULL, reset status.
        """
        room = await self.get_by_id(room_id)
        if not room:
            return

        async with self._pool.acquire() as conn:
            if room["red_user_id"] == user_id:
                # Red player (creator) leaving → delete room
                await conn.execute("DELETE FROM rooms WHERE id = $1", room_id)
            elif room["black_user_id"] == user_id:
                # Black player leaving → reset
                await conn.execute(
                    """UPDATE rooms
                       SET black_user_id = NULL, status = 'waiting'
                       WHERE id = $1""",
                    room_id,
                )

    async def is_user_in_room(self, user_id: int) -> bool:
        """Check if user is currently in an active room."""
        async with self._pool.acquire() as conn:
            count = await conn.fetchval(
                """SELECT COUNT(*) FROM rooms
                   WHERE (red_user_id = $1 OR black_user_id = $1)
                     AND status IN ('waiting', 'playing')""",
                user_id,
            )
            return count > 0

    async def get_active_rooms(self) -> list[asyncpg.Record]:
        """Get all active rooms (waiting/playing)."""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM rooms WHERE status IN ('waiting', 'playing')",
            )

    async def save_game_state(self, room_id: str, moves_json: list[dict],
                               metadata: Optional[dict] = None) -> None:
        """Save game state (moves + metadata) for room persistence."""
        import json
        async with self._pool.acquire() as conn:
            await conn.execute(
                """UPDATE rooms SET moves_json = $2, metadata = $3 WHERE id = $1""",
                room_id, json.dumps(moves_json), json.dumps(metadata) if metadata else None,
            )

    async def get_active_rooms_with_state(self) -> list[asyncpg.Record]:
        """Get all active rooms with full state data (moves_json, metadata)."""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                """SELECT r.*, 
                          ru.username as red_username, ru.nickname as red_nickname,
                          bu.username as black_username, bu.nickname as black_nickname
                   FROM rooms r
                   LEFT JOIN users ru ON ru.id = r.red_user_id
                   LEFT JOIN users bu ON bu.id = r.black_user_id
                   WHERE r.status IN ('waiting', 'playing')""",
            )

    async def delete(self, room_id: str) -> None:
        """Delete a room."""
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM rooms WHERE id = $1", room_id)


class GameRepository:
    """Game history table data access with asyncpg."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def create(self, room_id: str, winner: str, result: int,
                     total_moves: int, start_time, end_time,
                     pve_level: Optional[int] = None,
                     red_user_id: Optional[int] = None,
                     black_user_id: Optional[int] = None) -> asyncpg.Record:
        """Create a game history record."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """INSERT INTO game_history
                   (room_id, winner, result, total_moves, start_time, end_time,
                    pve_level, red_user_id, black_user_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                   RETURNING *""",
                room_id, winner, result, total_moves, start_time, end_time,
                pve_level, red_user_id, black_user_id,
            )

    async def get_by_id(self, game_id: int) -> Optional[asyncpg.Record]:
        """Get game by ID."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM game_history WHERE id = $1", game_id,
            )

    async def get_by_room_id(self, room_id: str) -> Optional[asyncpg.Record]:
        """Get game by room ID."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM game_history WHERE room_id = $1", room_id,
            )

    async def get_user_history(self, user_id: int, page: int = 1,
                               page_size: int = 20) -> tuple[list[asyncpg.Record], int]:
        """Get game history for a user."""
        async with self._pool.acquire() as conn:
            total = await conn.fetchval(
                """SELECT COUNT(*) FROM game_history
                   WHERE red_user_id = $1 OR black_user_id = $1""",
                user_id,
            )

            offset = (page - 1) * page_size
            rows = await conn.fetch(
                """SELECT * FROM game_history
                   WHERE red_user_id = $1 OR black_user_id = $1
                   ORDER BY end_time DESC
                   LIMIT $2 OFFSET $3""",
                user_id, page_size, offset,
            )

            return rows, total

    async def get_total_games_count(self) -> int:
        """Get total games count."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM game_history")

    async def get_today_games_count(self) -> int:
        """Get today's games count."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM game_history WHERE DATE(end_time) = CURRENT_DATE",
            )


class ModelRepository:
    """Model versions table data access with asyncpg."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def list_models(self) -> list[asyncpg.Record]:
        """List all model versions."""
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM model_versions ORDER BY created_at DESC",
            )

    async def get_latest_active(self) -> Optional[asyncpg.Record]:
        """Get the latest deployed model version."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """SELECT * FROM model_versions
                   WHERE status = 'deployed'
                   ORDER BY created_at DESC LIMIT 1""",
            )

    async def set_active(self, model_id: int) -> None:
        """Set a model as deployed, mark all others as not deployed."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE model_versions SET status = 'trained' WHERE status = 'deployed'",
                )
                await conn.execute(
                    "UPDATE model_versions SET status = 'deployed' WHERE id = $1",
                    model_id,
                )
