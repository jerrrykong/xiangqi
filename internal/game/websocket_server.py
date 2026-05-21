"""WebSocket server for real-time game communication."""
import asyncio
import json
import logging
import time
import uuid
from typing import Optional, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState
import uvicorn

from .room_manager import RoomManager
from .message_handler import MessageHandler
from .player_session import PlayerSession, ConnectionState
from .protocol import outbound as out_msg


# Configure module logger — must add handler so logs appear in uvicorn output
_logger = logging.getLogger(__name__)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S"
))
_logger.addHandler(_handler)
_logger.setLevel(logging.DEBUG)  # Capture all levels for diagnostics
# Don't propagate to root to avoid double-printing with uvicorn
_logger.propagate = False

def _log(level: str, msg: str, **kwargs):
    """Structured logging helper."""
    parts = [msg]
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    log_msg = " | ".join(parts)
    getattr(_logger, level)(log_msg)

class ConnectionManager:
    """Manages all active WebSocket connections."""

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}  # session_id -> websocket
        self._sessions: Dict[str, PlayerSession] = {}  # session_id -> session
        self._lock = asyncio.Lock()
        _log("debug", "connection_manager_init")

    async def connect(self, session: PlayerSession, websocket: WebSocket) -> None:
        """Register a new connection."""
        async with self._lock:
            self._connections[session.session_id] = websocket
            self._sessions[session.session_id] = session
            session.websocket = websocket
            session.state = ConnectionState.CONNECTED
            session.update_activity()
            _log("info", "session_connected",
                 session_id=session.session_id,
                 user_id=session.user_id,
                 username=session.username)

    async def disconnect(self, session_id: str) -> None:
        """Remove a connection."""
        async with self._lock:
            user_id = None
            if session_id in self._sessions:
                user_id = self._sessions[session_id].user_id
                self._sessions[session_id].state = ConnectionState.DISCONNECTED
                self._sessions[session_id].websocket = None
            if session_id in self._connections:
                del self._connections[session_id]
            _log("info", "session_disconnected",
                 session_id=session_id,
                 user_id=user_id)

    async def send_to(self, session_id: str, data: dict) -> bool:
        """Send a message to a specific session."""
        async with self._lock:
            ws = self._connections.get(session_id)
            if ws is None:
                _log("warning", "send_to_session_not_found",
                     session_id=session_id)
                return False
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(data)
                    _log("debug", "message_sent",
                         session_id=session_id,
                         msg_type=data.get("type"))
                    return True
            except Exception as e:
                _log("error", "send_to_error",
                     session_id=session_id,
                     error=str(e))
        return False

    async def broadcast_to_room(
        self,
        room_id: str,
        data: dict,
        room_manager: RoomManager,
        exclude_session: Optional[str] = None,
    ) -> None:
        """Broadcast a message to all sessions in a room."""
        room = await room_manager.get_room(room_id)
        if room is None:
            _log("warning", "broadcast_room_not_found",
                 room_id=room_id)
            return

        targets = []
        if room.red_session:
            targets.append(room.red_session.session_id)
        if room.black_session:
            targets.append(room.black_session.session_id)

        for session_id in targets:
            if session_id != exclude_session:
                await self.send_to(session_id, data)

        _log("debug", "broadcast_to_room",
             room_id=room_id,
             msg_type=data.get("type"),
             recipients=len(targets))

    def get_session(self, session_id: str) -> Optional[PlayerSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    @property
    def active_connections(self) -> int:
        """Get the count of active connections."""
        return len(self._connections)


class GameWebSocketServer:
    """Main WebSocket server for game communication."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8081,
        game_callback_url: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.game_callback_url = game_callback_url
        self.server_id = str(uuid.uuid4())[:8]

        self.app = FastAPI(title="Xiangqi Game Service")
        self.room_manager = RoomManager()
        self.message_handler = MessageHandler(self.room_manager)
        self.connection_manager = ConnectionManager()
        # room_id -> { user_id -> {"side": str, "token": str, "username": str} }
        self._pre_assigned: Dict[str, Dict[int, dict]] = {}

        _log("info", "game_server_init",
             server_id=self.server_id,
             host=host,
             port=port,
             callback_url=game_callback_url)

        self._setup_routes()
        self._setup_game_callback()

    def _setup_game_callback(self) -> None:
        """Setup callback for game over events."""
        async def on_game_over(room):
            """Called when a game ends."""
            _log("info", "game_over_event",
                 room_id=room.room_id,
                 result=room.result,
                 winner=room.winner,
                 reason=room.reason)

            # Notify both players
            game_over_msg = out_msg.game_over_message(
                winner=room.winner or "none",
                result=room.result or "",
                reason=room.reason or "",
            )

            await self.connection_manager.broadcast_to_room(
                room.room_id,
                game_over_msg,
                self.room_manager,
            )

            # Send result to Web service callback
            if self.game_callback_url:
                await self._send_game_result_callback(room)

            # Schedule room cleanup
            asyncio.create_task(self._cleanup_room(room.room_id))

        # This would be set as the callback for all rooms
        # self.room_manager.set_game_over_callback(on_game_over)

    async def _send_game_result_callback(self, room) -> None:
        """Send game result to Web service callback."""
        import httpx

        payload = {
            "room_id": room.room_id,
            "game_id": room.room_id,
            "result": room.result or "",
            "winner": room.winner or "none",
            "red_user_id": room.red_session.user_id if room.red_session else None,
            "black_user_id": room.black_session.user_id if room.black_session else None,
            "total_moves": room.game.move_count if room.game else 0,
            "duration_seconds": int(room.ended_at - room.started_at) if room.ended_at and room.started_at else 0,
            "pve_level": room.difficulty if room.room_type == "pve" else None,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.game_callback_url,
                    json=payload,
                    timeout=5.0,
                )
                _log("info", "game_result_callback_sent",
                     room_id=room.room_id,
                     status_code=response.status_code)
        except Exception as e:
            _log("error", "game_result_callback_failed",
                 room_id=room.room_id,
                 error=str(e))

    async def _cleanup_room(self, room_id: str) -> None:
        """Clean up a room after game ends."""
        _log("debug", "cleanup_room_scheduled",
             room_id=room_id,
             delay_seconds=300)
        await asyncio.sleep(300)  # Keep room for 5 minutes for reconnect
        room = await self.room_manager.get_room(room_id)
        if room and room.state.value == "finished":
            room.cleanup()
            _log("info", "room_cleaned_up",
                 room_id=room_id)

    def _setup_routes(self) -> None:
        """Setup FastAPI routes."""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "ok",
                "server_id": self.server_id,
                "active_connections": self.connection_manager.active_connections,
                "active_rooms": self.room_manager.count_active_rooms(),
            }

        @self.app.get("/stats")
        async def stats():
            """Server statistics."""
            return {
                "server_id": self.server_id,
                "active_connections": self.connection_manager.active_connections,
                "active_rooms": self.room_manager.count_active_rooms(),
            }

        @self.app.post("/internal/game/assign")
        async def assign_game(request: dict):
            """
            HTTP endpoint for game assignment from Web service.

            Request body:
            {
                "room_id": str,
                "game_type": "pvp" | "pve",
                "players": [{"user_id": int, "username": str, "side": "red" | "black"}],
                "callback_url": str,
                "difficulty"?: int (for PvE)
            }
            """
            room_id = request.get("room_id")
            game_type = request.get("game_type", "pvp")
            players = request.get("players", [])
            callback_url = request.get("callback_url")
            difficulty = request.get("difficulty")

            _log("info", "http_assign_game_request",
                 room_id=room_id,
                 game_type=game_type,
                 player_count=len(players),
                 difficulty=difficulty)

            # Generate session token and WebSocket URL
            import secrets
            session_token = secrets.token_urlsafe(32)
            ws_url = f"ws://localhost:{self.port}/game/{room_id}"

            # Create room in room manager
            room = await self.room_manager.create_room(room_id=room_id, room_type=game_type)

            # Assign sides to players — each gets their own token
            import secrets
            self._pre_assigned[room_id] = {}
            for player in players:
                player_token = secrets.token_urlsafe(32)
                uid = player.get("user_id")
                side = player.get("side", "red")
                uname = player.get("username", "")
                self._pre_assigned[room_id][uid] = {
                    "side": side,
                    "token": player_token,
                    "username": uname,
                }
                _log("info", "player_pre_assigned",
                     room_id=room_id,
                     user_id=uid,
                     user_id_type=type(uid).__name__,
                     side=side)

            # Return per-player token mapping so Web service can pass them individually
            # For now we still return a single token (Web service uses same token for both)
            # but also expose per-player tokens in the response
            player_tokens = {
                str(uid): info["token"]
                for uid, info in self._pre_assigned[room_id].items()
            }

            # Log all pre_assigned keys with their types for debugging
            pre_keys = list(self._pre_assigned.get(room_id, {}).keys())
            _log("info", "pre_assigned_keys_for_room",
                 room_id=room_id,
                 keys=pre_keys,
                 key_types=[type(k).__name__ for k in pre_keys])

            _log("info", "http_assign_game_success",
                 room_id=room_id,
                 game_id=room_id,
                 ws_url=ws_url,
                 player_count=len(players))

            # Use a shared placeholder token — real validation uses user_id
            return {
                "room_id": room_id,
                "ws_url": ws_url,
                "game_id": room_id,
                "session_token": "multi",  # placeholder; real tokens in player_tokens
                "player_tokens": player_tokens,
            }

        @self.app.websocket("/game/{room_id}")
        async def websocket_endpoint(
            websocket: WebSocket,
            room_id: str,
            token: str = Query(None),
            user_id: int = Query(None),
            username: str = Query(None),
        ):
            """
            Main WebSocket endpoint for game communication.

            Query parameters:
            - token: Session token for authentication
            - user_id: User ID
            - username: Username
            """
            start_time = time.time()

            _log("info", "websocket_connection_start",
                 room_id=room_id,
                 user_id=user_id,
                 username=username,
                 token_provided=bool(token))

            # Create session — look up pre-assigned side by user_id
            # Try both int and str forms of user_id to handle type mismatches
            pre_info = None
            if user_id is not None:
                room_pre = self._pre_assigned.get(room_id, {})
                # Log full lookup context
                _log("info", "pre_assigned_lookup_start",
                     room_id=room_id,
                     user_id=user_id,
                     user_id_type=type(user_id).__name__,
                     room_pre_keys=list(room_pre.keys()),
                     room_pre_key_types=[type(k).__name__ for k in room_pre.keys()])
                pre_info = room_pre.get(user_id) or room_pre.get(str(user_id))
                _log("info", "pre_assigned_lookup_result",
                     room_id=room_id,
                     user_id=user_id,
                     pre_info_found=pre_info is not None,
                     pre_info_side=pre_info["side"] if pre_info else None)
            assigned_side = pre_info["side"] if pre_info else None
            assigned_username = (pre_info["username"] if pre_info else None) or username or ""

            _log("info", "session_creating",
                 room_id=room_id,
                 user_id=user_id,
                 assigned_side=assigned_side,
                 assigned_username=assigned_username)

            session = PlayerSession(
                user_id=user_id,
                username=assigned_username,
                token=token or "",
                side=assigned_side,
            )

            await websocket.accept()

            _log("debug", "websocket_accepted",
                 room_id=room_id,
                 session_id=session.session_id)

            # Check if reconnecting
            reconnect_data = None
            try:
                first_msg = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=10.0,
                )
                if first_msg.get("type") == "reconnect":
                    reconnect_data = first_msg
                    _log("info", "reconnect_attempt",
                         room_id=room_id,
                         session_id=session.session_id)
            except asyncio.TimeoutError:
                _log("debug", "first_message_timeout",
                     room_id=room_id,
                     session_id=session.session_id)
            except Exception as e:
                _log("warning", "first_message_error",
                     room_id=room_id,
                     session_id=session.session_id,
                     error=str(e))

            # Connect
            await self.connection_manager.connect(session, websocket)

            try:
                # Handle reconnection if needed
                if reconnect_data:
                    data = reconnect_data.get("data", {})
                    success, response = await self.message_handler.handle(
                        session, {"type": "reconnect", "data": data}
                    )
                    if success:
                        await websocket.send_json(response)
                        _log("info", "reconnect_success",
                             room_id=room_id,
                             session_id=session.session_id)
                    else:
                        await websocket.send_json(response)
                        _log("warning", "reconnect_failed",
                             room_id=room_id,
                             session_id=session.session_id,
                             response=response)
                        return

                # Join room — use pre-assigned side if available, else fallback
                _log("debug", "joining_room",
                     room_id=room_id,
                     session_id=session.session_id,
                     pre_assigned_side=assigned_side)

                room = await self.room_manager.get_room(room_id)
                if room is None:
                    _log("info", "creating_room",
                         room_id=room_id,
                         session_id=session.session_id)
                    room = await self.room_manager.create_room(room_id=room_id)

                if assigned_side:
                    # Pre-assigned: directly claim the specified side
                    success, msg = await self.room_manager.assign_side(room_id, session, assigned_side)
                else:
                    # Fallback: auto-assign (first come first served)
                    success, msg = await self.room_manager.join_room(room_id, session)

                if not success:
                    _log("warning", "join_room_failed",
                         room_id=room_id,
                         session_id=session.session_id,
                         reason=msg)
                    # Check if WebSocket is still connected before sending
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(
                            out_msg.error_message(3001, msg)
                        )
                    else:
                        _log("warning", "websocket_closed_before_send",
                             room_id=room_id,
                             session_id=session.session_id)
                    return

                # Ensure session.side is set correctly after assign_side/join_room
                # This is a safety net: if side is still None, derive it from the room
                if session.side is None:
                    _log("warning", "session_side_none_after_join",
                         room_id=room_id,
                         session_id=session.session_id,
                         assigned_side=assigned_side)
                    # Try to derive side from room
                    room = await self.room_manager.get_room(room_id)
                    if room:
                        if room.red_session and room.red_session.session_id == session.session_id:
                            session.side = "red"
                        elif room.black_session and room.black_session.session_id == session.session_id:
                            session.side = "black"
                        else:
                            # Fallback: assign based on which side is empty
                            if room.red_session is None:
                                session.side = "red"
                            elif room.black_session is None:
                                session.side = "black"
                            else:
                                session.side = "red"  # last resort
                        _log("warning", "session_side_recovered",
                             room_id=room_id,
                             session_id=session.session_id,
                             recovered_side=session.side)

                _log("info", "join_room_success",
                     room_id=room_id,
                     session_id=session.session_id,
                     side=session.side,
                     assigned_side=assigned_side)

                # Detailed room state snapshot
                _log("info", "room_state_snapshot_after_join",
                     room_id=room_id,
                     room_state=room.state.value,
                     red_session_id=room.red_session.session_id if room.red_session else None,
                     red_user_id=room.red_session.user_id if room.red_session else None,
                     red_side=room.red_session.side if room.red_session else None,
                     black_session_id=room.black_session.session_id if room.black_session else None,
                     black_user_id=room.black_session.user_id if room.black_session else None,
                     black_side=room.black_session.side if room.black_session else None,
                     current_session_id=session.session_id,
                     current_side=session.side)

                # Send game start or wait message
                room = await self.room_manager.get_room(room_id)
                if room.state.value == "playing":
                    _log("info", "game_starting",
                         room_id=room_id,
                         session_id=session.session_id,
                         side=session.side)

                    # Ensure session.side is valid before sending
                    if not session.side:
                        _log("error", "session_side_invalid_before_game_start",
                             room_id=room_id,
                             session_id=session.session_id,
                             side=session.side)
                        # Check if WebSocket is still connected before sending
                        if websocket.client_state == WebSocketState.CONNECTED:
                            await websocket.send_json(
                                out_msg.error_message(3002, "Internal error: side not assigned")
                            )
                        else:
                            _log("warning", "websocket_closed_before_send",
                                 room_id=room_id,
                                 session_id=session.session_id)
                        return

                    your_side = session.side
                    game_start_msg = out_msg.game_start_message(
                        room_id=room_id,
                        your_side=your_side,
                        red_time=room.red_session.remaining_time if room.red_session else 600,
                        black_time=room.black_session.remaining_time if room.black_session else 600,
                    )
                    _log("info", "sending_game_start_to_client",
                         room_id=room_id,
                         session_id=session.session_id,
                         your_side=your_side,
                         msg_type=game_start_msg.get("type"),
                         msg_your_color=game_start_msg.get("your_color"),
                         msg_room_id=game_start_msg.get("room_id"))
                    # Check if WebSocket is still connected before sending
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(game_start_msg)
                    else:
                        _log("warning", "websocket_closed_before_send",
                             room_id=room_id,
                             session_id=session.session_id,
                             client_state=websocket.client_state.value)
                        return

                    # Notify opponent
                    opponent = room.get_opponent_session(session.session_id)
                    if opponent and opponent.is_connected():
                        # Ensure opponent.side is valid
                        if not opponent.side:
                            _log("error", "opponent_side_invalid_before_notify",
                                 room_id=room_id,
                                 opponent_session=opponent.session_id,
                                 side=opponent.side)
                            # Try to recover
                            if room.red_session and room.red_session.session_id == opponent.session_id:
                                opponent.side = "red"
                            elif room.black_session and room.black_session.session_id == opponent.session_id:
                                opponent.side = "black"

                        opponent_msg = out_msg.game_start_message(
                            room_id=room_id,
                            your_side=opponent.side,
                            red_time=room.red_session.remaining_time if room.red_session else 600,
                            black_time=room.black_session.remaining_time if room.black_session else 600,
                        )
                        _log("info", "sending_game_start_to_opponent",
                             room_id=room_id,
                             opponent_session=opponent.session_id,
                             opponent_side=opponent.side,
                             opponent_your_color=opponent_msg.get("your_color"))
                        await self.connection_manager.send_to(
                            opponent.session_id,
                            opponent_msg
                        )
                        _log("info", "opponent_notified_game_start",
                             room_id=room_id,
                             opponent_session=opponent.session_id,
                             opponent_side=opponent.side)
                else:
                    _log("debug", "waiting_for_opponent",
                         room_id=room_id,
                         session_id=session.session_id,
                         room_state=room.state.value)

                    # Ensure session.side is valid before sending waiting message
                    if not session.side:
                        _log("error", "session_side_invalid_before_waiting",
                             room_id=room_id,
                             session_id=session.session_id,
                             side=session.side)
                        # Check if WebSocket is still connected before sending
                        if websocket.client_state == WebSocketState.CONNECTED:
                            await websocket.send_json(
                                out_msg.error_message(3002, "Internal error: side not assigned"))
                        else:
                            _log("warning", "websocket_closed_before_send",
                                 room_id=room_id,
                                 session_id=session.session_id)
                        return

                    waiting_msg = out_msg.waiting_message(room_id=room_id, side=session.side)
                    _log("info", "sending_waiting_message",
                         room_id=room_id,
                         session_id=session.session_id,
                         your_side=session.side,
                         msg_your_color=waiting_msg.get("your_color"),
                         msg_room_id=waiting_msg.get("room_id"))
                    # Check if WebSocket is still connected before sending
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(waiting_msg)
                    else:
                        _log("warning", "websocket_closed_before_send",
                             room_id=room_id,
                             session_id=session.session_id,
                             client_state=websocket.client_state.value)

                # Message loop
                message_count = 0
                while True:
                    try:
                        data = await websocket.receive_json()
                        session.update_activity()
                        message_count += 1

                        _log("debug", "message_received",
                             room_id=room_id,
                             session_id=session.session_id,
                             msg_type=data.get("type"),
                             message_count=message_count)

                        response = await self.message_handler.handle(session, data)
                        if response:
                            _log("debug", "message_response_sent",
                                 room_id=room_id,
                                 session_id=session.session_id,
                                 msg_type=response.get("type"))
                            # Check if WebSocket is still connected before sending
                            if websocket.client_state == WebSocketState.CONNECTED:
                                await websocket.send_json(response)
                            else:
                                _log("warning", "websocket_closed_before_send",
                                     room_id=room_id,
                                     session_id=session.session_id,
                                     msg_type=response.get("type"))

                    except WebSocketDisconnect:
                        duration = time.time() - start_time
                        _log("info", "client_disconnected",
                             room_id=room_id,
                             session_id=session.session_id,
                             duration_seconds=round(duration, 2),
                             messages_received=message_count)
                        break
                    except Exception as e:
                        _log("error", "message_loop_error",
                             room_id=room_id,
                             session_id=session.session_id,
                             error=str(e),
                             error_type=type(e).__name__)
                        # Check if WebSocket is still connected before sending
                        if websocket.client_state == WebSocketState.CONNECTED:
                            await websocket.send_json(
                                out_msg.error_message(1000, str(e))
                            )
                        else:
                            _log("warning", "websocket_closed_before_send",
                                 room_id=room_id,
                                 session_id=session.session_id)

            except WebSocketDisconnect:
                duration = time.time() - start_time
                _log("info", "websocket_disconnected",
                     room_id=room_id,
                     session_id=session.session_id,
                     duration_seconds=round(duration, 2))
            except Exception as e:
                duration = time.time() - start_time
                _log("error", "websocket_error",
                     room_id=room_id,
                     session_id=session.session_id,
                     error=str(e),
                     error_type=type(e).__name__,
                     duration_seconds=round(duration, 2))
            finally:
                # Mark as disconnected but keep session for reconnect
                session.disconnect()

                # Notify opponent
                room = await self.room_manager.get_room_by_session(session.session_id)
                if room:
                    opponent = room.get_opponent_session(session.session_id)
                    if opponent and opponent.is_connected():
                        await self.connection_manager.send_to(
                            opponent.session_id,
                            out_msg.opponent_left_message(
                                reason="disconnect",
                                timeout=60,
                            )
                        )
                        _log("info", "opponent_notified_disconnect",
                             room_id=room_id,
                             opponent_session=opponent.session_id,
                             reason="disconnect")

                await self.connection_manager.disconnect(session.session_id)

    def run(self) -> None:
        """Run the server."""
        _log("info", "server_starting",
             host=self.host,
             port=self.port)
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        asyncio.run(server.serve())


# Convenience function
def create_server(
    host: str = "0.0.0.0",
    port: int = 8081,
    game_callback_url: Optional[str] = None,
) -> GameWebSocketServer:
    """Create and configure a game WebSocket server."""
    return GameWebSocketServer(host=host, port=port, game_callback_url=game_callback_url)


# Expose app for uvicorn CLI
app = create_server().app
