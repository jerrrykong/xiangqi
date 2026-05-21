# Game 服务详细设计（Python — 统一服务）

> 服务职责：用户认证、房间管理、ELO 匹配、实时对局、棋盘规则、AI 推理、管理后台
> 技术栈：Python 3.11+ / FastAPI / asyncio / asyncpg / PyTorch
> 文档版本：v2.0
> 架构变更：合并原 Web 服务（Go）+ Game 服务（Python）为统一 Python 服务

---

## 一、项目结构

```
game-service/
├── main.py                     # 程序入口（FastAPI + WebSocket）
├── config.py                   # 配置加载（YAML / 环境变量）
│
├── gateway/                    # WebSocket 网关层
│   ├── __init__.py
│   ├── connection_manager.py   # 连接管理器（生命周期 / 心跳 / 断线重连）
│   ├── message_router.py       # 消息路由（按 type 分发到对应 Handler）
│   └── connection_state.py     # 连接状态机定义
│
├── auth/                       # 认证模块
│   ├── __init__.py
│   ├── auth_handler.py         # WebSocket 认证消息处理
│   ├── auth_service.py         # 认证业务逻辑（登录/注册/Token）
│   └── jwt_manager.py          # JWT 生成 / 解析 / 刷新
│
├── user/                       # 用户模块
│   ├── __init__.py
│   ├── user_handler.py         # WebSocket 用户消息处理
│   ├── user_service.py         # 用户业务逻辑
│   └── user_repository.py      # 用户数据访问（asyncpg）
│
├── room/                       # 房间模块（统一房间 + 游戏）
│   ├── __init__.py
│   ├── room_handler.py         # WebSocket 房间/游戏消息处理
│   ├── room_service.py         # 房间业务逻辑
│   ├── room_manager.py         # 内存房间管理器（活跃房间池）
│   ├── room.py                 # 房间对象（含完整游戏状态和流程）
│   ├── player_session.py       # 玩家连接会话
│   └── timers.py               # 计时器管理（思考超时 / 回合超时）
│
├── match/                      # 匹配模块
│   ├── __init__.py
│   ├── match_handler.py        # WebSocket 匹配消息处理
│   ├── match_service.py        # ELO 匹配引擎（后台匹配循环）
│   └── match_queue.py          # 匹配队列（内存 SortedSet）
│
├── chess/                      # 棋盘引擎（复用 v1.0）
│   ├── __init__.py
│   ├── board.py                # 棋盘数据结构
│   ├── piece.py                # 棋子定义
│   ├── move.py                 # 着法数据结构
│   ├── move_generator.py       # 合法着法生成
│   ├── move_validator.py       # 着法验证
│   ├── win_checker.py          # 胜负判定
│   └── game_state.py           # 游戏状态机
│
├── ai/                         # AI 推理模块（复用 v1.0）
│   ├── __init__.py
│   ├── ai_proxy.py             # AI 推理调用封装
│   └── difficulty.py           # 难度控制器
│
├── admin/                      # 管理后台模块
│   ├── __init__.py
│   ├── admin_handler.py        # WebSocket 管理消息处理
│   └── admin_service.py        # 管理业务逻辑
│
├── protocol/                   # 协议定义
│   ├── __init__.py
│   ├── message.py              # 消息基类
│   ├── inbound.py              # 入站消息类型（客户端→服务端）
│   ├── outbound.py             # 出站消息类型（服务端→客户端）
│   └── serializer.py           # JSON 序列化/反序列化
│
├── db/                         # 数据库层
│   ├── __init__.py
│   ├── database.py             # asyncpg 连接池
│   └── migrations/             # SQL 迁移脚本
│
├── config.yaml                 # 配置文件
└── requirements.txt
```

---

## 二、WebSocket 连接管理

### 2.1 连接状态机

```python
# gateway/connection_state.py
from enum import IntEnum

class ConnectionState(IntEnum):
    UNAUTHENTICATED = 0   # 刚连接，未认证
    AUTHENTICATED   = 1   # 已认证，在大厅
    IN_ROOM         = 2   # 在房间中（对局中）
    MATCHMAKING     = 3   # 在匹配队列中

# 状态转换规则：
# UNAUTHENTICATED → AUTHENTICATED    auth_login/auth_register/auth_token 成功
# AUTHENTICATED → IN_ROOM            room_create/room_join/match_found
# AUTHENTICATED → MATCHMAKING        match_join
# IN_ROOM → AUTHENTICATED            game_over/room_leave
# MATCHMAKING → AUTHENTICATED        match_leave/match_timeout
# MATCHMAKING → IN_ROOM              match_found
# 任意 → UNAUTHENTICATED             auth_logout/连接断开
```

### 2.2 连接管理器

```python
# gateway/connection_manager.py
import asyncio
from typing import Dict, Optional
from fastapi import WebSocket

class ConnectionManager:
    """
    管理所有 WebSocket 连接
    """
    def __init__(self):
        self.connections: Dict[int, 'ClientConnection'] = {}  # user_id → ClientConnection
        self.lock = asyncio.Lock()

    async def register(self, user_id: int, conn: 'ClientConnection'):
        async with self.lock:
            # 如果已有连接，踢掉旧连接
            if user_id in self.connections:
                old_conn = self.connections[user_id]
                await old_conn.kick("duplicate_login")
            self.connections[user_id] = conn

    async def unregister(self, user_id: int):
        async with self.lock:
            self.connections.pop(user_id, None)

    def get(self, user_id: int) -> Optional['ClientConnection']:
        return self.connections.get(user_id)

    @property
    def online_count(self) -> int:
        return len(self.connections)


class ClientConnection:
    """
    单个客户端的 WebSocket 连接
    """
    def __init__(self, ws: WebSocket, user_id: int, username: str):
        self.ws = ws
        self.user_id = user_id
        self.username = username
        self.state = ConnectionState.UNAUTHENTICATED
        self.room_id: Optional[str] = None     # 当前所在房间 ID
        self.session_token: str = ""            # 断线重连用
        self.last_ping: float = 0.0             # 上次心跳时间

    async def send(self, msg: dict):
        """发送消息"""
        try:
            await self.ws.send_json(msg)
        except Exception:
            pass  # 连接已断开

    async def kick(self, reason: str):
        """踢出连接"""
        await self.send({"type": "kicked", "data": {"reason": reason}})
        await self.ws.close()
```

