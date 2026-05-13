"""WebSocket server for real-time game communication."""
import asyncio
import json
import logging
import time
from typing import Optional, Dict, Callable, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState
import uvicorn

from .room_manager import RoomManager
from .message_handler import MessageHandler
from .player_session import PlayerSession, ConnectionState
from .protocol import outbound as out_msg


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages all active WebSocket connections."""

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}  # session_id -> websocket
        self._sessions: Dict[str, PlayerSession] = {}  # session_id -> session
        self._lock = asyncio.Lock()

    async def connect(self, session: PlayerSession, websocket: WebSocket) -> None:
        """Register a new connection."""
        async with self._lock:
            self._connections[session.session_id] = websocket
            self._sessions[session.session_id] = session
            session.websocket = websocket
            session.state = ConnectionState.CONNECTED
            session.update_activity()

    async def disconnect(self, session_id: str) -> None:
        """Remove a connection."""
        async with self._lock:
            if session_id in self._connections:
                del self._connections[session_id]
            if session_id in self._sessions:
                self._sessions[session_id].state = ConnectionState.DISCONNECTED
                self._sessions[session_id].websocket = None

    async def send_to(self, session_id: str, data: dict) -> bool:
        """Send a message to a specific session."""
        async with self._lock:
            ws = self._connections.get(session_id)
            if ws is None:
                return False
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(data)
                    return True
            except Exception as e:
                logger.warning(f"Failed to send to {session_id}: {e}")
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
            return

        targets = []
        if room.red_session:
            targets.append(room.red_session.session_id)
        if room.black_session:
            targets.append(room.black_session.session_id)

        for session_id in targets:
            if session_id != exclude_session:
                await self.send_to(session_id, data)

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

        self.app = FastAPI(title="Xiangqi Game Service")
        self.room_manager = RoomManager()
        self.message_handler = MessageHandler(self.room_manager)
        self.connection_manager = ConnectionManager()

        self._setup_routes()
        self._setup_game_callback()

    def _setup_game_callback(self) -> None:
        """Setup callback for game over events."""
        async def on_game_over(room):
            """Called when a game ends."""
            logger.info(f"Game over in room {room.room_id}: {room.result}")

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
            "game_id": room.room_id,  # Using room_id as game_id for now
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
                await client.post(
                    self.game_callback_url,
                    json=payload,
                    timeout=5.0,
                )
                logger.info(f"Game result callback sent for room {room.room_id}")
        except Exception as e:
            logger.warning(f"Failed to send game result callback: {e}")

    async def _cleanup_room(self, room_id: str) -> None:
        """Clean up a room after game ends."""
        await asyncio.sleep(300)  # Keep room for 5 minutes for reconnect
        room = await self.room_manager.get_room(room_id)
        if room and room.state.value == "finished":
            room.cleanup()
            logger.info(f"Room {room_id} cleaned up")

    def _setup_routes(self) -> None:
        """Setup FastAPI routes."""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "ok",
                "active_connections": self.connection_manager.active_connections,
                "active_rooms": self.room_manager.count_active_rooms(),
            }

        @self.app.get("/stats")
        async def stats():
            """Server statistics."""
            return {
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
            # Create session
            session = PlayerSession(
                user_id=user_id,
                username=username,
                token=token or "",
            )

            await websocket.accept()

            # Check if reconnecting
            reconnect_data = None
            try:
                first_msg = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=10.0,
                )
                if first_msg.get("type") == "reconnect":
                    reconnect_data = first_msg
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

            # Connect
            await self.connection_manager.connect(session, websocket)
            logger.info(
                f"Client connected: session={session.session_id}, "
                f"user={username}, room={room_id}"
            )

            try:
                # Handle reconnection if needed
                if reconnect_data:
                    data = reconnect_data.get("data", {})
                    success, response = await self.message_handler.handle(
                        session, {"type": "reconnect", "data": data}
                    )
                    if success:
                        await websocket.send_json(response)
                    else:
                        await websocket.send_json(response)
                        return

                # Join room
                room = await self.room_manager.get_room(room_id)
                logger.info(f"[DEBUG] get_room({room_id}) = {room}")
                if room is None:
                    room = await self.room_manager.create_room(room_id=room_id)
                    logger.info(f"[DEBUG] created room: {room}")

                success, msg = await self.room_manager.join_room(room_id, session)
                logger.info(f"[DEBUG] join_room result: success={success}, msg={msg}, session.side={session.side}")
                if not success:
                    await websocket.send_json(
                        out_msg.error_message(3001, msg)
                    )
                    return

                # Send game start or wait message
                room = await self.room_manager.get_room(room_id)
                if room.state.value == "playing":
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
                else:
                    await websocket.send_json({
                        "type": "waiting",
                        "data": {"room_id": room_id, "side": session.side},
                    })

                # Message loop
                while True:
                    try:
                        data = await websocket.receive_json()
                        session.update_activity()

                        response = await self.message_handler.handle(session, data)
                        if response:
                            await websocket.send_json(response)

                    except WebSocketDisconnect:
                        logger.info(f"Client disconnected: {session.session_id}")
                        break
                    except Exception as e:
                        logger.error(f"Error in message loop: {e}", exc_info=True)
                        await websocket.send_json(
                            out_msg.error_message(1000, str(e))
                        )

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {session.session_id}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
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

                await self.connection_manager.disconnect(session.session_id)

    def run(self) -> None:
        """Run the server."""
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
