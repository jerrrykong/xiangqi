# Game 服务详细设计（Python — 统一服务）

> 服务职责：用户认证、房间管理、ELO 匹配、实时对局、棋盘规则、AI 推理、管理后台
> 技术栈：Python 3.11+ / FastAPI / asyncio / asyncpg / PyTorch
> 文档版本：v2.0
> 当前实现：`game-service/` 最新代码设计

---

## 一、项目结构

```
game-service/
├── admin/
│   ├── __init__.py
│   ├── admin_handler.py        # WebSocket 管理后台消息处理
│   └── admin_service.py        # 管理业务逻辑
├── ai/
│   ├── __init__.py
│   ├── ai_proxy.py             # AI 推理调用封装
│   └── difficulty.py           # 难度控制规则
├── auth/
│   ├── __init__.py
│   ├── auth_handler.py         # WebSocket 认证消息处理
│   ├── auth_service.py         # 登录/注册业务逻辑
│   └── jwt_manager.py          # JWT 生成 / 解析 / 刷新
├── chess/
│   ├── __init__.py
│   ├── board.py                # 棋盘数据结构与 FEN 序列化
│   ├── constants.py           # 棋子、颜色、结果类型
│   ├── game.py                 # 棋类与游戏状态机
│   ├── move.py                 # 着法数据结构
│   ├── move_generator.py       # 合法着法生成
│   ├── move_validator.py       # 着法验证
│   ├── piece.py                # 棋子定义
│   ├── win_checker.py          # 胜负判定
│   ├── recorder.py             # 对局记录（历史着法）
│   └── __pycache__/
├── config.py                   # YAML + 环境变量配置加载
├── config.yaml
├── db/
│   ├── __init__.py
│   ├── database.py             # asyncpg 连接池
│   └── migrations/
├── gateway/
│   ├── __init__.py
│   ├── connection_manager.py   # WebSocket 连接管理
│   ├── connection_state.py     # 连接状态机与状态转换规则
│   └── message_router.py       # 消息路由与状态访问控制
├── main.py                     # FastAPI 入口 + WebSocket / 心跳 / 生命周期
├── match/
│   ├── __init__.py
│   ├── match_handler.py        # WebSocket 匹配消息处理
│   ├── match_service.py        # ELO 匹配引擎
│   └── match_queue.py          # 排队与动态匹配范围
├── protocol/
│   ├── __init__.py
│   ├── inbound.py
│   ├── message.py
│   ├── outbound.py
│   └── serializer.py
├── requirements.txt
├── room/
│   ├── __init__.py
│   ├── player_session.py       # 房间内玩家会话
│   ├── room.py                 # 房间对象与生命周期状态
│   ├── room_handler.py         # WebSocket 房间/游戏消息处理
│   ├── room_manager.py         # 活跃房间管理与游戏流程
│   ├── room_repository.py      # 房间与对局持久化接口
│   └── timers.py               # 对局计时器 / 超时处理
└── user/
    ├── __init__.py
    ├── user_handler.py         # WebSocket 用户消息处理
    ├── user_repository.py      # 用户数据访问
    ├── user_service.py         # 用户业务逻辑
    └── elo_repository.py       # ELO 数据访问与排名
```

---

## 二、WebSocket 连接管理

### 2.1 连接状态机

```python
from enum import IntEnum

class ConnectionState(IntEnum):
    UNAUTHENTICATED = 0  # 刚连接，未认证
    AUTHENTICATED = 1    # 已认证，在大厅
    IN_ROOM = 2          # 在房间中（对局中）
    MATCHMAKING = 3      # 在匹配队列中

VALID_TRANSITIONS = {
    ConnectionState.UNAUTHENTICATED: {ConnectionState.AUTHENTICATED},
    ConnectionState.AUTHENTICATED: {
        ConnectionState.IN_ROOM,
        ConnectionState.MATCHMAKING,
    },
    ConnectionState.IN_ROOM: {ConnectionState.AUTHENTICATED},
    ConnectionState.MATCHMAKING: {
        ConnectionState.AUTHENTICATED,
        ConnectionState.IN_ROOM,
    },
}


def can_transition(from_state, to_state):
    return to_state in VALID_TRANSITIONS.get(from_state, set())
```

当前状态转换规则：

- `UNAUTHENTICATED -> AUTHENTICATED`：认证成功
- `AUTHENTICATED -> IN_ROOM`：进入房间
- `AUTHENTICATED -> MATCHMAKING`：加入匹配
- `IN_ROOM -> AUTHENTICATED`：离开房间
- `MATCHMAKING -> AUTHENTICATED`：取消匹配
- `MATCHMAKING -> IN_ROOM`：匹配成功

