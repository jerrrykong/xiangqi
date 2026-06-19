"""Tests for RoomRunner behaviors: rematch timeout and AI auto-ready."""
import asyncio
import pytest
import time
import sys
import os

# Ensure game-service is on path so `room` package can be imported during tests
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
GS_PATH = os.path.join(ROOT, 'game-service')
if GS_PATH not in sys.path:
    sys.path.insert(0, GS_PATH)

from room.room import Room, RoomPhase, RoomType
from room.player_session import PlayerSession
from room.runner import RoomRunner
from room.room_manager import RoomManager


@pytest.mark.asyncio
async def test_rematch_timeout_rolls_back_to_waiting():
    # Create a manager with short rematch timeout
    mgr = RoomManager(room_repo=None, game_repo=None, elo_repo=None, user_service=None,
                      disconnect_timeout=10, persist_every_n_moves=5,
                      ai_ready_delay=0.01, ai_rematch_delay=0.01, rematch_timeout=1.0)

    # Create room with two human players and FINISHED state
    room = Room(room_id="r1", room_type=RoomType.PVP, phase=RoomPhase.FINISHED)
    room.red_player = PlayerSession(user_id=1, username="r")
    room.black_player = PlayerSession(user_id=2, username="b")
    mgr.rooms[room.room_id] = room

    # Start runner
    task = asyncio.create_task(RoomRunner(mgr, room).run())

    # Wait longer than rematch_timeout
    await asyncio.sleep(1.2)

    # After timeout, room should roll back to WAITING
    assert room.phase == RoomPhase.WAITING

    task.cancel()


@pytest.mark.asyncio
async def test_ai_auto_ready_in_ready_state():
    # Manager with tiny AI ready delay
    mgr = RoomManager(room_repo=None, game_repo=None, elo_repo=None, user_service=None,
                      disconnect_timeout=10, persist_every_n_moves=5,
                      ai_ready_delay=0.05, ai_rematch_delay=0.01, rematch_timeout=1.0)

    # Create room: red is human, black is bot
    room = Room(room_id="r2", room_type=RoomType.PVE, phase=RoomPhase.READY)
    human = PlayerSession(user_id=10, username="human")
    bot = PlayerSession(user_id=0, username="ai")
    bot.is_bot = True
    room.add_player(human, "red")
    room.add_player(bot, "black")
    # mark human as already ready so AI auto-ready will trigger game start
    room.ready_players.add(human.user_id)

    mgr.rooms[room.room_id] = room

    # Run runner and allow AI to auto-ready and start the game
    task = asyncio.create_task(RoomRunner(mgr, room).run())

    # Wait a bit longer than ai_ready_delay
    await asyncio.sleep(0.2)

    # After AI ready, room should be PLAYING
    assert room.phase == RoomPhase.PLAYING

    task.cancel()
