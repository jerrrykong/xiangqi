"""Game Service v2.0 - Room Manager

Manages all active rooms in memory.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Optional, Tuple

from chess.constants import Color, GameResult, WinReason
from chess.game import ChessGame
from chess.move import Move
from chess.move_validator import MoveValidator
from chess.win_checker import WinChecker
from chess.piece import create_initial_board, board_to_fen
from ai.ai_proxy import AIProxy
from room.room import Room, RoomPhase, RoomSource, RoomType
from room.player_session import PlayerSession
from room.timers import MoveTimer
from room.runner import RoomRunner
from user.elo_repository import EloRepository
from room.room_repository import RoomRepository, GameRepository
from user.user_service import UserService

logger = logging.getLogger(__name__)


class RoomManager:
    """Manages all active rooms in memory.

    Rooms are the sole carrier of a game from creation to finish.
    """

    # AI name and avatar profile based on difficulty level (1-5)
    AI_PROFILES: Dict[int, Tuple[str, str]] = {
        1: ("电脑·初学", "sys:ai-easy"),
        2: ("电脑·普通", "sys:ai-medium"),
        3: ("电脑·专业", "sys:ai-hard"),
        4: ("电脑·大师", "sys:ai-master"),
        5: ("电脑·宗师", "sys:ai-grandmaster"),
    }
    AI_PROFILE_DEFAULT = ("电脑·普通", "sys:ai-medium")

    def __init__(self, room_repo: RoomRepository, game_repo: GameRepository,
                 elo_repo: EloRepository, user_service: UserService,
                 disconnect_timeout: int = 300,
                 persist_every_n_moves: int = 5,
                 ai_ready_delay: float = 0.25,
                 ai_rematch_delay: float = 0.5,
                 rematch_timeout: float = 60.0):
        self.rooms: Dict[str, Room] = {}
        self.user_rooms: Dict[int, str] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.ai_proxy = AIProxy()
        self.room_repo = room_repo
        self.game_repo = game_repo
        self.elo_repo = elo_repo
        self.user_service = user_service
        self.disconnect_timeout = disconnect_timeout
        # Persistence and AI timing configuration
        self.persist_every_n_moves = max(1, int(persist_every_n_moves))
        self.ai_ready_delay = float(ai_ready_delay)
        self.ai_rematch_delay = float(ai_rematch_delay)
        # How long to wait in FINISHED state for rematch before rolling back
        self.rematch_timeout = float(rematch_timeout)
        self._disconnect_checker_task: Optional[asyncio.Task] = None
        # Flag set during application shutdown to avoid DB writes
        self.shutting_down: bool = False
        # Debug flag: when True, _save_game_result will raise an exception after
        # computing ratings (simulates DB write failure for testing)
        self._debug_crash_on_save: bool = False

    # ---- Room Creation ----

    async def create_manual_room(self, creator: PlayerSession,
                                 initial_time: int = 600,
                                 increment: int = 10) -> Room:
        """Create a manual PvP room (creator is red, waiting for opponent)."""
        room_id = str(uuid.uuid4())
        room = Room(
            room_id=room_id,
            room_type=RoomType.PVP,
            source=RoomSource.MANUAL,
            phase=RoomPhase.WAITING,
            initial_time=initial_time,
            increment=increment,
        )
        room.add_player(creator, "red")
        self.rooms[room_id] = room
        self.user_rooms[creator.user_id] = room_id

        logger.info(f"Manual PvP room created: room_id={room_id}, creator={creator.username}(id={creator.user_id})")

        # Persist to DB
        try:
            await self.room_repo.create(
                room_id=room_id, room_type="pvp", source="manual",
                created_by=creator.user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to persist room creation: {e}")

        return room

    async def create_match_room(self, red: PlayerSession, black: PlayerSession,
                                initial_time: int = 600,
                                increment: int = 10) -> Room:
        """Create a match-based PvP room (directly enters PLAYING)."""
        room_id = str(uuid.uuid4())
        room = Room(
            room_id=room_id,
            room_type=RoomType.PVP,
            source=RoomSource.MATCH,
            phase=RoomPhase.PLAYING,
            initial_time=initial_time,
            increment=increment,
        )
        room.add_player(red, "red")
        room.add_player(black, "black")
        room.init_game()

        logger.info(f"Match PvP room created: room_id={room_id}, red={red.username}({red.rating}) vs black={black.username}({black.rating})")

        self.rooms[room_id] = room
        self.user_rooms[red.user_id] = room_id
        self.user_rooms[black.user_id] = room_id

        # Persist to DB
        try:
            await self.room_repo.create(
                room_id=room_id, room_type="pvp", source="match",
                created_by=red.user_id,
            )
            await self.room_repo.join_room(room_id, red.user_id, "red")
            await self.room_repo.join_room(room_id, black.user_id, "black")
            await self.room_repo.start_game(room_id)
        except Exception as e:
            logger.warning(f"Failed to persist match room: {e}")

        # Start room runner coroutine
        task = asyncio.create_task(RoomRunner(self, room).run())
        self.tasks[room_id] = task

        return room

    async def create_pve_room(self, player: PlayerSession, player_side: str = "red",
                              difficulty: int = 3,
                              initial_time: int = 600,
                              increment: int = 10) -> Room:
        """Create a PvE room (directly enters PLAYING)."""
        room_id = str(uuid.uuid4())

        # AI name and avatar based on difficulty level
        ai_name, ai_avatar = self.AI_PROFILES.get(difficulty, self.AI_PROFILE_DEFAULT)

        room = Room(
            room_id=room_id,
            room_type=RoomType.PVE,
            source=RoomSource.MANUAL,
            phase=RoomPhase.PLAYING,
            difficulty=difficulty,
            initial_time=initial_time,
            increment=increment,
            ai_name=ai_name,
            ai_avatar=ai_avatar,
        )

        if player_side == "red":
            room.add_player(player, "red")
            room.ai_side = Color.BLACK
        else:
            room.add_player(player, "black")
            room.ai_side = Color.RED

        room.init_game()

        logger.info(f"PvE room created: room_id={room_id}, player={player.username}(id={player.user_id}), side={player_side}, difficulty={difficulty}")

        self.rooms[room_id] = room
        self.user_rooms[player.user_id] = room_id
        try:
            await self.room_repo.create(
                room_id=room_id, room_type="pve", source="manual",
                created_by=player.user_id, difficulty=difficulty,
            )
            await self.room_repo.join_room(room_id, player.user_id, player_side)
            await self.room_repo.start_game(room_id)
        except Exception as e:
            logger.warning(f"Failed to persist PvE room: {e}")

        task = asyncio.create_task(RoomRunner(self, room).run())
        self.tasks[room_id] = task

        return room

    # ---- Room Join ----

    async def join_room(self, room_id: str, player: PlayerSession) -> Optional[Room]:
        """Join a manual room. Enters READY phase (both must click start)."""
        room = self.rooms.get(room_id)
        if not room:
            logger.debug(f"Join room failed: room_id={room_id} not found")
            return None
        if room.phase != RoomPhase.WAITING:
            logger.debug(f"Join room failed: room_id={room_id} phase={room.phase.name}, not WAITING")
            return None
        if room.is_full:
            logger.debug(f"Join room failed: room_id={room_id} is full")
            return None

        logger.info(f"Player {player.username}(id={player.user_id}) joining room {room_id}")
        room.add_player(player, "black")
        self.user_rooms[player.user_id] = room_id

        # Enter READY phase (both must click start)
        room.phase = RoomPhase.READY

        # Persist
        try:
            await self.room_repo.join_room(room_id, player.user_id, "black")
        except Exception as e:
            logger.warning(f"Failed to persist room join: {e}")

        # Auto-ready bot players
        await self._auto_ready_bots(room)

        return room

    # ---- Player Ready (READY phase) ----

    async def player_ready(self, room: Room, user_id: int) -> Optional[str]:
        """Handle player clicking 'Start' in READY phase.

        Returns:
            'started' if game starts, 'accepted' if waiting for opponent, None if invalid
        """
        if room.phase != RoomPhase.READY:
            return None

        room.ready_players.add(user_id)
        logger.info(f"Player {user_id} ready in room {room.room_id}, ready_players={room.ready_players}")

        # Check if both players are ready
        red_id = room.red_player.user_id if room.red_player else None
        black_id = room.black_player.user_id if room.black_player else None

        if red_id is not None and black_id is not None and red_id in room.ready_players and black_id in room.ready_players:
            # Both ready - start the game
            room.init_game()

            # Persist
            try:
                await self.room_repo.start_game(room.room_id)
            except Exception as e:
                logger.warning(f"Failed to persist game start: {e}")

            # Start RoomRunner to drive the game (broadcast game_start, handle moves, etc.)
            task = asyncio.create_task(RoomRunner(self, room).run())
            self.tasks[room.room_id] = task

            return "started"

        return "accepted"

    # ---- Rematch (FINISHED phase) ----

    async def rematch(self, room: Room, user_id: int) -> Optional[str]:
        """Handle player clicking 'Rematch' in FINISHED phase.

        Returns:
            'started' if new game starts, 'accepted' if waiting for opponent, None if invalid
        """
        if room.phase != RoomPhase.FINISHED:
            return None

        room.rematch_players.add(user_id)
        logger.info(f"Player {user_id} wants rematch in room {room.room_id}, rematch_players={room.rematch_players}")

        # Check if both players want rematch
        red_id = room.red_player.user_id if room.red_player else None
        black_id = room.black_player.user_id if room.black_player else None

        if red_id is not None and black_id is not None and red_id in room.rematch_players and black_id in room.rematch_players:
            # Both want rematch - swap colors and start new game
            room.swap_colors()
            room.init_game()

            # Persist
            try:
                await self.room_repo.join_room(room.room_id, room.red_player.user_id, "red")
                await self.room_repo.join_room(room.room_id, room.black_player.user_id, "black")
                await self.room_repo.start_game(room.room_id)
            except Exception as e:
                logger.warning(f"Failed to persist rematch: {e}")

            # Start room runner coroutine
            task = asyncio.create_task(RoomRunner(self, room).run())
            self.tasks[room.room_id] = task

            return "started"

        return "accepted"

    # ---- Bot Auto-Actions ----

    async def _auto_ready_bots(self, room: Room) -> None:
        """Auto-ready bot players when entering READY phase."""
        for player in [room.red_player, room.black_player]:
            if player and player.is_bot and player.user_id not in room.ready_players:
                logger.info(f"Auto-ready bot: user_id={player.user_id} in room={room.room_id}")
                # Short delay for AI ready UX
                try:
                    await asyncio.sleep(self.ai_ready_delay)
                except asyncio.CancelledError:
                    return
                # Notify human opponent
                opponent = room.get_opponent(player.user_id)
                if opponent and opponent.is_connected:
                    await opponent.send({
                        "type": "opponent_ready",
                        "data": {"user_id": player.user_id},
                    })
                result = await self.player_ready(room, player.user_id)
                if result == "started":
                    return

    async def _auto_rematch_bots(self, room: Room) -> None:
        """Auto-rematch bot players when game ends — works for all room types."""
        if room.room_id not in self.rooms:
            return
        if room.phase != RoomPhase.FINISHED:
            return

        # Step 1: 自动 rematch 所有拥有 PlayerSession 的 bot 玩家
        for player in [room.red_player, room.black_player]:
            if player and player.is_bot and player.user_id not in room.rematch_players:
                logger.info(f"Auto-rematch bot: user_id={player.user_id} in room={room.room_id}")
                # Short delay before bot rematch to avoid immediate restart
                try:
                    await asyncio.sleep(self.ai_rematch_delay)
                except asyncio.CancelledError:
                    return
                opponent = room.get_opponent(player.user_id)
                if opponent and opponent.is_connected:
                    await opponent.send({
                        "type": "opponent_rematch",
                        "data": {"user_id": player.user_id},
                    })
                room.rematch_players.add(player.user_id)

        # Step 2: 判断是否满足开局条件
        if room.room_type == RoomType.PVE:
            # PvE: AI will auto-add itself to rematch_players and notify the human opponent.
            # Do NOT auto-start a new game here — the human must explicitly request rematch.
            human = room.red_player if room.red_player and not room.red_player.is_bot else room.black_player
            bot = room.red_player if room.red_player and room.red_player.is_bot else room.black_player
            if human and human.is_connected:
                await human.send({
                    "type": "opponent_rematch",
                    "data": {"user_id": bot.user_id if bot else 0},
                })
            logger.info(f"Auto-rematch: PvE bot notified in room={room.room_id}")
            # Only start when both human and bot are recorded in rematch_players
            human_id = human.user_id if human else None
            bot_id = bot.user_id if bot else None
            if not (human_id is not None and bot_id is not None and
                    human_id in room.rematch_players and bot_id in room.rematch_players):
                return
        else:
            # PvP: 双方都必须已 rematch 才能开局
            red_id = room.red_player.user_id if room.red_player else None
            black_id = room.black_player.user_id if room.black_player else None
            if not (red_id is not None and black_id is not None
                    and red_id in room.rematch_players
                    and black_id in room.rematch_players):
                return

        # If shutting down, skip starting new games / persisting
        if getattr(self, 'shutting_down', False):
            logger.info(f"Shutting down: skip auto-rematch start for room={room.room_id}")
            return

        # Step 3: 开局（统一逻辑）
        logger.info(f"Auto-rematch: starting new game in room={room.room_id}")
        room.swap_colors()
        room.init_game()
        try:
            if room.red_player:
                await self.room_repo.join_room(room.room_id, room.red_player.user_id, "red")
            if room.black_player:
                await self.room_repo.join_room(room.room_id, room.black_player.user_id, "black")
            await self.room_repo.start_game(room.room_id)
        except Exception as e:
            logger.warning(f"Failed to persist auto-rematch: {e}")
        # Don't start a new runner here — the active RoomRunner will observe the
        # phase change and resume driving the PLAYING state.

    # ---- Leave Room ----

    async def leave_room(self, room: Room, user_id: int, reason: str = "explicit_leave") -> None:
        """Handle a player leaving the room.

        Rule 5: PLAYING state requires resign first; other states leave directly.
        After leaving, apply Rule 1 (delete room if no real players).

        Args:
            reason: Why the player is leaving, e.g. "disconnect_timeout",
                    "player_request", "join_other_room", "enter_matchmaking",
                    "explicit_leave".
        """
        side = room.get_player_side(user_id)
        if not side:
            return

        # Determine effective reason for PLAYING state
        effective_reason = reason
        if room.phase == RoomPhase.PLAYING:
            effective_reason = f"{reason}→resign_escape"

        # Log player exit with details
        player = room.get_player(side)
        is_bot = player.is_bot if player else False
        username = player.username if player else f"user_{user_id}"
        logger.info(
            f"Player leaving room: user_id={user_id}, username={username}, "
            f"side={side}, is_bot={is_bot}, room_id={room.room_id}, "
            f"room_type={room.room_type.name}, phase={room.phase.name}, "
            f"reason={effective_reason}"
        )

        # PLAYING state: must resign first
        if room.phase == RoomPhase.PLAYING:
            if side == "red":
                room.game_state.game_result = GameResult.RED_RESIGN
            else:
                room.game_state.game_result = GameResult.BLACK_RESIGN
            await self._handle_game_over(room, "resign", is_escape=True)
            room.move_event.set()

        # Remove player from room
        self._remove_player(room, user_id)
        self.user_rooms.pop(user_id, None)
        room.ready_players.discard(user_id)
        room.rematch_players.discard(user_id)

        # Rule 1: delete room if no real players (unless all bots)
        if self._should_delete_room(room):
            await self._cleanup_room(room, reason=f"no_real_players_after_leave(user={user_id},{effective_reason})")
            return

        # Notify remaining connected players
        for player in [room.red_player, room.black_player]:
            if player and player.is_connected:
                await player.send({
                    "type": "player_left",
                    "data": {"user_id": user_id, "phase": room.phase.name.lower()},
                })

        # Phase transition: if READY and a player left, go back to WAITING
        if room.phase == RoomPhase.READY:
            room.phase = RoomPhase.WAITING
            room.ready_players.clear()

    # ---- Rule 1: Empty Room Check ----

    def _should_delete_room(self, room: Room) -> bool:
        """Rule 1: Room should be deleted if it has no real (non-bot) players.
        Exception: don't delete rooms where all players are bots (reserved for auto-play).
        """
        players = [p for p in [room.red_player, room.black_player] if p is not None]
        if not players:
            return True  # No players at all → delete
        real_players = [p for p in players if not p.is_bot]
        if real_players:
            return False  # Has real players → keep
        # All players are bots → keep (reserved for auto-play)
        return False

    def _remove_player(self, room: Room, user_id: int) -> None:
        """Remove a player from the room."""
        side = room.get_player_side(user_id)
        if side == "red":
            room.red_player = None
        elif side == "black":
            room.black_player = None

    async def _run_room(self, room: Room) -> None:
        """Room main coroutine - manages the complete game flow."""
        try:
            # Initialize timer
            on_timeout = lambda side: self._handle_timeout(room, side)
            room.timer = MoveTimer(
                initial_time=room.initial_time,
                increment=room.increment,
                on_timeout=on_timeout,
            )
            room.timer.start("red")

            # Broadcast game_start
            fen = board_to_fen(room.game_state.board,room.game_state.current_player)

            # Build player info dicts (including AI for PvE rooms)
            red_info = self._player_info(room.red_player)
            black_info = self._player_info(room.black_player)
            if room.room_type == RoomType.PVE and room.ai_side is not None:
                ai_info = {
                    "user_id": 0,
                    "username": room.ai_name,
                    "nickname": room.ai_name,
                    "avatar": room.ai_avatar,
                    "rating": 0,
                    "is_bot": True,
                    "online": True,
                }
                if room.ai_side == Color.RED:
                    red_info = ai_info
                else:
                    black_info = ai_info

            for player in [room.red_player, room.black_player]:
                if player and player.is_connected:
                    side = player.side
                    await player.send({
                        "type": "game_start",
                        "data": {
                            "room_id": room.room_id,
                            "your_side": side,
                            "red_player": red_info,
                            "black_player": black_info,
                            "initial_time": room.initial_time,
                            "increment": room.increment,
                            "fen": fen,
                        },
                    })

            # If AI goes first (PvE, player is black), make AI move
            if room.room_type == RoomType.PVE and room.ai_side == Color.RED:
                await self._do_ai_move(room)

            # Game loop
            while room.phase == RoomPhase.PLAYING:
                if room.game_state.is_game_over:
                    await self._handle_game_over(room, self._get_game_over_reason(room))
                    break

                current_color = room.game_state.current_player
                current_side = "red" if current_color == Color.RED else "black"

                # AI turn
                if room.room_type == RoomType.PVE and room.ai_side == current_color:
                    await self._do_ai_move(room)
                    continue

                # Player turn - wait for move
                room.move_event.clear()
                try:
                    await asyncio.wait_for(
                        room.move_event.wait(),
                        timeout=room.timer.get_current_remaining() + 1,
                    )
                except asyncio.TimeoutError:
                    # Timer should have already handled this
                    pass

        except asyncio.CancelledError:
            logger.info(f"Room {room.room_id} game coroutine cancelled")
        except Exception as e:
            logger.exception(f"Room {room.room_id} error: {e}")
        finally:
            if room.timer:
                room.timer.stop()
            # NOTE: Don't cleanup room here - room persists for rematch
            # Cleanup happens when both players leave (via leave_room)

    # ---- Move Handling ----

    async def apply_player_move(self, room: Room, move: Move) -> None:
        """Apply a player's move. Called by RoomHandler."""
        logger.info(f"Applying move in room={room.room_id}: ({move.from_row},{move.from_col})->({move.to_row},{move.to_col})")
        await self._apply_and_broadcast_move(room, move, "opponent_move")
        room.move_event.set()

    async def _do_ai_move(self, room: Room) -> None:
        """AI makes a move."""
        # If shutting down, skip starting AI computation
        if getattr(self, 'shutting_down', False):
            logger.info(f"Shutting down: skip AI move for room={room.room_id}")
            return
        player = room.red_player if room.ai_side == Color.BLACK else room.black_player
        if player and player.is_connected:
            await player.send({"type": "ai_thinking", "data": {}})

        import time
        start = time.time()
        move = await self.ai_proxy.get_best_move(
            board=room.game_state.board,
            current_turn=room.game_state.current_player,
            difficulty=room.difficulty or 3,
        )
        think_time_ms = int((time.time() - start) * 1000)

        if move is None:
            # AI has no moves → AI loses
            if room.ai_side == Color.RED:
                room.game_state.game_result = GameResult.BLACK_WINS
            else:
                room.game_state.game_result = GameResult.RED_WINS
            await self._handle_game_over(room, "checkmate")
            return

        # Apply move
        success, error = room.game_state.make_move(move)
        if not success:
            logger.warning(f"AI move failed: {error}")
            if room.ai_side == Color.RED:
                room.game_state.game_result = GameResult.BLACK_WINS
            else:
                room.game_state.game_result = GameResult.RED_WINS
            await self._handle_game_over(room, "ai_error")
            return

        if room.timer:
            room.timer.switch_side()

        fen = board_to_fen(room.game_state.board, room.game_state.current_player)
        captured_info = None
        if room.game_state.history:
            last_record = room.game_state.history[-1]
            if last_record.captured is not None and last_record.captured >= 0:
                captured_info = {"piece": last_record.captured}

        if player and player.is_connected:
            await player.send({
                "type": "ai_move",
                "data": {
                    "from_pos": [move.from_row, move.from_col],
                    "to_pos": [move.to_row, move.to_col],
                    "fen": fen,
                    "captured": captured_info,
                    "think_time_ms": think_time_ms,
                    "red_remaining_time": room.timer.red_remaining,
                    "black_remaining_time": room.timer.black_remaining,
                },
            })

        # Check game over after AI move
        if room.game_state.is_game_over:
            await self._handle_game_over(room, self._get_game_over_reason(room))
        else:
            # Persist every N moves to reduce IO. N is configurable.
            try:
                moves_count = room.game_state.move_count if room.game_state else 0
                if moves_count % self.persist_every_n_moves == 0:
                    await self._persist_room_state(room)
            except Exception:
                # Fallback to best-effort persist
                await self._persist_room_state(room)

    async def _apply_and_broadcast_move(self, room: Room, move: Move,
                                        msg_type: str) -> None:
        """Execute a move and broadcast to both players."""
        success, error = room.game_state.make_move(move)
        if not success:
            logger.warning(f"Move failed in room {room.room_id}: {error}")
            return

        if room.timer:
            room.timer.switch_side()

        fen = board_to_fen(room.game_state.board, room.game_state.current_player)

        # Find who just moved (the player whose turn it was)
        current_color = room.game_state.current_player
        mover_side = "black" if current_color == Color.RED else "red"  # turn already switched
        mover = room.get_player(mover_side)

        # Find captured piece from history
        captured_info = None
        if room.game_state.history:
            last_record = room.game_state.history[-1]
            if last_record.captured is not None and last_record.captured >= 0:
                captured_info = {"piece": last_record.captured}

        # Send move_result to mover
        if mover and mover.is_connected:
            await mover.send({
                "type": "move_result",
                "data": {
                    "success": True,
                    "fen": fen,
                    "move": {
                        "from_pos": [move.from_row, move.from_col],
                        "to_pos": [move.to_row, move.to_col],
                    },
                    "captured": captured_info,
                    "red_remaining_time": room.timer.red_remaining,
                    "black_remaining_time": room.timer.black_remaining,
                },
            })

        # Send opponent_move to opponent
        opponent = room.get_opponent(mover.user_id if mover else 0)
        if opponent and opponent.is_connected:
            await opponent.send({
                "type": "opponent_move",
                "data": {
                    "from_pos": [move.from_row, move.from_col],
                    "to_pos": [move.to_row, move.to_col],
                    "fen": fen,
                    "captured": captured_info,
                    "red_remaining_time": room.timer.red_remaining,
                    "black_remaining_time": room.timer.black_remaining,
                },
            })

        # Check game over
        if room.game_state.is_game_over:
            await self._handle_game_over(room, self._get_game_over_reason(room))
        else:
            # Persist periodically (every N moves) to reduce IO.
            try:
                moves_count = room.game_state.move_count if room.game_state else 0
                if moves_count % self.persist_every_n_moves == 0:
                    await self._persist_room_state(room)
            except Exception:
                await self._persist_room_state(room)

    # ---- Game Over ----

    async def _handle_game_over(self, room: Room, reason: str, is_escape: bool = False) -> None:
        """Handle game over: determine winner, broadcast, save to DB."""
        room.phase = RoomPhase.FINISHED
        if room.timer:
            room.timer.stop()

        winner = "draw"
        logger.info(f"Game over: room={room.room_id}, reason={reason}, computing winner...")
        game_result = room.game_state.game_result if room.game_state else None

        if game_result in (GameResult.RED_WINS, GameResult.BLACK_RESIGN, GameResult.BLACK_TIMEOUT):
            winner = "red"
        elif game_result in (GameResult.BLACK_WINS, GameResult.RED_RESIGN, GameResult.RED_TIMEOUT):
            winner = "black"

        # Calculate rating changes first (before DB save, in case save fails)
        red_rating_change, black_rating_change = 0, 0
        try:
            red_rating_change, black_rating_change = await self._save_game_result(
                room, winner, reason, is_escape
            )
        except Exception as e:
            logger.error(f"Failed to save game result for room={room.room_id}: {e}", exc_info=True)

        # Broadcast game_over with rating changes (always send, even if DB save fails)
        fen = board_to_fen(room.game_state.board, room.game_state.current_player) if room.game_state else ""
        last_move = None
        if room.game_state and room.game_state.history:
            last_record = room.game_state.history[-1]
            last_move = {
                "from_pos": [last_record.move.from_row, last_record.move.from_col],
                "to_pos": [last_record.move.to_row, last_record.move.to_col],
            }
            if last_record.captured >= 0:
                last_move["captured"] = {"piece": last_record.captured}

        logger.info(f"Game over broadcast: room={room.room_id}, winner={winner}, reason={reason}, "
                     f"moves={room.game_state.move_count if room.game_state else 0}, "
                     f"red_change={red_rating_change}, black_change={black_rating_change}")
        await self._broadcast(room, {
            "type": "game_over",
            "data": {
                "room_id": room.room_id,
                "winner": winner,
                "reason": reason,
                "total_moves": room.game_state.move_count if room.game_state else 0,
                "red_rating_change": red_rating_change,
                "black_rating_change": black_rating_change,
                "fen": fen,
                "last_move": last_move,
            },
        })

        # Auto-rematch bot players (skip for escape/leave scenarios)
        if not is_escape:
            await self._auto_rematch_bots(room)

    async def _save_game_result(self, room: Room, winner: str, reason: str,
                                 is_escape: bool = False) -> tuple[int, int]:
        """Save game result to database and update ratings.

        Returns:
            (red_rating_change, black_rating_change)
        """
        red_user_id = room.red_player.user_id if room.red_player else None
        black_user_id = room.black_player.user_id if room.black_player else None

        # Determine winner int for DB (0=red, 1=black, -1=draw)
        winner_int = -1
        if winner == "red":
            winner_int = 0
        elif winner == "black":
            winner_int = 1

        result_str = "DRAW"
        if winner == "red":
            result_str = "RED_WINS"
        elif winner == "black":
            result_str = "BLACK_WINS"

        # Calculate duration
        import time
        duration = int(time.time() - room.started_at) if room.started_at else 0

        # Get moves JSON
        moves_json = "[]"
        if room.game_state and hasattr(room.game_state, 'recorder'):
            try:
                import json
                moves_json = json.dumps([
                    {"from": [m.move.from_row, m.move.from_col],
                     "to": [m.move.to_row, m.move.to_col]}
                    for m in room.game_state.recorder.moves
                ])
            except Exception:
                moves_json = "[]"

        moves_count = room.game_state.move_count if room.game_state else 0

        # If shutting down, skip DB writes to avoid pool-closed errors
        if getattr(self, 'shutting_down', False):
            logger.info(f"Shutting down: skip saving game result for room={room.room_id}")
            return 0, 0

        # Rating calculation for PvP
        red_rating_change = 0
        black_rating_change = 0
        red_rating_before = 1500
        black_rating_before = 1500
        red_rating_after = 1500
        black_rating_after = 1500

        if room.room_type == RoomType.PVP and red_user_id and black_user_id:
            red_elo = await self.elo_repo.get_or_create(red_user_id)
            black_elo = await self.elo_repo.get_or_create(black_user_id)
            red_rating_before = red_elo["rating"]
            black_rating_before = black_elo["rating"]

            # Use new scoring system
            red_rating_change, black_rating_change = UserService.calculate_score(
                red_rating_before, black_rating_before, winner,
                total_moves=moves_count, is_escape=is_escape,
            )

            # Apply rating with floor protection
            red_rating_after = UserService.apply_rating_floor(
                red_rating_before, red_rating_change,
                is_escape=is_escape and winner != "red",
            )
            black_rating_after = UserService.apply_rating_floor(
                black_rating_before, black_rating_change,
                is_escape=is_escape and winner != "black",
            )

            # DEBUG: crash-on-save simulation — raises after ratings computed
            if self._debug_crash_on_save:
                logger.warning(f"[DEBUG] Simulating DB save crash for room={room.room_id}")
                raise RuntimeError(f"DEBUG: simulated DB crash in _save_game_result for room={room.room_id}")

            # Update ELO in DB
            try:
                await self.elo_repo.update_rating(
                    red_user_id, red_rating_after,
                    red_elo["games_count"] + 1,
                )
            except Exception as e:
                logger.error(f"Failed to update red ELO rating for user={red_user_id}: {e}")
            try:
                await self.elo_repo.update_rating(
                    black_user_id, black_rating_after,
                    black_elo["games_count"] + 1,
                )
            except Exception as e:
                logger.error(f"Failed to update black ELO rating for user={black_user_id}: {e}")

            # Create ELO history
            try:
                await self.elo_repo.create_history(red_user_id, None, red_rating_after, red_rating_change)
                await self.elo_repo.create_history(black_user_id, None, black_rating_after, black_rating_change)
            except Exception as e:
                logger.warning(f"Failed to save ELO history: {e}")

            # Send rating_update to players
            for player, change, new_rating in [
                (room.red_player, red_rating_change, red_rating_after),
                (room.black_player, black_rating_change, black_rating_after),
            ]:
                try:
                    if player and player.is_connected:
                        await player.send({
                            "type": "rating_update",
                            "data": {
                                "rating": new_rating,
                                "change": change,
                                "games_count": (red_elo if player.side == "red" else black_elo)["games_count"] + 1,
                            },
                        })
                except Exception as e:
                    logger.warning(f"Failed to send rating_update to {player.side}: {e}")

        # Save game history
        try:
            import datetime
            start_time = datetime.datetime.fromtimestamp(room.started_at) if room.started_at else datetime.datetime.now()
            game_record = await self.game_repo.create(
                room_id=room.room_id,
                winner=winner,
                result=winner_int,
                total_moves=moves_count,
                start_time=start_time,
                end_time=datetime.datetime.now(),
                pve_level=room.difficulty if room.room_type == RoomType.PVE else None,
                red_user_id=red_user_id,
                black_user_id=black_user_id,
            )
        except Exception as e:
            logger.error(f"Failed to save game history: {e}")

        # Update room status in DB
        try:
            await self.room_repo.finish_game(room.room_id, winner, winner_int)
        except Exception as e:
            logger.error(f"Failed to update room status: {e}")

        return red_rating_change, black_rating_change

    # ---- Timeout ----

    async def _handle_timeout(self, room: Room, side: str) -> None:
        """Handle player timeout - the side that timed out loses."""
        if room.phase != RoomPhase.PLAYING:
            return

        logger.info(f"Timeout in room={room.room_id}, side={side} timed out")

        if side == "red":
            room.game_state.game_result = GameResult.RED_TIMEOUT
        else:
            room.game_state.game_result = GameResult.BLACK_TIMEOUT

        await self._handle_game_over(room, "timeout", is_escape=True)
        room.move_event.set()

    # ---- Resign ----

    async def resign(self, room: Room, user_id: int) -> None:
        """Handle player resignation."""
        if room.phase != RoomPhase.PLAYING:
            return

        side = room.get_player_side(user_id)
        if side == "red":
            room.game_state.game_result = GameResult.RED_RESIGN
        else:
            room.game_state.game_result = GameResult.BLACK_RESIGN

        await self._handle_game_over(room, "resign")
        room.move_event.set()

    # ---- Draw ----

    async def draw_request(self, room: Room, user_id: int) -> None:
        """Handle draw request - forward to opponent."""
        if room.phase != RoomPhase.PLAYING:
            return

        opponent = room.get_opponent(user_id)
        if opponent and opponent.is_connected:
            room.draw_requester_id = user_id
            await opponent.send({
                "type": "draw_request",
                "data": {"from_user_id": user_id},
            })

    async def draw_answer(self, room: Room, user_id: int, accept: bool) -> None:
        """Handle draw answer."""
        if room.phase != RoomPhase.PLAYING:
            return

        if accept:
            room.game_state.game_result = GameResult.DRAW
            await self._handle_game_over(room, "agreement")
            room.move_event.set()
        else:
            room.draw_requester_id = None
            opponent = room.get_opponent(user_id)
            if opponent and opponent.is_connected:
                await opponent.send({
                    "type": "draw_result",
                    "data": {"accepted": False},
                })

    # ---- Broadcast ----

    async def _broadcast(self, room: Room, msg: dict) -> None:
        """Broadcast message to all connected players in the room."""
        for player in [room.red_player, room.black_player]:
            if player and player.is_connected:
                await player.send(msg)

    # ---- Cleanup ----

    async def _cleanup_room(self, room: Room, reason: str = "rule1_no_real_players") -> None:
        """Delete room and all associated resources (Rule 1).

        Args:
            reason: Why the room is being cleaned up, for logging purposes.
        """
        logger.info(f"Cleaning up room={room.room_id}, phase={room.phase.name}, "
                     f"room_type={room.room_type.name}, game_count={room.game_count}, "
                     f"reason={reason}")

        # Log each player being removed from the room
        for player in [room.red_player, room.black_player]:
            if player:
                self.user_rooms.pop(player.user_id, None)
                logger.info(
                    f"Player removed during room cleanup: user_id={player.user_id}, "
                    f"username={player.username}, side={player.side}, "
                    f"is_bot={player.is_bot}, connected={player.is_connected}, "
                    f"room_id={room.room_id}, reason={reason}"
                )

        # Log PvE AI side exit (AI doesn't have a PlayerSession)
        if room.room_type == RoomType.PVE and room.ai_side is not None:
            ai_side_name = "red" if room.ai_side == Color.RED else "black"
            logger.info(
                f"AI player removed during room cleanup: side={ai_side_name}, "
                f"room_id={room.room_id}, room_type=PVE, reason={reason}"
            )
        # Cancel running game task if any
        task = self.tasks.pop(room.room_id, None)
        if task and not task.done():
            task.cancel()
        self.rooms.pop(room.room_id, None)

        # Persist deletion to DB
        if getattr(self, 'shutting_down', False):
            logger.info(f"Shutting down: skip DB cleanup for room={room.room_id}")
            return

        try:
            if room.game_count > 0:
                await self.room_repo.finish_game(room.room_id, "draw", -1)
            else:
                await self.room_repo.delete(room.room_id)
        except Exception as e:
            logger.warning(f"Failed to persist room cleanup for {room.room_id}: {e}")

    # ---- Queries ----

    def get_room(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    def get_user_room(self, user_id: int) -> Optional[Room]:
        room_id = self.user_rooms.get(user_id)
        if room_id:
            return self.rooms.get(room_id)
        return None

    def get_waiting_rooms(self) -> list[Room]:
        return [r for r in self.rooms.values() if r.phase == RoomPhase.WAITING]

    def is_user_in_room(self, user_id: int) -> bool:
        return user_id in self.user_rooms

    # ---- Helpers ----

    def _get_game_over_reason(self, room: Room) -> str:
        """Determine the game over reason from game state."""
        if room.game_state is None:
            return "unknown"
        win_reason = room.game_state.win_reason
        if win_reason == WinReason.CHECKMATE:
            return "checkmate"
        if win_reason == WinReason.STALEMATE:
            return "stalemate"
        if win_reason == WinReason.RESIGN:
            return "resign"
        if win_reason == WinReason.PERPETUAL_CHECK:
            return "perpetual_check"
        if win_reason == WinReason.PERPETUAL_CHASE:
            return "perpetual_chase"
        if win_reason == WinReason.THREEFOLD_REPETITION:
            return "threefold_repetition"
        if win_reason == WinReason.FIFTY_MOVE:
            return "fifty_move"
        gr = room.game_state.game_result
        if gr in (GameResult.RED_TIMEOUT, GameResult.BLACK_TIMEOUT):
            return "timeout"
        if gr in (GameResult.RED_RESIGN, GameResult.BLACK_RESIGN):
            return "resign"
        return "unknown"

    @staticmethod
    def _player_info(player: Optional[PlayerSession]) -> Optional[dict]:
        """Get player info dict for messages."""
        if not player:
            return None
        return {
            "user_id": player.user_id,
            "username": player.username,
            "nickname": player.nickname,
            "avatar": player.avatar,
            "rating": player.rating,
            "is_bot": player.is_bot,
            "online": player.is_bot or player.is_connected,
        }

    # ---- State Persistence & Recovery ----

    # ---- Disconnect Timeout Checker ----

    def start_disconnect_checker(self) -> None:
        """Start the background task that checks for disconnected player timeouts."""
        if self._disconnect_checker_task and not self._disconnect_checker_task.done():
            return
        self._disconnect_checker_task = asyncio.create_task(self._disconnect_checker_loop())
        logger.info(f"Disconnect checker started (timeout={self.disconnect_timeout}s)")

    def stop_disconnect_checker(self) -> None:
        """Stop the disconnect checker."""
        if self._disconnect_checker_task and not self._disconnect_checker_task.done():
            self._disconnect_checker_task.cancel()
        self._disconnect_checker_task = None
        logger.info("Disconnect checker stopped")

    async def stop_all_rooms(self) -> None:
        """Cancel and wait for all active RoomRunner tasks to finish.

        This is used during application shutdown to ensure no room tasks
        are left running which would prevent the event loop from closing.
        """
        if not self.tasks:
            return

        logger.info(f"Stopping all room runners ({len(self.tasks)})...")
        # Cancel tasks
        for room_id, task in list(self.tasks.items()):
            try:
                if task and not task.done():
                    task.cancel()
            except Exception:
                pass

        # Wake up room waiters (move_event) to unblock _run_room loops
        for room in list(self.rooms.values()):
            try:
                if hasattr(room, 'move_event') and room.move_event:
                    room.move_event.set()
            except Exception:
                pass

        # Await tasks with a short timeout to avoid blocking shutdown.
        # Use asyncio.wait to collect which tasks finished and which are still pending.
        pending = set(self.tasks.values())
        if pending:
            try:
                done, pending = await asyncio.wait(pending, timeout=5.0)
            except Exception as e:
                logger.warning(f"Error while waiting for room tasks: {e}")

        # Log completed tasks
        for t in list(self.tasks.values()):
            if t.done():
                logger.info(f"Room runner task done: {t.get_name() or repr(t)}")

        # For any pending tasks, attempt one more cancel and collect stacks for diagnostics
        if pending:
            logger.warning(f"{len(pending)} room runner tasks did not exit within timeout; collecting diagnostics")
            for t in pending:
                try:
                    logger.warning(f"Pending task: {repr(t)}")
                    # Try cancel again
                    t.cancel()
                    # Capture stack frames for diagnostic
                    stacks = t.get_stack(limit=10)
                    if stacks:
                        for frame in stacks:
                            logger.warning("Task stack: %s", ''.join(logging.Formatter().formatStack(frame)))
                except Exception:
                    logger.exception("Error while inspecting pending task")

        self.tasks.clear()
        logger.info("All room runners stopped")

    async def _disconnect_checker_loop(self) -> None:
        """Periodically check for disconnected players whose timeout has expired."""
        try:
            while True:
                await asyncio.sleep(10)  # Check every 10 seconds
                await self._check_disconnect_timeouts()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Disconnect checker error: {e}", exc_info=True)

    async def _check_disconnect_timeouts(self) -> None:
        """Check all rooms for disconnected players whose timeout has expired.

        Rule 4:
        - PLAYING: real players use game clock timeout (handled by MoveTimer)
        - Other states: use config disconnect_timeout
        - After timeout, auto-leave → apply Rule 1
        """
        now = time.time()
        timeout = self.disconnect_timeout
        expired_players: list[tuple[Room, int]] = []

        for room in list(self.rooms.values()):
            # PLAYING: game clock handles timeout, skip disconnect checker
            if room.phase == RoomPhase.PLAYING:
                continue

            # Rule 1 early check: no real players → delete
            if self._should_delete_room(room):
                logger.info(f"Room {room.room_id} has no real players (phase={room.phase.name}), deleting")
                await self._cleanup_room(room, reason="disconnect_checker_no_real_players")
                continue

            # Check each disconnected real player
            for player in [room.red_player, room.black_player]:
                if (player and not player.is_bot
                        and not player.is_connected
                        and player.disconnected_at is not None):
                    elapsed = now - player.disconnected_at
                    if elapsed >= timeout:
                        expired_players.append((room, player.user_id))

        # Handle expired players (auto-leave → Rule 1 applied in leave_room)
        for room, user_id in expired_players:
            if room.room_id not in self.rooms:
                continue
            try:
                logger.info(f"Disconnect timeout: user={user_id} in room={room.room_id} "
                           f"(phase={room.phase.name}), auto-leave")
                await self.leave_room(room, user_id, reason="disconnect_timeout")
            except Exception as e:
                logger.error(f"Failed to handle disconnect timeout for user={user_id}: {e}", exc_info=True)

    async def _persist_room_state(self, room: Room) -> None:
        """Persist current game state to DB for server restart recovery."""
        if getattr(self, 'shutting_down', False):
            logger.debug(f"Skipping persist for {room.room_id} because shutting_down=True")
            return
        if not room.game_state:
            return
        try:
            moves = []
            for record in room.game_state.history:
                moves.append({
                    "from_col": record.move.from_col,
                    "from_row": record.move.from_row,
                    "to_col": record.move.to_col,
                    "to_row": record.move.to_row,
                })
            metadata = {
                "current_player": room.game_state.current_player,
                "started_at": room.started_at,
            }
            if room.timer:
                metadata["red_remaining"] = room.timer.red_remaining
                metadata["black_remaining"] = room.timer.black_remaining
            await self.room_repo.save_game_state(room.room_id, moves, metadata)
        except Exception as e:
            logger.warning(f"Failed to persist room state for {room.room_id}: {e}")

    async def restore_active_rooms(self) -> int:
        """Restore active rooms from DB on server startup.
        
        Returns:
            Number of rooms restored.
        """
        try:
            rows = await self.room_repo.get_active_rooms_with_state()
        except Exception as e:
            logger.error(f"Failed to load active rooms from DB: {e}")
            return 0

        restored = 0
        for row in rows:
            try:
                room_id = str(row["id"])
                room_type = RoomType.PVP if row["type"] == "pvp" else RoomType.PVE
                source = RoomSource.MATCH if row.get("source") == "match" else RoomSource.MANUAL
                initial_time = row.get("initial_time", 600)
                increment = row.get("increment", 10)
                difficulty = row.get("ai_difficulty")

                phase = RoomPhase.WAITING if row["status"] == "waiting" else RoomPhase.PLAYING

                room = Room(
                    room_id=room_id,
                    room_type=room_type,
                    source=source,
                    phase=phase,
                    initial_time=initial_time,
                    increment=increment,
                    difficulty=difficulty,
                )

                # Restore players (disconnected - they'll reconnect)
                red_id = row.get("red_user_id")
                black_id = row.get("black_user_id")

                if red_id is not None:
                    red_player = PlayerSession(
                        user_id=red_id,
                        username=row.get("red_username", "") or f"user_{red_id}",
                        nickname=row.get("red_nickname", ""),
                        _conn=None,
                    )
                    red_player.side = "red"
                    red_player.connected = False
                    red_player.disconnected_at = time.time()  # Server just started
                    room.red_player = red_player
                    self.user_rooms[red_id] = room_id

                if black_id is not None:
                    black_player = PlayerSession(
                        user_id=black_id,
                        username=row.get("black_username", "") or f"user_{black_id}",
                        nickname=row.get("black_nickname", ""),
                        _conn=None,
                    )
                    black_player.side = "black"
                    black_player.connected = False
                    black_player.disconnected_at = time.time()  # Server just started
                    room.black_player = black_player
                    self.user_rooms[black_id] = room_id

                # Restore game state for playing rooms
                if phase == RoomPhase.PLAYING:
                    room.init_game()

                    metadata = row.get("metadata")
                    if metadata and isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except Exception:
                            metadata = None

                    # Replay moves from moves_json
                    moves_json = row.get("moves_json")
                    if moves_json:
                        if isinstance(moves_json, str):
                            try:
                                moves_json = json.loads(moves_json)
                            except Exception:
                                moves_json = None
                        if moves_json and isinstance(moves_json, list):
                            for move_data in moves_json:
                                move = Move(
                                    from_col=move_data["from_col"],
                                    from_row=move_data["from_row"],
                                    to_col=move_data["to_col"],
                                    to_row=move_data["to_row"],
                                )
                                room.game_state.make_move(move)

                    # Restore started_at
                    if metadata and isinstance(metadata, dict):
                        room.started_at = metadata.get("started_at", 0)

                    # Set AI side for PvE rooms
                    if room_type == RoomType.PVE:
                        if black_id is None:
                            room.ai_side = Color.BLACK
                        elif red_id is None:
                            room.ai_side = Color.RED
                        else:
                            room.ai_side = Color.BLACK

                        # Restore AI name and avatar from difficulty
                        diff = difficulty or 3
                        room.ai_name, room.ai_avatar = self.AI_PROFILES.get(diff, self.AI_PROFILE_DEFAULT)

                    # Start room runner coroutine (will wait for players to reconnect)
                    task = asyncio.create_task(RoomRunner(self, room).run())
                    self.tasks[room_id] = task

                self.rooms[room_id] = room
                restored += 1
                logger.info(f"Restored room: {room_id}, phase={phase.name}, type={room_type.name}, "
                           f"red={red_id}, black={black_id}")

            except Exception as e:
                logger.error(f"Failed to restore room {row.get('id', '?')}: {e}", exc_info=True)

        logger.info(f"Restored {restored} active rooms from DB")
        return restored
