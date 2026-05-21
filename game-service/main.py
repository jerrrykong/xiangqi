"""Game Service v2.0 - Main Entry Point

Integrates all modules and starts the FastAPI application with WebSocket support.
"""

import sys
import os
import json
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

# Add game-service root to Python path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response

from config import load_config, Config
from db.database import Database
from gateway.connection_manager import ConnectionManager, ClientConnection
from gateway.connection_state import ConnectionState
from gateway.message_router import MessageRouter
from auth.jwt_manager import JWTManager
from auth.auth_service import AuthService
from auth.auth_handler import AuthHandler
from user.user_repository import UserRepository
from user.elo_repository import EloRepository
from user.user_service import UserService
from user.user_handler import UserHandler
from room.room_repository import RoomRepository, GameRepository, ModelRepository
from room.room_manager import RoomManager
from room.room_handler import RoomHandler
from match.match_service import MatchService
from match.match_handler import MatchHandler
from admin.admin_service import AdminService
from admin.admin_handler import AdminHandler

logger = logging.getLogger(__name__)

# ---- Global Instances ----

config: Config = None
db: Database = None
connection_manager: ConnectionManager = None
jwt_manager: JWTManager = None
message_router: MessageRouter = None

# Repositories
user_repo: UserRepository = None
elo_repo: EloRepository = None
room_repo: RoomRepository = None
game_repo: GameRepository = None
model_repo: ModelRepository = None

# Services
auth_service: AuthService = None
user_service: UserService = None
room_manager: RoomManager = None
match_service: MatchService = None
admin_service: AdminService = None

# Handlers
auth_handler: AuthHandler = None
user_handler: UserHandler = None
room_handler: RoomHandler = None
match_handler: MatchHandler = None
admin_handler: AdminHandler = None


def setup_logging(config: Config) -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, config.logging.level, logging.INFO),
        format=config.logging.format,
    )


async def initialize(config: Config) -> None:
    """Initialize all modules."""
    global db, connection_manager, jwt_manager, message_router
    global user_repo, elo_repo, room_repo, game_repo, model_repo
    global auth_service, user_service, room_manager, match_service, admin_service
    global auth_handler, user_handler, room_handler, match_handler, admin_handler

    # 1. Database
    db = Database(config.database)
    await db.connect()
    logger.info("Database connected")

    # 2. Connection Manager
    connection_manager = ConnectionManager()

    # 3. JWT Manager
    jwt_manager = JWTManager(
        secret=config.jwt.secret,
        expire_hours=config.jwt.expire_hours,
        refresh_expire_hours=config.jwt.refresh_expire_hours,
        algorithm=config.jwt.algorithm,
    )

    # 4. Repositories
    user_repo = UserRepository(db.pool)
    elo_repo = EloRepository(db.pool)
    room_repo = RoomRepository(db.pool)
    game_repo = GameRepository(db.pool)
    model_repo = ModelRepository(db.pool)

    # 5. Services
    auth_service = AuthService(user_repo, elo_repo)
    user_service = UserService(user_repo, elo_repo)
    room_manager = RoomManager(room_repo, game_repo, elo_repo, user_service)
    match_service = MatchService(room_manager, connection_manager, user_service, config.match)
    admin_service = AdminService(
        user_repo, room_repo, game_repo, model_repo,
        online_count_func=connection_manager.online_count,
    )

    # 6. Handlers
    auth_handler = AuthHandler(auth_service, user_service, jwt_manager, connection_manager)
    user_handler = UserHandler(user_service)
    room_handler = RoomHandler(room_manager)
    match_handler = MatchHandler(match_service, room_manager, user_service)
    admin_handler = AdminHandler(admin_service, room_manager)

    # 7. Message Router
    message_router = MessageRouter()
    message_router.register_handler("auth", auth_handler)
    message_router.register_handler("user", user_handler)
    message_router.register_handler("room", room_handler)
    message_router.register_handler("game", room_handler)  # game_* goes to room_handler
    message_router.register_handler("match", match_handler)
    message_router.register_handler("admin", admin_handler)
    # reconnect goes to auth handler
    message_router.register_handler("reconnect", auth_handler)

    logger.info("All modules initialized")


async def cleanup() -> None:
    """Cleanup all resources."""
    global match_service, db

    if match_service:
        await match_service.stop()

    if db:
        await db.close()

    logger.info("All resources cleaned up")


# ---- FastAPI App ----

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    global config
    config = load_config()
    setup_logging(config)
    logger.info("Game Service v2.0 starting up...")
    await initialize(config)

    # Start match service
    await match_service.start()

    # Start heartbeat checker
    heartbeat_task = asyncio.create_task(heartbeat_checker())

    yield

    # Shutdown
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    await cleanup()
    logger.info("Game Service v2.0 shut down")


