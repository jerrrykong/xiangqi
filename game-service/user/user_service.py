"""Game Service v2.0 - User Service

User business logic: profile, rankings, history, ELO calculation.
"""

import logging
from typing import Any, Optional

import asyncpg

from user.user_repository import UserRepository
from user.elo_repository import EloRepository

logger = logging.getLogger(__name__)


class UserService:
    """User business logic."""

    def __init__(self, user_repo: UserRepository, elo_repo: EloRepository):
        self.user_repo = user_repo
        self.elo_repo = elo_repo

    async def get_user_info(self, user_id: int) -> Optional[dict]:
        """Get user info with rating data."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None

        elo = await self.elo_repo.get_by_user_id(user_id)

        return {
            "id": user["id"],
            "username": user["username"],
            "nickname": user.get("nickname", ""),
            "avatar": user.get("avatar", ""),
            "is_admin": user.get("is_admin", False),
            "is_banned": user.get("is_banned", False),
            "created_at": str(user.get("created_at", "")),
            "rating": elo["rating"] if elo else 1500,
            "games_count": elo["games_count"] if elo else 0,
        }

    async def update_profile(self, user_id: int, data: dict) -> Optional[dict]:
        """Update user profile (nickname, avatar)."""
        nickname = data.get("nickname")
        avatar = data.get("avatar")

        user = await self.user_repo.update_profile(user_id, nickname=nickname, avatar=avatar)
        if not user:
            return None

        return {
            "nickname": user.get("nickname", ""),
            "avatar": user.get("avatar", ""),
        }

    async def get_rankings(self, page: int = 1, page_size: int = 20) -> dict:
        """Get ELO rankings."""
        rows, total = await self.elo_repo.get_rankings(page, page_size)

        rankings = []
        for i, row in enumerate(rows):
            offset = (page - 1) * page_size
            rankings.append({
                "rank": offset + i + 1,
                "user_id": row["user_id"],
                "username": row.get("username", ""),
                "nickname": row.get("nickname", ""),
                "rating": row["rating"],
                "games_count": row["games_count"],
            })

        return {
            "rankings": rankings,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_history(self, user_id: int, page: int = 1, page_size: int = 20,
                          game_type: Optional[str] = None) -> dict:
        """Get game history for a user."""
        rows, total = await self.user_repo.get_game_history(user_id, page, page_size, game_type)

        games = []
        for row in rows:
            is_red = row["red_user_id"] == user_id
            opponent_id = row["black_user_id"] if is_red else row["red_user_id"]

            # Determine result from user's perspective
            winner = row.get("winner", "")
            if winner == "red":
                result = "win" if is_red else "loss"
            elif winner == "black":
                result = "loss" if is_red else "win"
            else:
                result = "draw"

            games.append({
                "game_id": row["id"],
                "room_id": str(row["room_id"]),
                "room_type": row.get("room_type", ""),
                "result": result,
                "side": "red" if is_red else "black",
                "opponent_id": opponent_id,
                "total_moves": row.get("total_moves", 0),
                "start_time": str(row.get("start_time", "")),
                "end_time": str(row.get("end_time", "")),
            })

        return {
            "games": games,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def calculate_elo(rating_a: int, rating_b: int, result: float,
                      games_a: int) -> tuple[int, int]:
        """Calculate ELO rating changes.

        Args:
            rating_a: Player A's current rating
            rating_b: Player B's current rating
            result: 1.0 for A wins, 0.0 for B wins, 0.5 for draw
            games_a: Player A's total game count (for K-factor)

        Returns:
            (change_a, change_b) - rating changes for both players
        """
        # K-factor strategy
        K = 40
        if games_a > 100:
            K = 10
        elif games_a > 30:
            K = 20

        # Expected score
        EA = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))

        # Rating change
        change_a = int(K * (result - EA))
        change_b = -change_a

        return change_a, change_b