### 2.3 消息路由器

```python
# gateway/message_router.py
from auth.auth_handler import AuthHandler
from user.user_handler import UserHandler
from room.room_handler import RoomHandler
from match.match_handler import MatchHandler
from admin.admin_handler import AdminHandler

class MessageRouter:
    """
    WebSocket 消息路由 — 根据 type 前缀分发到对应 Handler
    """
    def __init__(self, auth_handler, user_handler, room_handler,
                 match_handler, admin_handler):
        self.auth_handler = auth_handler
        self.user_handler = user_handler
        self.room_handler = room_handler
        self.match_handler = match_handler
        self.admin_handler = admin_handler

    # 消息 type → handler 映射
    ROUTE_MAP = {
        # 认证（UNAUTHENTICATED 状态可用）
        "auth_login":      "auth_handler",
        "auth_register":   "auth_handler",
        "auth_token":      "auth_handler",
        "auth_refresh":    "auth_handler",

        # 用户（AUTHENTICATED 状态可用）
        "user_get_me":       "user_handler",
        "user_update_profile": "user_handler",
        "user_get_rankings": "user_handler",
        "user_get_history":  "user_handler",

        # 房间（AUTHENTICATED / IN_ROOM 状态）
        "room_create":    "room_handler",
        "room_list":      "room_handler",
        "room_join":      "room_handler",
        "room_leave":     "room_handler",

        # 游戏（IN_ROOM 状态）
        "game_move":      "room_handler",
        "game_resign":    "room_handler",
        "game_draw_req":  "room_handler",
        "game_draw_ans":  "room_handler",

        # 匹配（AUTHENTICATED 状态）
        "match_join":     "match_handler",
        "match_leave":    "match_handler",

        # 管理后台（AUTHENTICATED + is_admin 状态）
        "admin_users":    "admin_handler",
        "admin_ban":      "admin_handler",
        "admin_stats":    "admin_handler",
        "admin_models":   "admin_handler",

        # 通用
        "ping":           None,  # 直接回复 pong
        "reconnect":      "auth_handler",
    }

    async def route(self, conn: 'ClientConnection', msg: dict):
        """路由消息到对应 handler"""
        msg_type = msg.get("type", "")
        handler_name = self.ROUTE_MAP.get(msg_type)

        if handler_name is None and msg_type == "ping":
            await conn.send({"type": "pong", "data": {}})
            return

        if handler_name is None:
            await conn.send({"type": "error", "data": {"code": 1003, "message": "unknown message type"}})
            return

        handler = getattr(self, handler_name)
        await handler.handle(conn, msg)
```

---

## 三、认证模块（WebSocket 认证）

### 3.1 AuthHandler

```python
# auth/auth_handler.py
class AuthHandler:
    """处理所有认证相关的 WebSocket 消息"""

    async def handle(self, conn: 'ClientConnection', msg: dict):
        handlers = {
            "auth_login":    self._handle_login,
            "auth_register": self._handle_register,
            "auth_token":    self._handle_token_auth,
            "auth_refresh":  self._handle_refresh,
            "reconnect":     self._handle_reconnect,
        }
        handler = handlers.get(msg["type"])
        if handler:
            await handler(conn, msg)

    async def _handle_login(self, conn, msg):
        """登录"""
        data = msg["data"]
        username = data.get("username", "")
        password = data.get("password", "")

        user = await self.auth_service.login(username, password)
        if not user:
            await conn.send({
                "type": "auth_result",
                "data": {"success": False, "error": "invalid_credentials"}
            })
            return

        # 生成 JWT + session_token
        token, expires_at = self.jwt_manager.create_token(user.id, user.username, user.is_admin)
        session_token = str(uuid.uuid4())

        # 注册连接
        conn.user_id = user.id
        conn.username = user.username
        conn.session_token = session_token
        conn.state = ConnectionState.AUTHENTICATED
        await self.connection_manager.register(user.id, conn)

        await conn.send({
            "type": "auth_result",
            "data": {
                "success": True,
                "user_id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "rating": user.rating,
                "games_count": user.games_count,
                "token": token,
                "expires_at": expires_at,
                "session_token": session_token,
            }
        })

    async def _handle_register(self, conn, msg):
        """注册"""
        data = msg["data"]
        user = await self.auth_service.register(
            username=data["username"],
            password=data["password"],
            nickname=data.get("nickname", data["username"]),
        )
        if not user:
            await conn.send({
                "type": "auth_result",
                "data": {"success": False, "error": "username_exists"}
            })
            return

        # 注册成功后自动登录
        token, expires_at = self.jwt_manager.create_token(user.id, user.username, False)
        session_token = str(uuid.uuid4())

        conn.user_id = user.id
        conn.username = user.username
        conn.session_token = session_token
        conn.state = ConnectionState.AUTHENTICATED
        await self.connection_manager.register(user.id, conn)

        await conn.send({
            "type": "auth_result",
            "data": {
                "success": True,
                "user_id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "rating": 1500,
                "games_count": 0,
                "token": token,
                "expires_at": expires_at,
                "session_token": session_token,
            }
        })

    async def _handle_token_auth(self, conn, msg):
        """使用已有 JWT Token 认证"""
        token = msg["data"].get("token", "")
        claims = self.jwt_manager.parse_token(token)

        if not claims:
            await conn.send({
                "type": "auth_result",
                "data": {"success": False, "error": "token_invalid"}
            })
            return

        user = await self.user_service.get_user(claims.user_id)
        if not user or user.is_banned:
            await conn.send({
                "type": "auth_result",
                "data": {"success": False, "error": "user_banned"}
            })
            return

        session_token = str(uuid.uuid4())
        conn.user_id = user.id
        conn.username = user.username
        conn.session_token = session_token
        conn.state = ConnectionState.AUTHENTICATED
        await self.connection_manager.register(user.id, conn)

        await conn.send({
            "type": "auth_result",
            "data": {
                "success": True,
                "user_id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "rating": user.rating,
                "games_count": user.games_count,
                "session_token": session_token,
            }
        })

    async def _handle_reconnect(self, conn, msg):
        """断线重连"""
        session_token = msg["data"].get("session_token", "")
        room_id = msg["data"].get("room_id", "")

        # 验证 session_token
        # ... 找到原始连接，恢复状态
        # 推送完整游戏状态
```

