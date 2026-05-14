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


# Configure module logger
logger = logging.getLogger(__name__)


def _log(level: str, msg: str, **kwargs):
    """Structured logging helper."""
    parts = [msg]
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    log_msg = " | ".join(parts)
    getattr(logger, level)(log_msg)


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

            # Create session
            session = PlayerSession(
                user_id=user_id,
                username=username,
                token=token or "",
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

                # Join room
                _log("debug", "joining_room",
                     room_id=room_id,
                     session_id=session.session_id)

                room = await self.room_manager.get_room(room_id)
                if room is None:
                    _log("info", "creating_room",
                         room_id=room_id,
                         session_id=session.session_id)
                    room = await self.room_manager.create_room(room_id=room_id)

                success, msg = await self.room_manager.join_room(room_id, session)
                if not success:
                    _log("warning", "join_room_failed",
                         room_id=room_id,
                         session_id=session.session_id,
                         reason=msg)
                    await websocket.send_json(
                        out_msg.error_message(3001, msg)
                    )
                    return

                _log("info", "join_room_success",
                     room_id=room_id,
                     session_id=session.session_id,
                     side=session.side)

                # Send game start or wait message
                room = await self.room_manager.get_room(room_id)
                if room.state.value == "playing":
                    _log("info", "game_starting",
                         room_id=room_id,
                         session_id=session.session_id,
                         side=session.side)

                    await websocket.send_json(
                        out_msg.game_start_message(
                            room_id=room_id,
                            your_side=session.side or "red",
                            red_time=room.red_session.remaining_time if room.red_session else 600,
                            black_time=room.black_session.remaining_time if room.black_session else 600,
                        )
                    )

                    # Notify opponent
                    opponent = room.get_opponent_session(session.session_id)
                    if opponent and opponent.is_connected():
                        await self.connection_manager.send_to(
                            opponent.session_id,
                            out_msg.game_start_message(
                                room_id=room_id,
                                your_side=opponent.side or "black",
                                red_time=room.red_session.remaining_time if room.red_session else 600,
                                black_time=room.black_session.remaining_time if room.black_session else 600,
                            )
                        )
                        _log("info", "opponent_notified_game_start",
                             room_id=room_id,
                             opponent_session=opponent.session_id)
                else:
                    _log("debug", "waiting_for_opponent",
                         room_id=room_id,
                         session_id=session.session_id,
                         room_state=room.state.value)
                    await websocket.send_json({
                        "type": "waiting",
                        "data": {"room_id": room_id, "side": session.side},
                    })

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
                            await websocket.send_json(response)

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
                        await websocket.send_json(
                            out_msg.error_message(1000, str(e))
                        )

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
