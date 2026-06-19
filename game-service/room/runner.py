"""RoomRunner: a small state-machine wrapper that drives a Room lifecycle.

This runner orchestrates the higher-level state transitions (WAITING -> READY -> PLAYING -> FINISHED)
and delegates concrete actions (AI moves, persistence, broadcasting) to RoomManager's existing methods.

The goal is incremental refactor: keep existing helper methods in RoomManager while
centralizing the room-driving logic here.
"""

import asyncio
import logging
from typing import Any, Optional

from room.room import Room, RoomPhase

logger = logging.getLogger(__name__)


class RoomRunner:
    """Drive a single room using a small state machine.

    This runner is intended to be started as an asyncio.Task by RoomManager and
    will exit when the room is deleted or all real players have left (and cleanup
    completed by RoomManager).
    """

    def __init__(self, manager: Any, room: Room):
        self.manager = manager
        self.room = room
        self._stopped = False

    async def run(self) -> None:
        room = self.room
        mgr = self.manager

        try:
            while True:
                # If room was removed externally, stop
                if room.room_id not in mgr.rooms:
                    logger.info(f"RoomRunner stopping: room {room.room_id} no longer managed")
                    return

                # If application is shutting down, exit quickly to avoid long blocking operations
                if getattr(mgr, 'shutting_down', False):
                    logger.info(f"RoomRunner exiting early due to shutting_down for room {room.room_id}")
                    return

                phase = room.phase

                if phase == RoomPhase.WAITING:
                    # Passive wait for players to join or become ready
                    # If this room is configured to allow full-AI runs and both
                    # sides are populated by bots, transition to READY so bots
                    # can auto-ready and start games.
                    if getattr(room, 'allow_full_ai_run', False):
                        red = room.red_player
                        black = room.black_player
                        if red and black and red.is_bot and black.is_bot:
                            room.phase = RoomPhase.READY
                            # continue to READY handling immediately
                            continue

                    await asyncio.sleep(0.25)
                    # If no real players, cleanup and exit
                    if mgr._should_delete_room(room):
                        await mgr._cleanup_room(room)
                        return
                    continue

                if phase == RoomPhase.READY:
                    # Let manager auto-ready bots (use configured AI ready delay)
                    await asyncio.sleep(getattr(mgr, 'ai_ready_delay', 0.25))
                    await mgr._auto_ready_bots(room)

                    # Wait until phase transitions (player_ready or leave)
                    while room.phase == RoomPhase.READY:
                        # If room emptied, cleanup and exit
                        if mgr._should_delete_room(room):
                            await mgr._cleanup_room(room)
                            return
                        # short polling interval to react quickly to ready changes
                        await asyncio.sleep(0.05)
                    continue

                if phase == RoomPhase.PLAYING:
                    # Delegate the play loop to existing manager implementation
                    # which will run until the game finishes (phase -> FINISHED)
                    await mgr._run_room(room)
                    # after playing returns, loop will continue to FINISHED handling
                    continue

                if phase == RoomPhase.FINISHED:
                    # Ensure bots are auto-processed (may add bot user_ids to rematch_players)
                    await mgr._auto_rematch_bots(room)

                    # Wait for rematch decisions or leave, with configurable timeout
                    start_ts = asyncio.get_event_loop().time()
                    timeout = getattr(mgr, 'rematch_timeout', 60.0)
                    interval = 0.5

                    while room.phase == RoomPhase.FINISHED:
                        # If room emptied, cleanup and exit
                        if mgr._should_delete_room(room):
                            await mgr._cleanup_room(room)
                            return

                        # Check rematch conditions
                        red_id = room.red_player.user_id if room.red_player else None
                        black_id = room.black_player.user_id if room.black_player else None

                        if room.room_type.name == 'PVE':
                            # For PvE, AI auto-rematch handled; human must be in rematch_players
                            human = room.red_player if room.red_player and not room.red_player.is_bot else room.black_player
                            human_id = human.user_id if human else None
                            if human_id and human_id in room.rematch_players:
                                # Start new game in-place
                                try:
                                    room.swap_colors()
                                    room.init_game()
                                    if room.red_player:
                                        await mgr.room_repo.join_room(room.room_id, room.red_player.user_id, 'red')
                                    if room.black_player:
                                        await mgr.room_repo.join_room(room.room_id, room.black_player.user_id, 'black')
                                    await mgr.room_repo.start_game(room.room_id)
                                except Exception:
                                    # persist errors shouldn't block starting the in-memory game
                                    pass
                                # Drive the new playing game
                                await mgr._run_room(room)
                                break
                        else:
                            # PvP: require both players to have requested rematch
                            if red_id is not None and black_id is not None and red_id in room.rematch_players and black_id in room.rematch_players:
                                try:
                                    room.swap_colors()
                                    room.init_game()
                                    if room.red_player:
                                        await mgr.room_repo.join_room(room.room_id, room.red_player.user_id, 'red')
                                    if room.black_player:
                                        await mgr.room_repo.join_room(room.room_id, room.black_player.user_id, 'black')
                                    await mgr.room_repo.start_game(room.room_id)
                                except Exception:
                                    pass
                                await mgr._run_room(room)
                                break

                        # Timeout handling
                        now = asyncio.get_event_loop().time()
                        if now - start_ts >= timeout:
                            # No rematch action within timeout: rollback to WAITING
                            room.phase = RoomPhase.WAITING
                            room.rematch_players.clear()
                            break

                        await asyncio.sleep(interval)
                    continue

                # Unknown phase: sleep briefly
                await asyncio.sleep(0.25)

        except asyncio.CancelledError:
            logger.info(f"RoomRunner cancelled for room {room.room_id}")
        except Exception:
            logger.exception(f"RoomRunner error for room {room.room_id}")
        finally:
            logger.info(f"RoomRunner exited for room {room.room_id}")
