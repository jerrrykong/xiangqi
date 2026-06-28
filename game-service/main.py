"""Game Service v2.0 - Main Entry Point

Integrates all modules and starts the FastAPI application with WebSocket support.
"""

import sys
import os
import json
import asyncio
import logging
import logging.handlers
import time
import uuid
from contextlib import asynccontextmanager

# Load .env before any config (project root takes priority)
from dotenv import load_dotenv
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_dotenv_path = os.path.join(_project_root, ".env")
if os.path.exists(_dotenv_path):
    load_dotenv(_dotenv_path)
    # Avoid leaking vars into module scope
    del _project_root, _dotenv_path

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
from room.room import RoomPhase
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
    """Configure logging with console and rotating file handlers."""
    log_cfg = config.logging
    log_level = getattr(logging, log_cfg.level, logging.INFO)
    formatter = logging.Formatter(log_cfg.format)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # 清除已有 handler（避免 uvicorn 或重复调用导致重复日志）
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler - TimedRotatingFileHandler (按日期滚动)
    log_dir = os.path.abspath(log_cfg.log_dir)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_cfg.filename)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path,
        when=log_cfg.when,
        interval=log_cfg.interval,
        backupCount=log_cfg.backup_count,
        encoding=log_cfg.encoding,
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler.suffix = "%Y-%m-%d"  # 滚动文件后缀格式
    root_logger.addHandler(file_handler)

    # 让 uvicorn 的日志也走 root logger（写入文件）
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.setLevel(log_level)
        uv_logger.handlers.clear()  # 移除 uvicorn 默认的 console handler
        uv_logger.propagate = True  # 传播到 root logger


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
    room_manager = RoomManager(room_repo, game_repo, elo_repo, user_service,
                                disconnect_timeout=config.game.disconnect_timeout)
    match_service = MatchService(room_manager, connection_manager, user_service, config.match)

    # Set room_manager reference on connection_manager for reconnect state_sync
    connection_manager._room_manager_ref = room_manager
    admin_service = AdminService(
        user_repo, room_repo, game_repo, model_repo,
        online_count_func=connection_manager.online_count,
    )

    # 6. Handlers
    auth_handler = AuthHandler(auth_service, user_service, jwt_manager, connection_manager)
    user_handler = UserHandler(user_service)
    room_handler = RoomHandler(room_manager, connection_manager)
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
    logger.info("\n\n===============================================")    
    logger.info("Game Service v2.0 starting up...")
    logger.info("===============================================")    
    await initialize(config)

    # Start match service
    await match_service.start()

    # Restore active rooms from DB
    restored = await room_manager.restore_active_rooms()
    if restored > 0:
        logger.info(f"Restored {restored} active rooms from DB")

    # Start disconnect timeout checker
    room_manager.start_disconnect_checker()

    # Start heartbeat checker
    heartbeat_task = asyncio.create_task(heartbeat_checker())

    yield

    # Shutdown sequence (ordered to avoid DB pool closed while workers still write)
    logger.info("Shutdown initiated")

    # 1) Prevent room manager from performing DB writes
    room_manager.shutting_down = True

    # 2) Stop match service to avoid creating new rooms
    logger.info("Stopping match service...")
    try:
        await asyncio.wait_for(match_service.stop(), timeout=5.0)
        logger.info("Match service stopped")
    except asyncio.TimeoutError:
        logger.warning("Timeout while stopping match service")
    except Exception:
        logger.exception("Error stopping match service")

    # 3) Stop periodic background checkers (disconnect checker)
    logger.info("Stopping disconnect checker...")
    room_manager.stop_disconnect_checker()

    # 4) Cancel and wait for all room runners to finish
    logger.info("Stopping all room runners...")
    try:
        await asyncio.wait_for(room_manager.stop_all_rooms(), timeout=5.0)
        logger.info("All room runners stopped")
    except asyncio.TimeoutError:
        logger.warning("Timeout while waiting for room runners to stop")
    except Exception as e:
        logger.warning(f"Error while stopping room runners: {e}")

    # 5) Close all client connections (this may trigger handle_disconnect / leave_room while DB is still open)
    logger.info("Closing all client connections...")
    try:
        await asyncio.wait_for(connection_manager.close_all("server_shutdown"), timeout=5.0)
        logger.info("All client connections closed")
    except asyncio.TimeoutError:
        logger.warning("Timeout while closing client connections")
    except Exception:
        logger.exception("Error closing client connections")

    # Give small grace period for disconnect handlers to finish
    try:
        await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass

    # 6) Stop heartbeat and other background tasks
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass

    # 7) Now safe to cleanup / close DB
    logger.info("Cleaning up resources (DB close etc.)...")
    await cleanup()
    logger.info("Cleanup complete")
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
        logger.info(f"WebSocket connected: {conn_id} (total={connection_manager.total_connections})")

        # === 认证阶段: 必须在 30 秒内认证成功 ===
        AUTH_MSG_TYPES = {"auth_login", "auth_register", "auth_token", "reconnect"}
        auth_deadline = time.time() + 30

        while not conn.is_authenticated:
            remaining = auth_deadline - time.time()
            if remaining <= 0:
                await conn.send({
                    "type": "error",
                    "seq": 0,
                    "data": {"code": 1004, "message": "Authentication timeout"},
                })
                await ws.close()
                connection_manager.unregister(conn)
                return

            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=remaining)
                msg = json.loads(raw)
                conn.last_ping = time.time()
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected during auth: {conn_id}")
                return
            except asyncio.TimeoutError:
                await conn.send({
                    "type": "error",
                    "seq": 0,
                    "data": {"code": 1004, "message": "Authentication timeout"},
                })
                await ws.close()
                connection_manager.unregister(conn)
                return

            msg_type = msg.get("type", "")
            if msg_type not in AUTH_MSG_TYPES:
                logger.warning(f"Non-auth message '{msg_type}' during auth phase from conn={conn_id}")
                await conn.send({
                    "type": "error",
                    "seq": msg.get("seq", 0),
                    "data": {"code": 1004, "message": "Authentication required"},
                })
                continue  # 不关闭，允许重试

            # 路由认证消息
            try:
                await message_router.route(conn, msg)
            except Exception as e:
                logger.error(f"Auth handler error: {e}", exc_info=True)
                await conn.send({
                    "type": "error",
                    "seq": msg.get("seq", 0),
                    "data": {"code": 1000, "message": "Internal server error"},
                })

            # is_authenticated 已在 handler 中更新

        # === 认证成功，进入主消息循环 ===
        logger.info(f"User {conn.username}(id={conn.user_id}) authenticated, conn={conn_id}")
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
            except RuntimeError as e:
                # WS 已断开（未 accept 或已关闭），退出循环
                logger.info(f"WebSocket closed externally: {conn_id} ({e})")
                break
            except Exception as e:
                logger.error(f"Message handling error: {e}", exc_info=True)
                # 检查 WS 是否仍可用，不可用则退出避免死循环
                try:
                    await ws.send_text("")  # 探测 WS 是否仍连接
                except Exception:
                    logger.info(f"WebSocket no longer usable: {conn_id}")
                    break

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Handle disconnection
        await handle_disconnect(conn)
        connection_manager.unregister(conn)
        logger.info(f"WebSocket closed: {conn_id} user={conn.user_id} (online={connection_manager.online_count})")


