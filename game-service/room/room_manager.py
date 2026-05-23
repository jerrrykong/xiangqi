"""Game Service v2.0 - Room Manager

Manages all active rooms in memory.
"""

import asyncio
import logging
import uuid
from typing import Dict, Optional

from chess.constants import Color, GameResult
from chess.game import ChessGame
from chess.move import Move
from chess.move_validator import MoveValidator
from chess.win_checker import WinChecker
from chess.piece import create_initial_board, board_to_fen
from ai.ai_proxy import AIProxy
from room.room import Room, RoomPhase, RoomSource, RoomType
from room.player_session import PlayerSession
from room.timers import MoveTimer
from user.elo_repository import EloRepository
from room.room_repository import RoomRepository, GameRepository
from user.user_service import UserService

logger = logging.getLogger(__name__)


class RoomManager:
    """Manages all active rooms in memory.

    Rooms are the sole carrier of a game from creation to finish.
    """

    def __init__(self, room_repo: RoomRepository, game_repo: GameRepository,
                 elo_repo: EloRepository, user_service: UserService):
        self.rooms: Dict[str, Room] = {}
        self.user_rooms: Dict[int, str] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.ai_proxy = AIProxy()
        self.room_repo = room_repo
        self.game_repo = game_repo
        self.elo_repo = elo_repo
        self.user_service = user_service

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

        # Start room coroutine
        task = asyncio.create_task(self._run_room(room))
        self.tasks[room_id] = task

        return room

    async def create_pve_room(self, player: PlayerSession, player_side: str = "red",
                              difficulty: int = 3,
                              initial_time: int = 600,
                              increment: int = 10) -> Room:
        """Create a PvE room (directly enters PLAYING)."""
        room_id = str(uuid.uuid4())
        room = Room(
            room_id=room_id,
            room_type=RoomType.PVE,
            source=RoomSource.MANUAL,
            phase=RoomPhase.PLAYING,
            difficulty=difficulty,
            initial_time=initial_time,
            increment=increment,
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

        task = asyncio.create_task(self._run_room(room))
        self.tasks[room_id] = task

        return room

    # ---- Room Join ----

    async def join_room(self, room_id: str, player: PlayerSession) -> Optional[Room]:
        """Join a manual room. Automatically starts the game."""
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

        # Start the game
        room.init_game()

        # Persist
        try:
            await self.room_repo.join_room(room_id, player.user_id, "black")
            await self.room_repo.start_game(room_id)
        except Exception as e:
            logger.warning(f"Failed to persist room join: {e}")

        # Start room coroutine
        task = asyncio.create_task(self._run_room(room))
        self.tasks[room_id] = task

        return room

    # ---- Room Coroutine ----

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
            fen = board_to_fen(room.game_state.board)
            for player in [room.red_player, room.black_player]:
                if player and player.is_connected:
                    side = player.side
                    await player.send({
                        "type": "game_start",
                        "data": {
                            "room_id": room.room_id,
                            "your_side": side,
                            "red_player": self._player_info(room.red_player),
                            "black_player": self._player_info(room.black_player),
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
            logger.info(f"Room {room.room_id} coroutine cancelled")
        except Exception as e:
            logger.exception(f"Room {room.room_id} error: {e}")
        finally:
            if room.timer:
                room.timer.stop()
            await self._cleanup_room(room)

    # ---- Move Handling ----

    async def apply_player_move(self, room: Room, move: Move) -> None:
        """Apply a player's move. Called by RoomHandler."""
        logger.debug(f"Applying move in room={room.room_id}: ({move.from_row},{move.from_col})->({move.to_row},{move.to_col})")
        await self._apply_and_broadcast_move(room, move, "opponent_move")
        room.move_event.set()

    async def _do_ai_move(self, room: Room) -> None:
        """AI makes a move."""
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

        room.timer.switch_side()

        fen = board_to_fen(room.game_state.board)
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
                },
            })

        # Check game over after AI move
        if room.game_state.is_game_over:
            await self._handle_game_over(room, self._get_game_over_reason(room))

    async def _apply_and_broadcast_move(self, room: Room, move: Move,
                                        msg_type: str) -> None:
        """Execute a move and broadcast to both players."""
        success, error = room.game_state.make_move(move)
        if not success:
            logger.warning(f"Move failed in room {room.room_id}: {error}")
            return

        room.timer.switch_side()

        fen = board_to_fen(room.game_state.board)

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
                },
            })

        # Check game over
        if room.game_state.is_game_over:
            await self._handle_game_over(room, self._get_game_over_reason(room))

    # ---- Game Over ----

    async def _handle_game_over(self, room: Room, reason: str) -> None:
        """Handle game over: determine winner, broadcast, save to DB."""
        room.phase = RoomPhase.FINISHED
        if room.timer:
            room.timer.stop()

        winner = "draw"
        logger.info(f"Game over: room={room.room_id}, reason={reason}, computing winner...")
        game_result = room.game_state.game_result if room.game_state else None

        if game_result in (GameResult.RED_WINS, "RED_WINS"):
            winner = "red"
        elif game_result in (GameResult.BLACK_WINS, "BLACK_WINS"):
            winner = "black"

        # Broadcast game_over
        logger.info(f"Game over broadcast: room={room.room_id}, winner={winner}, reason={reason}, moves={room.game_state.move_count if room.game_state else 0}")
        await self._broadcast(room, {
            "type": "game_over",
            "data": {
                "room_id": room.room_id,
                "winner": winner,
                "reason": reason,
                "total_moves": room.game_state.move_count if room.game_state else 0,
            },
        })

        # Save to DB and update ELO
        await self._save_game_result(room, winner, reason)

    async def _save_game_result(self, room: Room, winner: str, reason: str) -> None:
        """Save game result to database and update ELO ratings."""
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

        # ELO calculation for PvP
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

            result = 1.0 if winner == "red" else (0.0 if winner == "black" else 0.5)
            red_rating_change, black_rating_change = UserService.calculate_elo(
                red_rating_before, black_rating_before, result, red_elo["games_count"],
            )
            red_rating_after = red_rating_before + red_rating_change
            black_rating_after = black_rating_before + black_rating_change

            # Update ELO in DB
            await self.elo_repo.update_rating(
                red_user_id, red_rating_after,
                red_elo["games_count"] + 1,
            )
            await self.elo_repo.update_rating(
                black_user_id, black_rating_after,
                black_elo["games_count"] + 1,
            )

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
                if player and player.is_connected:
                    await player.send({
                        "type": "rating_update",
                        "data": {
                            "rating": new_rating,
                            "change": change,
                            "games_count": (red_elo if player.side == "red" else black_elo)["games_count"] + 1,
                        },
                    })

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

        await self._handle_game_over(room, "timeout")
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

    async def _cleanup_room(self, room: Room) -> None:
        """Clean up room resources."""
        logger.info(f"Cleaning up room={room.room_id}")
        room.phase = RoomPhase.FINISHED
        for player in [room.red_player, room.black_player]:
            if player:
                self.user_rooms.pop(player.user_id, None)
        self.rooms.pop(room.room_id, None)
        self.tasks.pop(room.room_id, None)

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
        gr = room.game_state.game_result
        if gr in (GameResult.RED_WINS, GameResult.BLACK_WINS):
            return "checkmate"
        if gr == GameResult.DRAW:
            return "stalemate"
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
            "rating": player.rating,
        }
