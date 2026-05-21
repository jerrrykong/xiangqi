"""Game Service v2.0 - Admin Service

Admin business logic: user management, stats, model management.
"""

import logging
from typing import Optional

from room.room_repository import RoomRepository, GameRepository, ModelRepository
from user.user_repository import UserRepository

logger = logging.getLogger(__name__)


class AdminService:
    """Admin business logic."""

    def __init__(self, user_repo: UserRepository, room_repo: RoomRepository,
                 game_repo: GameRepository, model_repo: ModelRepository,
                 online_count_func):
        self.user_repo = user_repo
        self.room_repo = room_repo
        self.game_repo = game_repo
        self.model_repo = model_repo
        self._online_count_func = online_count_func

    async def list_users(self, page: int = 1, page_size: int = 20,
                         search: Optional[str] = None) -> dict:
        """List users with optional search."""
        rows, total = await self.user_repo.list_users(page, page_size, search)

        users = []
        for row in rows:
            users.append({
                "id": row["id"],
                "username": row["username"],
                "nickname": row.get("nickname", ""),
                "is_admin": row.get("is_admin", False),
                "is_banned": row.get("is_banned", False),
                "created_at": str(row.get("created_at", "")),
                "last_login_at": str(row.get("last_login_at", "")),
            })

        return {
            "users": users,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def ban_user(self, user_id: int, banned: bool,
                       reason: str = "") -> dict:
        """Ban or unban a user."""
        await self.user_repo.set_banned(user_id, banned)
        return {"success": True, "user_id": user_id, "banned": banned}

    async def get_stats(self, active_rooms_count: int = 0) -> dict:
        """Get operational stats."""
        total_users = await self.user_repo.get_user_count()
        total_games = await self.game_repo.get_total_games_count()
        today_games = await self.game_repo.get_today_games_count()
        online_users = self._online_count_func()

        return {
            "online_users": online_users,
            "active_rooms": active_rooms_count,
            "total_users": total_users,
            "total_games": total_games,
            "today_games": today_games,
        }

    async def list_models(self) -> dict:
        """List all AI model versions."""
        rows = await self.model_repo.list_models()

        models = []
        for row in rows:
            models.append({
                "id": row["id"],
                "version": row.get("version", ""),
                "model_path": row.get("model_path", ""),
                "elo_score": row.get("elo_score", 0),
                "status": row.get("status", ""),
                "note": row.get("note", ""),
                "created_at": str(row.get("created_at", "")),
            })

        return {"models": models}

    async def publish_model(self, model_id: int) -> dict:
        """Publish (activate) an AI model version."""
        await self.model_repo.set_active(model_id)
        return {"success": True, "model_id": model_id}