async def handle_disconnect(conn: ClientConnection) -> None:
    """Handle a player disconnection."""
    if not conn.user_id:
        return

    room = room_manager.get_user_room(conn.user_id)
    if not room:
        return

    player = room.get_player(room.get_player_side(conn.user_id) or "")
    if player:
        player.disconnect()
        logger.info(f"Player {conn.user_id} disconnected from room {room.room_id} (phase={room.phase.name})")

        # Notify the opponent about status change
        opponent = room.get_opponent(conn.user_id)
        if opponent and opponent.is_connected:
            await opponent.send({
                "type": "opponent_status_change",
                "data": {"user_id": conn.user_id, "online": False},
            })


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


# ---- Debug Endpoints (仅 GS_DEBUG_ENABLE=1 时可用) ----

def _is_debug_enabled() -> bool:
    """Check if debug mode is enabled via environment variable."""
    return os.environ.get("GS_DEBUG_ENABLE", "0") == "1"


@app.post("/api/debug/trigger")
async def debug_trigger(request: Request):
    """Trigger debug scenarios for testing error handling.

    Requires GS_DEBUG_ENABLE=1 environment variable.

    Actions:
      - force_timeout: { room_id, side }  立即触发走棋超时
      - force_disconnect: { user_id }      模拟玩家断线
      - crash_save: { enable: true/false } 切换 DB 保存异常模拟
      - list_rooms: {}                     列出所有活跃房间
    """
    if not _is_debug_enabled():
        return Response(
            content=json.dumps({"error": "Debug mode not enabled. Set GS_DEBUG_ENABLE=1"}),
            status_code=403,
            media_type="application/json",
        )

    try:
        body = await request.json()
    except Exception:
        return Response(
            content=json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            media_type="application/json",
        )

    action = body.get("action", "")
    logger.warning(f"[DEBUG] Trigger action: {action}, body={body}")

    # ---- list_rooms ----
    if action == "list_rooms":
        rooms_info = []
        for room_id, room in room_manager.rooms.items():
            rooms_info.append({
                "room_id": room_id,
                "phase": room.phase.name if room.phase else "unknown",
                "room_type": room.room_type.name if room.room_type else "unknown",
                "red_user_id": room.red_player.user_id if room.red_player else None,
                "black_user_id": room.black_player.user_id if room.black_player else None,
                "red_connected": room.red_player.is_connected if room.red_player else False,
                "black_connected": room.black_player.is_connected if room.black_player else False,
                "current_side": room.game_state.current_player.name if room.game_state else None,
                "red_remaining": room.timer.red_remaining if room.timer else 0,
                "black_remaining": room.timer.black_remaining if room.timer else 0,
                "game_count": room.game_count,
            })
        return {"rooms": rooms_info, "total": len(rooms_info)}

    # ---- crash_save ----
    if action == "crash_save":
        enable = body.get("enable", False)
        room_manager._debug_crash_on_save = enable
        logger.warning(f"[DEBUG] crash_save set to: {enable}")
        return {"status": "ok", "crash_save_enabled": enable}

    # ---- force_timeout ----
    if action == "force_timeout":
        room_id = body.get("room_id", "")
        side = body.get("side", "red")  # "red" or "black"

        if not room_id:
            return Response(
                content=json.dumps({"error": "Missing room_id"}),
                status_code=400,
                media_type="application/json",
            )

        room = room_manager.get_room(room_id)
        if not room:
            return Response(
                content=json.dumps({"error": f"Room {room_id} not found"}),
                status_code=404,
                media_type="application/json",
            )

        if side not in ("red", "black"):
            return Response(
                content=json.dumps({"error": f"Invalid side: {side}, must be 'red' or 'black'"}),
                status_code=400,
                media_type="application/json",
            )

        logger.warning(f"[DEBUG] Forcing timeout: room={room_id}, side={side}")
        await room_manager._handle_timeout(room, side)
        return {"status": "ok", "action": "force_timeout", "room_id": room_id, "side": side}

    # ---- force_disconnect ----
    if action == "force_disconnect":
        user_id = body.get("user_id")
        if not user_id:
            return Response(
                content=json.dumps({"error": "Missing user_id"}),
                status_code=400,
                media_type="application/json",
            )

        room = room_manager.get_user_room(user_id)
        if not room:
            return Response(
                content=json.dumps({"error": f"No active room for user {user_id}"}),
                status_code=404,
                media_type="application/json",
            )

        # Find the user's connection and simulate disconnect
        player = room.get_player(room.get_player_side(user_id) or "")
        if player and player.is_connected:
            player.disconnect()
            logger.warning(f"[DEBUG] Forced disconnect: user={user_id}, room={room.room_id}")

            # Notify opponent about disconnect
            opponent = room.get_opponent(user_id)
            if opponent and opponent.is_connected:
                await opponent.send({
                    "type": "opponent_status_change",
                    "data": {"user_id": user_id, "online": False},
                })

            return {"status": "ok", "action": "force_disconnect", "user_id": user_id,
                    "room_id": room.room_id}
        else:
            return {"status": "skipped", "reason": "Player not connected",
                    "user_id": user_id}

    return Response(
        content=json.dumps({"error": f"Unknown action: {action}"}),
        status_code=400,
        media_type="application/json",
    )


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

    log_level = getattr(logging, config.logging.level, logging.INFO)

    # 禁用 uvicorn 默认日志配置，使用我们自己的 root logger
    # uvicorn 的 log_config=None 会跳过默认配置，日志由 root logger 统一处理
    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        workers=config.server.workers,
        reload=False,
        log_level=log_level,
        log_config=None,
        timeout_graceful_shutdown=30
    )


if __name__ == "__main__":
    main()