### 3.2 AuthService

```python
# auth/auth_service.py
import bcrypt

class AuthService:
    def __init__(self, user_repository):
        self.user_repo = user_repository

    async def login(self, username: str, password: str):
        """登录验证"""
        user = await self.user_repo.get_by_username(username)
        if not user:
            return None
        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return None
        if user.is_banned:
            return None
        # 更新 last_login_at
        await self.user_repo.update_last_login(user.id)
        return user

    async def register(self, username: str, password: str, nickname: str):
        """注册"""
        # 验证用户名唯一
        if await self.user_repo.get_by_username(username):
            return None
        # 密码强度验证
        if len(password) < 8 or not any(c.isdigit() for c in password) or not any(c.isalpha() for c in password):
            return None
        # 创建用户
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = await self.user_repo.create(username, password_hash, nickname)
        # 创建 ELO 积分记录
        await self.user_repo.create_elo_rating(user.id)
        return user
```

---

## 四、用户模块

### 4.1 UserHandler

```python
# user/user_handler.py
class UserHandler:
    async def handle(self, conn, msg):
        handlers = {
            "user_get_me":         self._get_me,
            "user_update_profile": self._update_profile,
            "user_get_rankings":   self._get_rankings,
            "user_get_history":    self._get_history,
        }
        handler = handlers.get(msg["type"])
        if handler:
            await handler(conn, msg)

    async def _get_me(self, conn, msg):
        user = await self.user_service.get_user(conn.user_id)
        await conn.send({
            "type": "user_me",
            "data": {
                "user_id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "rating": user.rating,
                "games_count": user.games_count,
                "created_at": user.created_at.isoformat(),
            }
        })

    async def _get_rankings(self, conn, msg):
        data = msg["data"]
        page = data.get("page", 1)
        page_size = data.get("page_size", 20)
        result = await self.user_service.get_rankings(page, page_size)
        await conn.send({"type": "user_rankings", "data": result})

    async def _get_history(self, conn, msg):
        data = msg["data"]
        page = data.get("page", 1)
        page_size = data.get("page_size", 20)
        game_type = data.get("type", "")
        result = await self.user_service.get_history(conn.user_id, page, page_size, game_type)
        await conn.send({"type": "user_history", "data": result})

    async def _update_profile(self, conn, msg):
        data = msg["data"]
        await self.user_service.update_profile(conn.user_id, data)
        await conn.send({"type": "user_profile_updated", "data": {"success": True}})
```

### 4.2 UserService

```python
# user/user_service.py
class UserService:
    def __init__(self, user_repo, elo_repo):
        self.user_repo = user_repo
        self.elo_repo = elo_repo

    async def get_user(self, user_id: int):
        return await self.user_repo.get_by_id(user_id)

    async def update_profile(self, user_id: int, data: dict):
        await self.user_repo.update(user_id, nickname=data.get("nickname"), avatar=data.get("avatar"))

    async def get_rankings(self, page: int, page_size: int):
        return await self.elo_repo.get_rankings(page, page_size)

    async def get_history(self, user_id: int, page: int, page_size: int, game_type: str):
        return await self.user_repo.get_game_history(user_id, page, page_size, game_type)

    async def calculate_elo(self, rating_a: int, rating_b: int, result: float, games_a: int) -> tuple[int, int]:
        """ELO 积分计算"""
        K = 40
        if games_a > 100:
            K = 10
        elif games_a > 30:
            K = 20
        EA = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))
        change_a = int(K * (result - EA))
        change_b = -change_a
        return change_a, change_b
```

---

## 五、房间模块（统一房间 + 游戏）

### 5.1 核心设计

**房间是游戏的唯一载体**。从创建到结束的完整生命周期都在 Room 对象内管理。

```
房间生命周期：

手动 PvP：
  create_room → WAITING → 对手 join → PLAYING → 游戏结束 → FINISHED

匹配 PvP：
  match_found → 直接 PLAYING → 游戏结束 → FINISHED
  （无 WAITING 阶段，跳过准备）

人机 PvE：
  create_pve_room → 直接 PLAYING → 游戏结束 → FINISHED
  （无 WAITING 阶段，AI 即时就位）
```

### 5.2 Room 数据类

```python
# room/room.py
import asyncio
from dataclasses import dataclass, field
from enum import IntEnum
from chess.game_state import GameState, GameResult
from chess.piece import Color
from room.player_session import PlayerSession

class RoomSource(IntEnum):
    MANUAL = 1    # 手动创建
    MATCH  = 2    # 匹配创建

class RoomPhase(IntEnum):
    WAITING   = 1  # 等待对手加入（仅手动 PvP）
    PLAYING   = 2  # 对局中
    FINISHED  = 3  # 已结束

class RoomType(IntEnum):
    PVP = 1       # 人人对战
    PVE = 2       # 人机对战


@dataclass
class Room:
    room_id: str
    room_type: RoomType
    source: RoomSource = RoomSource.MANUAL
    phase: RoomPhase = RoomPhase.WAITING
    difficulty: int | None = None   # PvE 难度 1~5

    # 玩家
    red_player: PlayerSession | None = None
    black_player: PlayerSession | None = None

    # 游戏状态（双方就位后初始化）
    game_state: GameState | None = None

    # 计时
    move_timer: asyncio.Task | None = None
    move_timeout_seconds: int = 60
    started_at: float = 0.0

    # AI 专用
    ai_side: Color | None = None

    # 回调
    on_game_over: callable | None = None

    # 异步事件
    move_event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def is_full(self) -> bool:
        return self.red_player is not None and self.black_player is not None

    def get_player(self, side: str) -> PlayerSession | None:
        return self.red_player if side == "red" else self.black_player

    def get_opponent(self, user_id: int) -> PlayerSession | None:
        if self.red_player and self.red_player.user_id == user_id:
            return self.black_player
        if self.black_player and self.black_player.user_id == user_id:
            return self.red_player
        return None

    def get_player_side(self, user_id: int) -> str | None:
        if self.red_player and self.red_player.user_id == user_id:
            return "red"
        if self.black_player and self.black_player.user_id == user_id:
            return "black"
        return None
```

