"""Game Service v2.0 - Database Layer - Connection Pool

Manages asyncpg connection pool with convenient query methods.
"""

import logging
from typing import Any, Optional

import asyncpg

from config import DatabaseConfig

logger = logging.getLogger(__name__)


class Database:
    """Asyncpg database connection pool manager."""

    def __init__(self, config: DatabaseConfig):
        self._config = config
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Initialize the connection pool."""
        logger.info(
            f"Connecting to database: {self._config.host}:{self._config.port}/{self._config.dbname}"
        )
        self._pool = await asyncpg.create_pool(
            dsn=self._config.dsn,
            min_size=self._config.min_pool_size,
            max_size=self._config.max_pool_size,
        )
        logger.info("Database connection pool initialized")

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("Database connection pool closed")

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool. Must call connect() first."""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Execute a query and return all rows."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        """Execute a query and return one row."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any, column: int = 0) -> Any:
        """Execute a query and return a single value."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args, column=column)

    async def execute_many(self, query: str, args_list: list[tuple]) -> None:
        """Execute a query with multiple argument sets in a transaction."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(query, args_list)
