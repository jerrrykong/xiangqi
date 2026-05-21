"""Game Service v2.0 - Auth Service

Authentication business logic: login, register.
"""

import logging
from typing import Optional

import asyncpg

import bcrypt
from user.user_repository import UserRepository
from user.elo_repository import EloRepository

logger = logging.getLogger(__name__)


class AuthService:
    """Handles login and registration business logic."""

    def __init__(self, user_repo: UserRepository, elo_repo: EloRepository):
        self.user_repo = user_repo
        self.elo_repo = elo_repo

    async def login(self, username: str, password: str) -> Optional[asyncpg.Record]:
        """Login verification.

        Returns user record on success, None on failure.
        """
        user = await self.user_repo.get_by_username(username)
        if not user:
            return None

        # Verify password
        try:
            if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                return None
        except Exception as e:
            logger.warning(f"Password check error for user {username}: {e}")
            return None

        # Check if banned
        if user.get("is_banned", False):
            return None

        # Update last login time
        await self.user_repo.update_last_login(user["id"])

        # Get ELO rating
        elo = await self.elo_repo.get_by_user_id(user["id"])

        # Return user with rating info (as a dict-like record)
        return user

    async def register(self, username: str, password: str,
                       nickname: str = "") -> Optional[asyncpg.Record]:
        """Register a new user.

        Returns user record on success, None on failure.
        """
        # Validate username uniqueness
        if await self.user_repo.exists_username(username):
            return None

        # Password strength validation
        if len(password) < 8:
            return None
        if not any(c.isdigit() for c in password):
            return None
        if not any(c.isalpha() for c in password):
            return None

        # Username format validation
        if len(username) < 3:
            return None

        # Hash password
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        # Create user
        user = await self.user_repo.create(
            username=username,
            password_hash=password_hash,
            nickname=nickname or username,
        )

        if user is None:
            return None

        # Create ELO rating record (default 1500)
        await self.elo_repo.create(user["id"], rating=1500)

        return user