### 5.3 RoomManager

```python
# room/room_manager.py
import asyncio
import logging
from typing import Dict
from room.room import Room, RoomPhase, RoomType, RoomSource
from room.player_session import PlayerSession
from chess.game_state import GameState, GameResult
from chess.board import Board
from chess.piece import Color
from chess.move_validator import MoveValidator
from chess.win_checker import WinChecker
from ai.ai_proxy import AIProxy

logger = logging.getLogger(__name__)


class RoomManager:
    """
    房间管理器 — 管理所有活跃房间
    """

    def __init__(self, db_pool, elo_service):
        self.rooms: Dict[str, Room] = {}          # room_id → Room
        self.user_rooms: Dict[int, str] = {}      # user_id → room_id
        self.tasks: Dict[str, asyncio.Task] = {}   # room_id → asyncio.Task
        self.ai_proxy = AIProxy()
        self.db_pool = db_pool
        self.elo_service = elo_service

    # ---- 房间创建 ----

    async def create_manual_room(self, room_id: str, creator: PlayerSession) -> Room:
        """手动创建 PvP 房间"""
        room = Room(
            room_id=room_id,
            room_type=RoomType.PVP,
            source=RoomSource.MANUAL,
            phase=RoomPhase.WAITING,
        )
        room.red_player = creator
        self.rooms[room_id] = room
        self.user_rooms[creator.user_id] = room_id
        return room

    async def create_match_room(self, room_id: str,
                                 red: PlayerSession, black: PlayerSession) -> Room:
        """匹配创建 PvP 房间 — 直接进入 PLAYING"""
        room = Room(
            room_id=room_id,
            room_type=RoomType.PVP,
            source=RoomSource.MATCH,
            phase=RoomPhase.PLAYING,
        )
        room.red_player = red
        room.black_player = black
        room.game_state = GameState(room_id=room_id, board=Board())
        room.game_state.started_at = asyncio.get_event_loop().time()

        self.rooms[room_id] = room
        self.user_rooms[red.user_id] = room_id
        self.user_rooms[black.user_id] = room_id

        # 启动房间协程
        task = asyncio.create_task(self._run_room(room))
        self.tasks[room_id] = task

        return room

    async def create_pve_room(self, room_id: str,
                               player: PlayerSession, player_side: str,
                               difficulty: int) -> Room:
        """创建 PvE 房间 — 直接进入 PLAYING"""
        room = Room(
            room_id=room_id,
            room_type=RoomType.PVE,
            source=RoomSource.MANUAL,
            phase=RoomPhase.PLAYING,
            difficulty=difficulty,
        )

        if player_side == "red":
            room.red_player = player
            room.ai_side = Color.BLACK
        else:
            room.black_player = player
            room.ai_side = Color.RED

        room.game_state = GameState(room_id=room_id, board=Board())
        room.game_state.started_at = asyncio.get_event_loop().time()

        self.rooms[room_id] = room
        self.user_rooms[player.user_id] = room_id

        task = asyncio.create_task(self._run_room(room))
        self.tasks[room_id] = task

        return room

    # ---- 房间加入 ----

    async def join_room(self, room_id: str, player: PlayerSession) -> Room:
        """加入手动房间 — 加入后直接开始"""
        room = self.rooms.get(room_id)
        if not room:
            return None
        if room.phase != RoomPhase.WAITING:
            return None
        if room.is_full:
            return None

        room.black_player = player
        self.user_rooms[player.user_id] = room_id

        # 直接进入 PLAYING
        room.phase = RoomPhase.PLAYING
        room.game_state = GameState(room_id=room_id, board=Board())
        room.game_state.started_at = asyncio.get_event_loop().time()

        # 启动房间协程
        task = asyncio.create_task(self._run_room(room))
        self.tasks[room_id] = task

        return room

    # ---- 房间协程 ----

    async def _run_room(self, room: Room):
        """房间主协程 — 管理完整对局流程"""
        try:
            # 通知双方游戏开始
            await self._broadcast(room, {
                "type": "game_start",
                "data": {
                    "room_id": room.room_id,
                    "game_type": "pvp" if room.room_type == RoomType.PVP else "pve",
                }
            })
            # 分别通知各方执子
            if room.red_player:
                await room.red_player.send({"type": "game_start", "data": {"your_side": "red"}})
            if room.black_player:
                await room.black_player.send({"type": "game_start", "data": {"your_side": "black"}})

            while room.phase == RoomPhase.PLAYING and not room.game_state.is_over():
                current_color = room.game_state.current_turn
                current_side = "red" if current_color == Color.RED else "black"

                # AI 回合
                if room.room_type == RoomType.PVE and room.ai_side == current_color:
                    await self._do_ai_move(room)
                    continue

                # 玩家回合 — 等待操作
                room.move_event.clear()
                try:
                    await asyncio.wait_for(
                        room.move_event.wait(),
                        timeout=room.move_timeout_seconds
                    )
                except asyncio.TimeoutError:
                    await self._handle_timeout(room, current_side)
                    break

        except Exception as e:
            logger.exception(f"Room {room.room_id} error: {e}")
        finally:
            await self._cleanup_room(room)

    async def _do_ai_move(self, room: Room):
        """AI 落子"""
        # 通知玩家 AI 思考中
        player = room.red_player if room.ai_side == Color.BLACK else room.black_player
        if player:
            await player.send({"type": "ai_thinking", "data": {}})

        move = await self.ai_proxy.get_best_move(
            board=room.game_state.board,
            difficulty=room.difficulty,
        )
        await self._apply_and_broadcast_move(room, move, "ai_move")

    async def apply_player_move(self, room: Room, move, player_side: str):
        """玩家落子 — 由 RoomHandler 调用"""
        await self._apply_and_broadcast_move(room, move, "move_result")
        room.move_event.set()  # 通知房间协程继续

    async def _apply_and_broadcast_move(self, room: Room, move, msg_type: str):
        """执行着法并广播"""
        gs = room.game_state
        captured = gs.make_move(move)
        player_side = "red" if gs.move_no % 2 == 1 else "black"

        await self._broadcast(room, {
            "type": msg_type,
            "data": {
                "player": player_side,
                "from": move.from_pos,
                "to": move.to_pos,
                "captured": captured,
                "move_no": gs.move_no,
            }
        })

        # 胜负判定
        win_checker = WinChecker(gs.board)
        is_over, reason = win_checker.check_game_over(gs.current_turn)

        if is_over:
            if reason == "checkmate":
                gs.result = GameResult.RED_WINS if gs.current_turn == Color.BLACK else GameResult.BLACK_WINS
            elif reason == "stalemate":
                gs.result = GameResult.DRAW
            await self._handle_game_over(room, reason)

    async def _handle_game_over(self, room: Room, reason: str):
        """游戏结束"""
        gs = room.game_state
        room.phase = RoomPhase.FINISHED

        winner = "draw"
        if gs.result in (GameResult.RED_WINS, GameResult.RED_RESIGN, GameResult.RED_TIMEOUT):
            winner = "red"
        elif gs.result in (GameResult.BLACK_WINS, GameResult.BLACK_RESIGN, GameResult.BLACK_TIMEOUT):
            winner = "black"

        await self._broadcast(room, {
            "type": "game_over",
            "data": {
                "room_id": room.room_id,
                "winner": winner,
                "result": int(gs.result),
                "reason": reason,
                "total_moves": gs.move_no,
            }
        })

        # 写入数据库、更新 ELO
        await self._save_game_result(room)

    async def _save_game_result(self, room: Room):
        """保存对局结果到数据库，更新 ELO 积分"""
        gs = room.game_state
        winner = "draw"
        red_user_id = room.red_player.user_id if room.red_player else None
        black_user_id = room.black_player.user_id if room.black_player else None

        if gs.result in (GameResult.RED_WINS, GameResult.RED_RESIGN, GameResult.RED_TIMEOUT):
            winner = "red"
        elif gs.result in (GameResult.BLACK_WINS, GameResult.BLACK_RESIGN, GameResult.BLACK_TIMEOUT):
            winner = "black"

        # 写入 game_history
        # 更新 ELO（仅 PvP）
        if room.room_type == RoomType.PVP and red_user_id and black_user_id:
            red_rating = await self.elo_service.get_rating(red_user_id)
            black_rating = await self.elo_service.get_rating(black_user_id)
            result = 1.0 if winner == "red" else (0.0 if winner == "black" else 0.5)
            change_red, change_black = await self.elo_service.calculate_and_update(
                red_user_id, black_user_id,
                red_rating, black_rating, result
            )
            # 推送积分变化
            for player, change in [(room.red_player, change_red), (room.black_player, change_black)]:
                if player:
                    await player.send({
                        "type": "rating_update",
                        "data": {"change": change, "new_rating": red_rating + change_red if player == room.red_player else black_rating + change_black}
                    })

    async def _handle_timeout(self, room: Room, side: str):
        """超时判负"""
        gs = room.game_state
        if side == "red":
            gs.result = GameResult.RED_TIMEOUT
        else:
            gs.result = GameResult.BLACK_TIMEOUT
        await self._handle_game_over(room, "timeout")

    async def _broadcast(self, room: Room, msg: dict):
        """向房间内所有在线玩家广播"""
        for player in [room.red_player, room.black_player]:
            if player and player.is_connected:
                await player.send(msg)

    async def _cleanup_room(self, room: Room):
        """清理房间资源"""
        room.phase = RoomPhase.FINISHED
        # 移除用户→房间映射
        for player in [room.red_player, room.black_player]:
            if player:
                self.user_rooms.pop(player.user_id, None)
        self.rooms.pop(room.room_id, None)
        self.tasks.pop(room.room_id, None)

    # ---- 查询 ----

    def get_room(self, room_id: str) -> Room | None:
        return self.rooms.get(room_id)

    def get_user_room(self, user_id: int) -> Room | None:
        room_id = self.user_rooms.get(user_id)
        if room_id:
            return self.rooms.get(room_id)
        return None

    def get_waiting_rooms(self) -> list[Room]:
        return [r for r in self.rooms.values() if r.phase == RoomPhase.WAITING]
```

