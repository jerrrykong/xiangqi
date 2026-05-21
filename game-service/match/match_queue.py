"""Game Service v2.0 - Match Queue

In-memory sorted queue for ELO-based matchmaking.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class QueueEntry:
    """A player's entry in the match queue."""
    user_id: int
    username: str
    rating: int
    joined_at: float = 0.0  # timestamp when joined

    def __post_init__(self):
        if self.joined_at == 0.0:
            self.joined_at = time.time()


class MatchQueue:
    """In-memory match queue sorted by ELO rating.

    Uses a sorted list for efficient range queries.
    """

    def __init__(self):
        self._entries: list[QueueEntry] = []
        self._user_map: dict[int, QueueEntry] = {}  # user_id → entry

    def join(self, entry: QueueEntry) -> bool:
        """Add a player to the queue. Returns False if already in queue."""
        if entry.user_id in self._user_map:
            return False

        self._user_map[entry.user_id] = entry
        self._entries.append(entry)
        # Keep sorted by rating
        self._entries.sort(key=lambda e: e.rating)
        return True

    def leave(self, user_id: int) -> Optional[QueueEntry]:
        """Remove a player from the queue."""
        entry = self._user_map.pop(user_id, None)
        if entry:
            self._entries.remove(entry)
        return entry

    def find_match(self, elo_range: int = 100,
                   max_wait_time: int = 180,
                   expand_rate: int = 50,
                   expand_interval: int = 30) -> Optional[tuple[QueueEntry, QueueEntry]]:
        """Find a match between two players in the queue.

        Strategy:
        - Initial ELO range is wider for new players
        - Normal ELO range for regular players
        - Gradually expand range for players who have waited longer
        - Max wait time with maximum range expansion

        Returns a pair of matched entries, or None if no match found.
        """
        if len(self._entries) < 2:
            return None

        now = time.time()
        best_match = None
        best_diff = float('inf')

        for i in range(len(self._entries)):
            entry_a = self._entries[i]
            wait_time = now - entry_a.joined_at

            # Calculate dynamic ELO range based on wait time
            dynamic_range = elo_range + int(wait_time / expand_interval) * expand_rate
            dynamic_range = min(dynamic_range, elo_range * 4)  # Cap at 4x

            # Look for opponent within range
            for j in range(i + 1, len(self._entries)):
                entry_b = self._entries[j]
                diff = abs(entry_a.rating - entry_b.rating)

                if diff > dynamic_range:
                    break  # No more matches possible (sorted by rating)

                if diff < best_diff:
                    best_diff = diff
                    best_match = (entry_a, entry_b)

        if best_match:
            # Remove matched entries
            self.leave(best_match[0].user_id)
            self.leave(best_match[1].user_id)
            return best_match

        return None

    def size(self) -> int:
        return len(self._entries)

    def get_position(self, user_id: int) -> Optional[int]:
        """Get a player's position in the queue."""
        entry = self._user_map.get(user_id)
        if entry:
            return self._entries.index(entry)
        return None

    def get_all_entries(self) -> list[QueueEntry]:
        """Get all entries (for admin/debug)."""
        return list(self._entries)

    def clear(self) -> None:
        """Clear the entire queue."""
        self._entries.clear()
        self._user_map.clear()
