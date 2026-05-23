"""Game Service v2.0 - User Repository

Handles all database operations for users table.
Mirrors Go UserRepository with asyncpg.
"""

import logging
from datetime import datetime
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)


class UserRepository:
    """User table data access with asyncpg."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def create(self, username: str, password_hash: str, nickname: str = "",
                     avatar: str = "", is_admin: bool = False) -> asyncpg.Record:
        """Create a new user. Returns the created user record."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """INSERT INTO users (username, password_hash, nickname, avatar, is_admin)
                   VALUES ($1, $2, $3, $4, $5)
                   RETURNING *""",
                username, password_hash, nickname, avatar, is_admin,
            )

    async def get_by_id(self, user_id: int) -> Optional[asyncpg.Record]:
        """Get user by ID."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1", user_id,
            )

    async def get_by_username(self, username: str) -> Optional[asyncpg.Record]:
        """Get user by username."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE username = $1", username,
            )

    async def update(self, user_id: int, **fields) -> Optional[asyncpg.Record]:
        """Update user fields. Returns updated record."""
        if not fields:
            return await self.get_by_id(user_id)

        set_clauses = []
        values = []
        idx = 1
        for key, value in fields.items():
            set_clauses.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1

        values.append(user_id)
        query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *"

        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *values)

    async def update_last_login(self, user_id: int) -> None:
        """Update user's last login timestamp."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = $1",
                user_id,
            )

    async def update_profile(self, user_id: int, nickname: Optional[str] = None,
                             avatar: Optional[str] = None) -> Optional[asyncpg.Record]:
        """Update user profile fields."""
        fields = {}
        if nickname is not None:
            fields["nickname"] = nickname
        if avatar is not None:
            fields["avatar"] = avatar
        return await self.update(user_id, **fields)

    async def set_banned(self, user_id: int, banned: bool) -> None:
        """Set user banned status."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_banned = $1 WHERE id = $2",
                banned, user_id,
            )

    async def list_users(self, page: int = 1, page_size: int = 20,
                         search: Optional[str] = None) -> tuple[list[asyncpg.Record], int]:
        """List users with optional search. Returns (users, total_count)."""
        async with self._pool.acquire() as conn:
            conditions = []
            params = []
            idx = 1

            if search:
                conditions.append(f"username LIKE ${idx}")
                params.append(f"%{search}%")
                idx += 1

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM users {where}", *params,
            )

            offset = (page - 1) * page_size
            rows = await conn.fetch(
                f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
                *params, page_size, offset,
            )

            return rows, total

    async def exists_username(self, username: str) -> bool:
        """Check if username already exists."""
        async with self._pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE username = $1", username,
            )
            return count > 0

    async def get_user_count(self) -> int:
        """Get total user count."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM users")

    async def get_game_history(self, user_id: int, page: int = 1, page_size: int = 20,
                               game_type: Optional[str] = None) -> tuple[list[asyncpg.Record], int]:
        """Get game history for a user."""
        async with self._pool.acquire() as conn:
            conditions = ["(gh.red_user_id = $1 OR gh.black_user_id = $1)"]
            params: list[Any] = [user_id]
            idx = 2

            if game_type:
                conditions.append(f"r.type = ${idx}")
                params.append(game_type)
                idx += 1

            where = f"WHERE {' AND '.join(conditions)}"

            total = await conn.fetchval(
                f"""SELECT COUNT(*)
                    FROM game_history gh
                    LEFT JOIN rooms r ON r.id = gh.room_id
                    {where}""",
                *params,
            )

            offset = (page - 1) * page_size
            rows = await conn.fetch(
                f"""SELECT gh.*, r.type as room_type
                    FROM game_history gh
                    LEFT JOIN rooms r ON r.id = gh.room_id
                    {where}
                    ORDER BY gh.end_time DESC
                    LIMIT ${idx} OFFSET ${idx + 1}""",
                *params, page_size, offset,
            )

            return rows, total