### 5.4 RoomHandler

```python
# room/room_handler.py
from chess.move import Move
from chess.move_validator import MoveValidator
from chess.piece import Color
from room.room import RoomPhase, RoomType
from protocol.outbound import send_error

class RoomHandler:
    """处理房间和游戏相关的 WebSocket 消息"""

    async def handle(self, conn, msg):
        handlers = {
            "room_create":   self._create_room,
            "room_list":     self._list_rooms,
            "room_join":     self._join_room,
            "room_leave":    self._leave_room,
            "game_move":     self._game_move,
            "game_resign":   self._game_resign,
            "game_draw_req": self._game_draw_req,
            "game_draw_ans": self._game_draw_ans,
        }
        handler = handlers.get(msg["type"])
        if handler:
            await handler(conn, msg)

    async def _create_room(self, conn, msg):
        """创建房间"""
        # 检查是否已在房间中
        if self.room_manager.get_user_room(conn.user_id):
            await conn.send({"type": "error", "data": {"code": 3004, "message": "already in room"}})
            return

        import uuid
        room_id = str(uuid.uuid4())
        player = self._make_player_session(conn, "red")
        room = await self.room_manager.create_manual_room(room_id, player)

        conn.state = ConnectionState.IN_ROOM
        conn.room_id = room_id

        await conn.send({
            "type": "room_created",
            "data": {
                "room_id": room_id,
                "your_side": "red",
                "status": "waiting",
            }
        })

    async def _list_rooms(self, conn, msg):
        """获取等待中的房间列表"""
        rooms = self.room_manager.get_waiting_rooms()
        room_list = []
        for r in rooms:
            room_list.append({
                "room_id": r.room_id,
                "red_player": {"user_id": r.red_player.user_id, "username": r.red_player.username} if r.red_player else None,
                "created_at": r.room_id,  # 简化
            })
        await conn.send({"type": "room_list", "data": {"rooms": room_list}})

    async def _join_room(self, conn, msg):
        """加入房间"""
        if self.room_manager.get_user_room(conn.user_id):
            await conn.send({"type": "error", "data": {"code": 3004, "message": "already in room"}})
            return

        room_id = msg["data"].get("room_id")
        player = self._make_player_session(conn, "black")
        room = await self.room_manager.join_room(room_id, player)

        if not room:
            await conn.send({"type": "error", "data": {"code": 3001, "message": "cannot join room"}})
            return

        conn.state = ConnectionState.IN_ROOM
        conn.room_id = room_id

        # game_start 由 RoomManager._run_room 广播

    async def _game_move(self, conn, msg):
        """玩家落子"""
        room = self.room_manager.get_user_room(conn.user_id)
        if not room or room.phase != RoomPhase.PLAYING:
            await conn.send({"type": "error", "data": {"code": 3005, "message": "not in room"}})
            return

        side = room.get_player_side(conn.user_id)
        current_side = "red" if room.game_state.current_turn == Color.RED else "black"

        if side != current_side:
            await conn.send({"type": "error", "data": {"code": 3006, "message": "not your turn"}})
            return

        # 解析着法
        data = msg["data"]
        try:
            from_pos = data["from"]
            to_pos = data["to"]
            from_col = ord(from_pos[0]) - ord('a')
            from_row = int(from_pos[1:])
            to_col = ord(to_pos[0]) - ord('a')
            to_row = int(to_pos[1:])
            move = Move(from_col, from_row, to_col, to_row)
        except Exception:
            await conn.send({"type": "error", "data": {"code": 3007, "message": "invalid move format"}})
            return

        # 验证着法
        validator = MoveValidator(room.game_state.board)
        valid, err = validator.validate_and_apply(room.game_state, move)
        if not valid:
            await conn.send({"type": "error", "data": {"code": 3007, "message": err}})
            return

        # 通知房间协程继续
        await self.room_manager.apply_player_move(room, move, side)

    async def _game_resign(self, conn, msg):
        """认输"""
        room = self.room_manager.get_user_room(conn.user_id)
        if not room or room.phase != RoomPhase.PLAYING:
            return

        side = room.get_player_side(conn.user_id)
        if side == "red":
            room.game_state.result = GameResult.RED_RESIGN
        else:
            room.game_state.result = GameResult.BLACK_RESIGN

        await self.room_manager._handle_game_over(room, "resign")
        room.move_event.set()  # 中断等待

    async def _game_draw_req(self, conn, msg):
        """和棋请求"""
        room = self.room_manager.get_user_room(conn.user_id)
        if not room or room.phase != RoomPhase.PLAYING:
            return

        side = room.get_player_side(conn.user_id)
        opponent = room.get_opponent(conn.user_id)
        if opponent and opponent.is_connected:
            await opponent.send({"type": "draw_request", "data": {"from": side}})

    async def _game_draw_ans(self, conn, msg):
        """和棋应答"""
        room = self.room_manager.get_user_room(conn.user_id)
        if not room or room.phase != RoomPhase.PLAYING:
            return

        accept = msg["data"].get("accept", False)
        side = room.get_player_side(conn.user_id)
        opponent = room.get_opposite_player(conn.user_id)

        if accept:
            room.game_state.result = GameResult.DRAW
            await self.room_manager._handle_game_over(room, "draw_agreement")
            room.move_event.set()
        else:
            if opponent and opponent.is_connected:
                await opponent.send({"type": "draw_answered", "data": {"from": side, "accept": False}})
```

