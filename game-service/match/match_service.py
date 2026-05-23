"""Game Service v2.0 - Match Service

ELO-based matchmaking engine with background match loop.
"""

import asyncio
import logging
from typing import Optional

from config import MatchConfig
from gateway.connection_manager import ConnectionManager
from match.match_queue import MatchQueue, QueueEntry
from room.room_manager import RoomManager
from room.player_session import PlayerSession
from user.user_service import UserService

logger = logging.getLogger(__name__)


class MatchService:
    """ELO-based matchmaking service.

    Runs a background loop that periodically checks the queue for matches.
    When a match is found, creates a room and notifies both players.
    """

    def __init__(self, room_manager: RoomManager, connection_manager: ConnectionManager,
                 user_service: UserService, config: MatchConfig):
        self.room_manager = room_manager
        self.connection_manager = connection_manager
        self.user_service = user_service
        self.config = config
        self.queue = MatchQueue()
        self._loop_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background match loop."""
        self._loop_task = asyncio.create_task(self._match_loop())
        logger.info("Match service started")

    async def stop(self) -> None:
        """Stop the background match loop."""
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        logger.info("Match service stopped")

    async def join_match(self, user_id: int, username: str, rating: int) -> dict:
        """Add a player to the match queue.

        Returns match_queued response data.
        """
        entry = QueueEntry(user_id=user_id, username=username, rating=rating)
        if not self.queue.join(entry):
            return {"error": "already_in_queue"}

        position = self.queue.size()
        estimated_wait = self._estimate_wait_time(rating)

        return {
            "position": position,
            "estimated_wait": estimated_wait,
        }

    async def leave_match(self, user_id: int) -> bool:
        """Remove a player from the match queue."""
        entry = self.queue.leave(user_id)
        return entry is not None

    async def _match_loop(self) -> None:
        """Background loop that processes the match queue."""
        try:
            while True:
                await asyncio.sleep(self.config.tick_interval)
                await self._process_matches()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Match loop error: {e}", exc_info=True)

    async def _process_matches(self) -> None:
        """Process all available matches in the queue."""
        while self.queue.size() >= 2:
            result = self.queue.find_match(
                elo_range=self.config.normal_elo_range,
                max_wait_time=self.config.max_wait_time,
                expand_rate=self.config.expand_rate,
                expand_interval=self.config.expand_interval,
            )

            if result is None:
                break

            entry_a, entry_b = result
            logger.info(f"Match found: {entry_a.username}({entry_a.rating}) vs {entry_b.username}({entry_b.rating})")
            await self._create_match(entry_a, entry_b)

    async def _create_match(self, entry_a: QueueEntry, entry_b: QueueEntry) -> None:
        """Create a match between two players."""
        # Higher-rated player gets red
        if entry_a.rating >= entry_b.rating:
            red_entry, black_entry = entry_a, entry_b
        else:
            red_entry, black_entry = entry_b, entry_a

        # Get user info
        red_info = await self.user_service.get_user_info(red_entry.user_id)
        black_info = await self.user_service.get_user_info(black_entry.user_id)

        # Create player sessions
        red_conn = self.connection_manager.get_by_user_id(red_entry.user_id)
        black_conn = self.connection_manager.get_by_user_id(black_entry.user_id)

        red_player = PlayerSession(
            user_id=red_entry.user_id,
            username=red_entry.username,
            nickname=red_info.get("nickname", "") if red_info else "",
            side="red",
            rating=red_entry.rating,
            _conn=red_conn,
        )
        black_player = PlayerSession(
            user_id=black_entry.user_id,
            username=black_entry.username,
            nickname=black_info.get("nickname", "") if black_info else "",
            side="black",
            rating=black_entry.rating,
            _conn=black_conn,
        )

        # Create room
        room = await self.room_manager.create_match_room(red_player, black_player)

        # Notify players
        if red_conn:
            red_conn.set_state(__import__('gateway.connection_state', fromlist=['ConnectionState']).ConnectionState.IN_ROOM)
            red_conn.room_id = room.room_id
            await red_conn.send({
                "type": "match_found",
                "data": {
                    "room_id": room.room_id,
                    "opponent": {
                        "user_id": black_entry.user_id,
                        "username": black_entry.username,
                        "nickname": black_info.get("nickname", "") if black_info else "",
                        "rating": black_entry.rating,
                    },
                    "your_side": "red",
                },
            })

        if black_conn:
            black_conn.set_state(__import__('gateway.connection_state', fromlist=['ConnectionState']).ConnectionState.IN_ROOM)
            black_conn.room_id = room.room_id
            await black_conn.send({
                "type": "match_found",
                "data": {
                    "room_id": room.room_id,
                    "opponent": {
                        "user_id": red_entry.user_id,
                        "username": red_entry.username,
                        "nickname": red_info.get("nickname", "") if red_info else "",
                        "rating": red_entry.rating,
                    },
                    "your_side": "black",
                },
            })

        logger.info(
            f"Match created: {red_entry.username}({red_entry.rating}) vs "
            f"{black_entry.username}({black_entry.rating}) in room {room.room_id}"
        )

    def _estimate_wait_time(self, rating: int) -> int:
        """Estimate wait time based on rating and queue size."""
        base_wait = 30  # seconds
        queue_size = self.queue.size()

        # More players in queue = shorter wait
        if queue_size > 10:
            base_wait = 10
        elif queue_size > 5:
            base_wait = 20

        # Extreme ratings wait longer
        if rating > 2000 or rating < 1000:
            base_wait = int(base_wait * 1.5)

        return base_wait

    @property
    def queue_size(self) -> int:
        return self.queue.size()