### 2.2 ConnectionManager

`gateway/connection_manager.py` 管理 WebSocket 连接与用户绑定。

核心功能：

- `register(conn)`：注册新连接
- `bind_user(conn, user_id)`：用户认证后绑定到连接，若已有旧连接则踢掉旧会话
- `unregister(conn)`：从连接表中移除
- `get_by_user_id(user_id)`：获取当前在线连接
- `send_to_user(user_id, data)`：向指定用户发送数据
- `broadcast(data, exclude=None)`：向全部已认证用户广播

`ClientConnection` 记录了：

- `conn_id`
- `user_id`
- `username`
- `state`
- `room_id`
- `session_token`
- `is_admin`
- `last_ping`

发送失败时会将连接标记为不可用。

### 2.3 MessageRouter

`gateway/message_router.py` 负责：

- 请求合法性校验
- 状态访问控制
- 按消息前缀路由到对应 Handler

消息路由方式：

- `ping` 直接回复 `pong`
- 按 `msg_type.split("_")[0]` 查找注册的 Handler
- 如果当前状态不允许该消息，则返回错误

权限与消息分组：

- `auth` 前缀：认证相关消息
- `user` 前缀：用户信息查询/更新
- `room` / `game` 前缀：房间/游戏操作
- `match` 前缀：匹配操作
- `admin` 前缀：管理后台操作
- `reconnect`：特殊认证/重连流程

---

## 三、认证模块

### 3.1 AuthHandler

`auth/auth_handler.py` 处理认证类消息：

- `auth_login`
- `auth_register`
- `auth_token`
- `auth_refresh`
- `reconnect`

常见返回消息：

- `auth_result`
- `auth_register_result`
- `auth_token_result`
- `auth_refresh_result`
- `reconnect_result`
- `state_sync`

登录结果包括：

- `token`
- `refresh_token`
- `expires_at`
- `session_token`
- `rating`
- `games_count`
- `is_admin`

`reconnect` 会使用旧 `session_token` 查找原连接，并将玩家恢复到房间状态。

### 3.2 AuthService

`auth/auth_service.py` 负责登录与注册逻辑：

- `login(username, password)`：
  - 从用户仓库获取用户
  - 验证 bcrypt 密码
  - 检查是否被封禁
  - 更新 `last_login`

- `register(username, password, nickname)`：
  - 校验用户名唯一性
  - 密码强度校验
  - 创建用户记录
  - 初始化默认 ELO 评分

---

## 四、用户模块

### 4.1 UserHandler

`user/user_handler.py` 处理用户相关消息：

- `user_get_me`
- `user_update_profile`
- `user_get_rankings`
- `user_get_history`

### 4.2 UserService

`user/user_service.py` 提供：

- `get_user_info(user_id)`：返回用户基础信息和评分数据
- `update_profile(user_id, data)`：更新昵称与头像
- `get_rankings(page, page_size)`：分页排行榜
- `get_history(user_id, page, page_size, game_type)`：用户对局历史
- `calculate_elo(...)`：传统 ELO 算分方法
- `calculate_score(...)`：当前胜负评分规则
- `apply_rating_floor(...)`：分数保底规则

---

## 五、房间模块

### 5.1 房间生命周期

`room/room.py` 定义房间生命周期：

- `WAITING`：手动房间等待对手
- `READY`：双方加入后等待点击开始
- `PLAYING`：对局进行中
- `FINISHED`：对局结束，可发起续局

流程：

- 手动 PvP：`room_create` → `room_join` → 双方 `game_ready` → 对局开始
- 匹配 PvP：`match_join` → `match_found` → 直接开始
- PvE：`room_create(room_type=pve)` → 直接开始

### 5.2 Room 数据模型

`room/room.py` 关键字段：

- `room_id`
- `room_type` (`PVP` / `PVE`)
- `source` (`MANUAL` / `MATCH`)
- `phase` (`WAITING` / `READY` / `PLAYING` / `FINISHED`)
- `red_player` / `black_player`
- `game_state`
- `timer`
- `initial_time` / `increment`
- `difficulty`
- `ai_side`
- `ready_players`
- `rematch_players`
- `game_count`

### 5.3 RoomManager

`room/room_manager.py` 是房间生命周期和游戏流程的核心。

功能包括：