---

## 六、匹配模块

### 6.1 MatchHandler

```python
# match/match_handler.py
class MatchHandler:
    async def handle(self, conn, msg):
        handlers = {
            "match_join":  self._join,
            "match_leave": self._leave,
        }
        handler = handlers.get(msg["type"])
        if handler:
            await handler(conn, msg)

    async def _join(self, conn, msg):
        """加入匹配队列"""
        if self.room_manager.get_user_room(conn.user_id):
            await conn.send({"type": "error", "data": {"code": 3004, "message": "already in room"}})
            return

        # 获取用户 ELO
        rating = await self.user_service.get_rating(conn.user_id)

        await self.match_service.join_queue(conn.user_id, conn.username, rating)
        conn.state = ConnectionState.MATCHMAKING

        await conn.send({
            "type": "match_queued",
            "data": {"status": "queued", "rating": rating}
        })

    async def _leave(self, conn, msg):
        """离开匹配队列"""
        await self.match_service.leave_queue(conn.user_id)
        conn.state = ConnectionState.AUTHENTICATED
        await conn.send({"type": "match_left", "data": {"status": "left"}})
```

### 6.2 MatchService（ELO 匹配引擎）

```python
# match/match_service.py
import asyncio
import uuid
import logging
from match.match_queue import MatchQueue

logger = logging.getLogger(__name__)


class MatchService:
    """
    ELO 匹配引擎
    后台 asyncio 协程定期扫描匹配队列
    """

    def __init__(self, room_manager, connection_manager, user_service):
        self.room_manager = room_manager
        self.connection_manager = connection_manager
        self.user_service = user_service
        self.queue = MatchQueue()
        self._task: asyncio.Task | None = None

    async def start(self):
        """启动匹配循环"""
        self._task = asyncio.create_task(self._match_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()

    async def join_queue(self, user_id: int, username: str, rating: int):
        self.queue.add(user_id, username, rating)

    async def leave_queue(self, user_id: int):
        self.queue.remove(user_id)

    async def _match_loop(self):
        """每 2 秒扫描一次匹配队列"""
        while True:
            try:
                await asyncio.sleep(2)
                await self._try_match()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Match loop error: {e}")

    async def _try_match(self):
        """尝试匹配"""
        pair = self.queue.find_match()
        if not pair:
            return

        red_entry, black_entry = pair

        # 获取连接
        red_conn = self.connection_manager.get(red_entry.user_id)
        black_conn = self.connection_manager.get(black_entry.user_id)

        if not red_conn or not black_conn:
            # 一方已断线，移除
            self.queue.remove(red_entry.user_id)
            self.queue.remove(black_entry.user_id)
            return

        # 创建匹配房间 — 直接 PLAYING
        import uuid
        room_id = str(uuid.uuid4())

        from room.player_session import PlayerSession
        red_player = PlayerSession(user_id=red_entry.user_id, username=red_entry.username, side="red", ws=red_conn.ws)
        black_player = PlayerSession(user_id=black_entry.user_id, username=black_entry.username, side="black", ws=black_conn.ws)

        room = await self.room_manager.create_match_room(room_id, red_player, black_player)

        # 更新连接状态
        red_conn.state = ConnectionState.IN_ROOM
        red_conn.room_id = room_id
        black_conn.state = ConnectionState.IN_ROOM
        black_conn.room_id = room_id

        # 通知双方
        await red_conn.send({
            "type": "match_found",
            "data": {
                "room_id": room_id,
                "your_side": "red",
                "opponent": {"user_id": black_entry.user_id, "username": black_entry.username, "rating": black_entry.rating}
            }
        })
        await black_conn.send({
            "type": "match_found",
            "data": {
                "room_id": room_id,
                "your_side": "black",
                "opponent": {"user_id": red_entry.user_id, "username": red_entry.username, "rating": red_entry.rating}
            }
        })

        logger.info(f"Matched: {red_entry.username} vs {black_entry.username}, room={room_id}")
```