app = FastAPI(
    title="Xiangqi Game Service",
    version="2.0.0",
    lifespan=lifespan,
)


# ---- WebSocket Endpoint ----

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Main WebSocket endpoint - the only entry point for all client communication."""
    conn_id = str(uuid.uuid4())[:8]
    conn = ClientConnection(ws, conn_id)

    try:
        await ws.accept()
        connection_manager.register(conn)
        logger.info(f"WebSocket connected: {conn_id}")

        # First message must be authentication (within 30 seconds)
        try:
            auth_data = await asyncio.wait_for(ws.receive_text(), timeout=30)
            auth_msg = json.loads(auth_data)

            if auth_msg.get("type") not in ("auth_login", "auth_register", "auth_token", "reconnect"):
                await ws.send_json({
                    "type": "error",
                    "data": {"code": 1004, "message": "Authentication required"},
                })
                await ws.close()
                connection_manager.unregister(conn)
                return

            # Route the auth message
            await message_router.route(conn, auth_msg)

            if not conn.is_authenticated:
                # Auth failed, close connection
                await ws.close()
                connection_manager.unregister(conn)
                return

        except asyncio.TimeoutError:
            await ws.send_json({
                "type": "error",
                "data": {"code": 1004, "message": "Authentication timeout"},
            })
            await ws.close()
            connection_manager.unregister(conn)
            return

        # Main message loop
        while True:
            try:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                conn.last_ping = time.time()

                await message_router.route(conn, msg)

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {conn_id} (user={conn.user_id})")
                break
            except json.JSONDecodeError:
                await conn.send({
                    "type": "error",
                    "data": {"code": 1000, "message": "Invalid JSON"},
                })
            except Exception as e:
                logger.error(f"Message handling error: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Handle disconnection
        await handle_disconnect(conn)
        connection_manager.unregister(conn)
        logger.info(f"WebSocket closed: {conn_id}")


async def handle_disconnect(conn: ClientConnection) -> None:
    """Handle a player disconnection."""
    if not conn.user_id:
        return

    room = room_manager.get_user_room(conn.user_id)
    if room and room.phase == RoomPhase.PLAYING:
        # Player is in a game - keep room alive for reconnection
        player = room.get_player(room.get_player_side(conn.user_id) or "")
        if player:
            player.disconnect()
        logger.info(f"Player {conn.user_id} disconnected from room {room.room_id}")
    elif room and room.phase == RoomPhase.WAITING:
        # Player is in a waiting room - leave
        # Room handler will handle cleanup
        pass


# ---- HTTP Endpoints ----

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "online_users": connection_manager.online_count if connection_manager else 0,
        "active_rooms": len(room_manager.rooms) if room_manager else 0,
    }


@app.post("/internal/model/reload")
async def model_reload(request: Request):
    """Internal endpoint for model hot-reload notification.

    Called by the training service when a new model is ready.
    Requires internal secret for authentication.
    """
    body = await request.json()

    # Verify internal secret
    internal_secret = request.headers.get("X-Internal-Secret", "")
    if internal_secret != config.internal.secret:
        return Response(
            content=json.dumps({"error": "Unauthorized"}),
            status_code=401,
            media_type="application/json",
        )

    model_path = body.get("model_path", "")
    version = body.get("version", "")
    elo_score = body.get("elo_score", 0)

    logger.info(f"Model reload request: version={version}, path={model_path}, elo={elo_score}")

    # TODO: Implement model hot-reload when neural network AI is ready (Phase 2)
    # For now, just log the notification

    return {"status": "accepted", "version": version}


# ---- Background Tasks ----

async def heartbeat_checker():
    """Background task to check heartbeat and clean up stale connections."""
    while True:
        try:
            await asyncio.sleep(config.game.heartbeat_interval)
            now = time.time()
            timeout = config.game.heartbeat_timeout

            stale_connections = []
            for conn_id, conn in list(connection_manager._connections.items()):
                if now - conn.last_ping > timeout:
                    stale_connections.append(conn)

            for conn in stale_connections:
                logger.info(f"Heartbeat timeout: {conn.conn_id} (user={conn.user_id})")
                try:
                    await conn.kick("Heartbeat timeout")
                except Exception:
                    pass
                connection_manager.unregister(conn)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Heartbeat checker error: {e}", exc_info=True)


# ---- Entry Point ----

def main():
    """Start the Game Service."""
    import uvicorn

    config = load_config()
    setup_logging(config)

    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        workers=config.server.workers,
        reload=False,
        log_level=config.logging.level.lower(),
    )


if __name__ == "__main__":
    main()