- 创建房间：`create_manual_room()` / `create_match_room()` / `create_pve_room()`
- 加入房间：`join_room()` → READY
- 准备开始：`player_ready()`
- 续局：`rematch()`
- 离开房间：`leave_room()`
- 运行对局：`_run_room()`
- 处理落子：`apply_player_move()` / `_apply_and_broadcast_move()`
- AI 行为：`_do_ai_move()`
- 结束逻辑：`_handle_game_over()`
- 数据持久化：`_save_game_result()`
- 房间清理：`_cleanup_room()`

`RoomManager` 还负责将房间与对局状态写入数据库，以及在房间结束后更新 ELO 分数。

### 5.3.1 新增组件与配置

为提高房间驱动的可测试性与可维护性，引入 `RoomRunner` 组件：

- `RoomRunner`：每个房间对应一个短生命周期协程，负责以状态机方式驱动房间（WAITING → READY → PLAYING → FINISHED），并在合适时机调用 `RoomManager._run_room(room)` 来执行对局循环。
- `RoomRunner` 负责在 `READY` 阶段触发 AI 的短延迟自动 ready，`FINISHED` 阶段收集 rematch 请求并在满足条件时直接在 runner 内部启动下一局或在超时后回退到 `WAITING`。

新增的配置项（位于 `game` 配置段）：
- `persist_every_n_moves`：整数，默认 `5`，表示每 N 步持久化一次房间状态（减少 I/O）；
- `ai_ready_delay`：浮点，默认 `0.25` 秒，AI 在 READY 阶段自动 ready 的延迟；
- `ai_rematch_delay`：浮点，默认 `0.5` 秒，AI 在 FINISHED 阶段自动 rematch 的延迟；
- `rematch_timeout`：浮点，默认 `60.0` 秒，FINISHED 状态等待 rematch 的超时时间。

房间数据模型扩展：
- `allow_full_ai_run`：布尔，预留字段，表示是否允许该房间在无真人情况下持续自动对弈；仅通过 API 创建/删除时设置，默认 `False`。

持久化策略调整：将“每步保存”改为“每 N 步或失败后回退保存”的策略，以减少数据库写入压力，同时在关键点（对局结束）保证写入完整记录以便恢复与统计。

### 5.4 房间消息与交互

`room/room_handler.py` 支持的消息：

- `room_create`
- `room_list`
- `room_join`
- `room_leave`
- `game_move`
- `game_resign`
- `game_draw_req`
- `game_draw_ans`
- `game_ready`
- `game_rematch`

服务端推送（与 READY / FINISHED 流程相关）:

- `opponent_ready`：告知玩家对手已准备（主要用于 bot 自动就绪场景，`data` 包含 `user_id`）。
- `opponent_rematch`：告知玩家对手发起了续局（`data` 包含 `user_id`）。

在 `FINISHED` 阶段，`RoomRunner` 会等待 `rematch_timeout`（可配置）时间以收集双方的续局意向；若在超时内双方达成一致，则在原房间内交换颜色并直接进入下一局，否则回退到 `WAITING`。

`room_create` 支持 `room_type=pvp` 和 `room_type=pve`。

`room_join` 后进入 `READY` 状态，房间创建者会收到 `player_joined`。对局开始由双方发送 `game_ready` 触发。

`game_move` 使用位置数组格式：

```json
{"from_pos": [row, col], "to_pos": [row, col]}
```

### 5.5 离开与清理规则

`RoomManager.leave_room()` 的规则：

- PLAYING 状态离开相当于认输
- READY/WAITING 状态离开可直接退出
- 若房间中无真实玩家，则删除房间
- 全机器人房间不会自动删除，支持自动续局/对弈

---

## 六、匹配模块

### 6.1 MatchHandler

`match/match_handler.py` 负责：

- `match_join`
- `match_leave`

加入匹配前会校验玩家是否已经在房间中。

### 6.2 MatchService

`match/match_service.py` 的职责：

- 管理匹配队列
- 周期性扫描匹配
- 创建匹配房间
- 推送 `match_found`

匹配响应：

- `match_queued`
- `match_left`
- `match_found`

### 6.3 MatchQueue

`match/match_queue.py` 使用内存排序队列实现动态 ELO 匹配。

策略：

- 按 `rating` 排序
- 随等待时间逐步放宽匹配范围
- 尽量匹配差距最小的对手

---

## 七、棋盘引擎

`chess/` 模块实现棋盘与规则引擎。

核心组件：

- `Board`：棋盘数据结构与 FEN 序列化
- `Move`：着法结构
- `MoveValidator`：着法合法性验证
- `ChessGame`：游戏状态机、落子与历史记录
- `WinChecker`：胜负判定
- `recorder`：对局记录