### 6.3 MatchQueue

```python
# match/match_queue.py
import time
from dataclasses import dataclass
from typing import Optional

@dataclass
class QueueEntry:
    user_id: int
    username: str
    rating: int
    joined_at: float

class MatchQueue:
    """
    匹配队列 — 内存 SortedSet
    按积分排序，贪心匹配
    """

    def __init__(self):
        self.entries: dict[int, QueueEntry] = {}  # user_id → entry
        self._sorted: list[QueueEntry] = []

    def add(self, user_id: int, username: str, rating: int):
        entry = QueueEntry(user_id, username, rating, time.time())
        self.entries[user_id] = entry
        self._rebuild()

    def remove(self, user_id: int):
        self.entries.pop(user_id, None)
        self._rebuild()

    def find_match(self) -> Optional[tuple[QueueEntry, QueueEntry]]:
        """
        找到一对积分差在阈值内的玩家
        返回 (red_entry, black_entry) 或 None
        """
        if len(self._sorted) < 2:
            return None

        for i in range(len(self._sorted) - 1):
            a = self._sorted[i]
            b = self._sorted[i + 1]

            threshold = self._get_threshold(a, b)
            diff = abs(a.rating - b.rating)

            if diff <= threshold:
                # 匹配成功
                self.entries.pop(a.user_id)
                self.entries.pop(b.user_id)
                self._rebuild()

                # 积分高的执红
                if a.rating >= b.rating:
                    return a, b
                else:
                    return b, a

        return None

    def _get_threshold(self, a: QueueEntry, b: QueueEntry) -> int:
        """动态阈值"""
        min_rating = min(a.rating, b.rating)
        min_games = min(a.rating, b.rating)  # 简化，实际应查 games_count

        # 基础阈值
        if min_games < 5:   # 新手
            threshold = 200
        elif min_rating > 2000:  # 高手
            threshold = 150
        else:
            threshold = 100

        # 等待超时放宽
        wait_time = max(time.time() - a.joined_at, time.time() - b.joined_at)
        if wait_time > 60:
            threshold += 50
        if wait_time > 120:
            threshold += 50

        return threshold

    def _rebuild(self):
        self._sorted = sorted(self.entries.values(), key=lambda e: e.rating)
```

---

## 七、棋盘引擎（复用 v1.0）

> 无变更，详见 v1.0 文档或 `chess/` 模块代码。

核心组件：
- `Board` — 棋盘数据结构（10×9 数组）
- `Move` — 着法数据结构
- `MoveGenerator` — 合法着法生成
- `MoveValidator` — 着法验证（含送将检查）
- `WinChecker` — 胜负判定（将死、困毙）
- `GameState` — 游戏状态机

---

## 八、AI 推理模块（复用 v1.0）

> 无变更，详见 v1.0 文档或 `ai/` 模块代码。

核心组件：
- `AIProxy` — AI 推理调用封装（异步，线程池运行 PyTorch）
- `DifficultyController` — 难度控制（MCTS 模拟次数映射）

---

## 九、管理后台模块

### 9.1 AdminHandler

```python
# admin/admin_handler.py
class AdminHandler:
    async def handle(self, conn, msg):
        # 验证管理员权限
        user = await self.user_service.get_user(conn.user_id)
        if not user or not user.is_admin:
            await conn.send({"type": "error", "data": {"code": 1005, "message": "forbidden"}})
            return

        handlers = {
            "admin_users":  self._list_users,
            "admin_ban":    self._ban_user,
            "admin_stats":  self._get_stats,
            "admin_models": self._list_models,
        }
        handler = handlers.get(msg["type"])
        if handler:
            await handler(conn, msg)

    async def _list_users(self, conn, msg):
        data = msg["data"]
        result = await self.admin_service.list_users(
            page=data.get("page", 1),
            page_size=data.get("page_size", 20),
            search=data.get("search", ""),
        )
        await conn.send({"type": "admin_users_result", "data": result})

    async def _ban_user(self, conn, msg):
        data = msg["data"]
        await self.admin_service.ban_user(data["user_id"], data.get("banned", True), data.get("reason", ""))
        await conn.send({"type": "admin_ban_result", "data": {"success": True}})

    async def _get_stats(self, conn, msg):
        result = await self.admin_service.get_stats()
        await conn.send({"type": "admin_stats_result", "data": result})

    async def _list_models(self, conn, msg):
        result = await self.admin_service.list_models()
        await conn.send({"type": "admin_models_result", "data": result})
```

---

## 十、主入口（FastAPI + WebSocket）

```python
# main.py
import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from gateway.connection_manager import ConnectionManager, ClientConnection, ConnectionState
from gateway.message_router import MessageRouter
from auth.auth_handler import AuthHandler
from auth.auth_service import AuthService
from auth.jwt_manager import JWTManager
from user.user_handler import UserHandler
from user.user_service import UserService
from room.room_handler import RoomHandler
from room.room_manager import RoomManager
from match.match_handler import MatchHandler
from match.match_service import MatchService
from admin.admin_handler import AdminHandler
from db.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- 初始化 ----

db = Database()
connection_manager = ConnectionManager()
jwt_manager = JWTManager(config.JWT_SECRET, config.JWT_EXPIRE_HOURS)

# Repositories
user_repo = UserRepository(db.pool)
elo_repo = EloRepository(db.pool)

# Services
auth_service = AuthService(user_repo)
user_service = UserService(user_repo, elo_repo)
elo_service = EloService(elo_repo)
room_manager = RoomManager(db.pool, elo_service)
match_service = MatchService(room_manager, connection_manager, user_service)

# Handlers
auth_handler = AuthHandler(auth_service, user_service, jwt_manager, connection_manager)
user_handler = UserHandler(user_service)
room_handler = RoomHandler(room_manager)
match_handler = MatchHandler(match_service, room_manager, user_service)
admin_handler = AdminHandler(AdminService(db.pool))

# Message Router
router = MessageRouter(auth_handler, user_handler, room_handler, match_handler, admin_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    await db.connect()
    await match_service.start()
    yield
    # 关闭
    await match_service.stop()
    await db.disconnect()


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """统一 WebSocket 入口"""
    await ws.accept()

    # 创建未认证的连接对象
    conn = ClientConnection(ws=ws, user_id=0, username="")

    try:
        # 首条消息必须是认证
        auth_data = await asyncio.wait_for(ws.receive_text(), timeout=30)
        auth_msg = json.loads(auth_data)

        if auth_msg.get("type") not in ("auth_login", "auth_register", "auth_token", "reconnect"):
            await ws.send_json({"type": "error", "data": {"code": 1004, "message": "authentication required"}})
            await ws.close()
            return

        await router.route(conn, auth_msg)

        if conn.state == ConnectionState.UNAUTHENTICATED:
            await ws.close()
            return

        # 认证成功，进入消息循环
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            await router.route(conn, msg)

    except WebSocketDisconnect:
        logger.info(f"User {conn.user_id} disconnected")
    except asyncio.TimeoutError:
        await ws.send_json({"type": "error", "data": {"code": 1004, "message": "auth timeout"}})
        await ws.close()
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
    finally:
        # 清理连接
        if conn.user_id:
            await connection_manager.unregister(conn.user_id)
            # 如果在房间中，处理断线
            room = room_manager.get_user_room(conn.user_id)
            if room and room.phase == RoomPhase.PLAYING:
                player = room.get_player(conn.user_id)
                if player:
                    player.is_connected = False
                    # 通知对手
                    opponent = room.get_opponent(conn.user_id)
                    if opponent and opponent.is_connected:
                        await opponent.send({
                            "type": "opponent_left",
                            "data": {"reason": "disconnect", "timeout": 60}
                        })
                    # TODO: 启动 60s 重连计时器


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "online_users": connection_manager.online_count,
        "active_rooms": len(room_manager.rooms),
        "match_queue_size": match_service.queue.size,
    }
```

---

## 十一、心跳与断线重连

### 11.1 心跳机制

```
客户端每 30s 发送：{ "type": "ping", "data": {} }
服务端立即回复：  { "type": "pong", "data": {} }

服务端 60s 未收到 ping → 判定断线
```

### 11.2 断线重连流程

```
1. 客户端断线，服务端保留 session_token 和房间状态
2. 客户端重新连接 WebSocket
3. 客户端发送：{ "type": "reconnect", "data": { "session_token": "...", "room_id": "..." } }
4. 服务端验证：
   - session_token 有效
   - 房间仍在 PLAYING
   - 更新 PlayerSession 的 ws 引用
5. 服务端推送完整游戏状态：{ "type": "state_sync", "data": { ... } }
6. 通知对手：{ "type": "opponent_rejoin", "data": { "username": "..." } }
7. 超时 60s 未重连 → 判负 → 通知对手获胜
```

---

## 十二、配置结构

```yaml
# config.yaml
server:
  host: "0.0.0.0"
  port: 8080

database:
  host: "localhost"
  port: 5432
  user: "postgres"
  password: "your_password"
  dbname: "chinese_chess"
  min_pool: 5
  max_pool: 20

jwt:
  secret: "your-jwt-secret"
  expire_hours: 24

game:
  move_timeout_seconds: 60
  reconnect_timeout_seconds: 60
  heartbeat_interval_seconds: 30

match:
  tick_interval_seconds: 2
  base_threshold: 100
  new_player_threshold: 200
  high_rating_threshold: 150

ai:
  default_model_path: "./models/latest.pt"
  device: "cpu"

logging:
  level: "INFO"
  file: "./logs/game-service.log"
```