当前版本将 `ChessGame` 作为房间 `game_state` 的主体，在 `RoomManager` 中直接执行落子、判胜与保存。

---

## 八、AI 推理模块

`ai/ai_proxy.py` 封装异步 AI 推理调用。

`RoomManager` 在 PvE 对局中：

- 判断 `room.ai_side`
- 让 AI 下子
- 发送 `ai_thinking`
- 发送 `ai_move`

`difficulty.py` 提供默认难度与参数映射。

---

## 九、管理后台模块

`admin/admin_handler.py` 处理管理员消息：

- `admin_users`
- `admin_ban`
- `admin_stats`
- `admin_models`

管理员权限依赖 `conn.is_admin`，若未授权返回错误。

`AdminService` 提供用户列表、封禁、统计与模型信息。

---

## 十、主入口

`main.py` 负责服务初始化与生命周期：

- 读取配置
- 初始化日志
- 连接数据库
- 初始化仓库/服务/处理器
- 启动匹配服务
- 恢复活动房间
- 启动断线和心跳检查
- 提供 WebSocket `/ws`
- 提供健康检查 `/health`
- 提供内部模型热更新通知 `/internal/model/reload`

WebSocket 入口流程：

1. 接收连接并注册
2. 在 30 秒内完成认证
3. 认证后进入消息循环
4. 持续处理消息并更新 `last_ping`
5. 断开时执行 `handle_disconnect()`

`handle_disconnect()` 会：

- 标记玩家断开
- 如果在房间中，则通知对手
- 保留房间状态以便后续重连

---

## 十一、心跳与断线重连

### 11.1 心跳机制

`main.py` 启动 `heartbeat_checker()`：

- 每 `config.game.heartbeat_interval` 秒检查一次
- 超过 `config.game.heartbeat_timeout` 秒未收到 `ping` 则踢掉连接

客户端发送：

```json
{"type": "ping", "seq": 1, "data": {}}
```

服务端返回：

```json
{"type": "pong", "seq": 1, "data": {"timestamp": 1680000000000}}
```

### 11.2 断线重连流程

当前实现支持 `reconnect`：

- 使用旧 `session_token` 查找原连接
- 迁移用户状态到新连接
- 若用户仍在房间，则恢复 `IN_ROOM`
- 发送 `state_sync` 给客户端

`state_sync` 包含：

- `room_id`
- `room_type`
- `phase`
- `fen`
- `your_side`
- `current_side`
- `red_player`
- `black_player`
- `red_remaining_time`
- `black_remaining_time`
- `moves`
- `ready_players`
- `rematch_players`

---

## 十二、配置结构

当前配置项由 `config.py` 定义，可从 `config.yaml` 加载并被环境变量覆盖。

主要配置：

```yaml
server:
  host: "0.0.0.0"
  port: 8765
  workers: 1

database:
  host: "localhost"
  port: 5432
  user: "xiangqi"
  password: "xiangqi"
  dbname: "xiangqi"
  min_pool_size: 5
  max_pool_size: 20

jwt:
  secret: "your-jwt-secret-change-in-production"
  algorithm: "HS256"
  expire_hours: 168
  refresh_expire_hours: 720

game:
  default_initial_time: 600
  default_increment: 10
  max_think_time: 300
  heartbeat_interval: 30
  heartbeat_timeout: 60
  disconnect_timeout: 300

match:
  tick_interval: 2
  initial_elo_range: 200
  normal_elo_range: 100
  high_elo_range: 150
  high_elo_threshold: 2000
  expand_rate: 50
  expand_interval: 30
  max_wait_time: 180

ai:
  default_difficulty: 3
  max_threads: 4

internal:
  secret: "internal-service-secret-key"

logging:
  level: "INFO"
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
  log_dir: "logs"
  filename: "game-service.log"
  when: "midnight"
  interval: 1
  backup_count: 30
  encoding: "utf-8"
```

环境变量支持部分配置覆盖，如 `GS_SERVER_HOST`、`GS_JWT_SECRET`、`GS_DATABASE_HOST` 等。

---

## 十三、补充说明

- `room_service.py` 在当前实现中不存在，房间业务逻辑集中于 `room_manager.py` 和 `room_handler.py`。
- `ConnectionManager` 使用 `conn_id` 维护连接，用户绑定后通过 `user_id` 快速查找当前连接。
- `MessageRouter` 的状态访问控制是当前实现的核心安全机制。
- `AuthHandler` 已支持访问令牌刷新与重连恢复。
- 房间与对局持久化通过 `room_repository.py` / `game_repository` / `elo_repository.py` 协同完成。
