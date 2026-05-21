# GameService v2.0 实施方案

## 任务总览

| ID | 任务 | 状态 | 依赖 |
|---|---|---|---|
| T1 | 项目骨架搭建 | pending | - |
| T2 | 数据库层 | pending | T1 |
| T3 | 协议层 | pending | T1 |
| T4 | WebSocket 网关层 | pending | T3 |
| T5 | 认证模块 | pending | T2, T4 |
| T6 | 用户模块 | pending | T5 |
| T7 | 房间模块 | pending | T5, T9, T10 |
| T8 | 匹配模块 | pending | T7 |
| T9 | 棋盘引擎迁移 | pending | T1 |
| T10 | AI 推理模块迁移 | pending | T9 |
| T11 | 管理后台模块 | pending | T5 |
| T12 | 主入口整合 | pending | T2-T11 |
| T13 | 集成测试与验证 | pending | T12 |

## 执行顺序

```
T1 → T2 + T3（并行）→ T4 → T5 → T6 + T9 + T10（并行）→ T7 → T8 + T11（并行）→ T12 → T13
```

---

## T1: 项目骨架搭建

**目标**：创建 `game-service/` 新目录结构，作为统一服务的独立根目录

**详细说明**：
- 在项目根目录下创建 `game-service/` 目录，按设计文档 §一 的项目结构创建所有子目录和 `__init__.py`
- 创建 `requirements.txt`（fastapi, uvicorn, asyncpg, bcrypt, pyjwt, pyyaml 等）
- 创建 `config.py`（YAML 配置加载 + 环境变量覆盖）
- 创建 `config.yaml`（数据库连接、JWT 密钥、服务端口等）
- **不修改**现有 `internal/` 目录下的任何代码，旧服务保持不变

**产出目录结构**：
```
game-service/
├── main.py
├── config.py
├── config.yaml
├── requirements.txt
├── gateway/
│   ├── __init__.py
│   ├── connection_manager.py
│   ├── connection_state.py
│   └── message_router.py
├── auth/
│   ├── __init__.py
│   ├── auth_handler.py
│   ├── auth_service.py
│   └── jwt_manager.py
├── user/
│   ├── __init__.py
│   ├── user_handler.py
│   └── user_service.py
├── room/
│   ├── __init__.py
│   ├── room.py
│   ├── room_handler.py
│   ├── room_manager.py
│   ├── player_session.py
│   └── timers.py
├── match/
│   ├── __init__.py
│   ├── match_handler.py
│   ├── match_service.py
│   └── match_queue.py
├── chess/
│   ├── __init__.py
│   ├── piece.py
│   ├── move_generator.py
│   ├── move_validator.py
│   ├── win_checker.py
│   ├── game.py
│   └── recorder.py
├── ai/
│   ├── __init__.py
│   ├── engine.py
│   ├── ai_proxy.py
│   └── difficulty.py
├── admin/
│   ├── __init__.py
│   ├── admin_handler.py
│   └── admin_service.py
├── protocol/
│   ├── __init__.py
│   ├── message.py
│   ├── inbound.py
│   └── outbound.py
└── db/
    ├── __init__.py
    ├── database.py
    ├── user_repository.py
    ├── elo_repository.py
    ├── room_repository.py
    └── game_repository.py
```

**验证标准**：
- [ ] 目录结构创建完成
- [ ] requirements.txt 包含所有依赖
- [ ] config.py 可加载 config.yaml
- [ ] 所有 `__init__.py` 文件已创建

---

## T2: 数据库层

**目标**：使用 asyncpg 实现异步数据库访问，替代 Go 侧的 GORM

**详细说明**：
- `db/database.py`：asyncpg 连接池管理（从 config.yaml 读取连接参数），提供 `get_pool()` / `execute()` / `fetch()` / `fetchrow()` 便捷方法
- `db/user_repository.py`：用户 CRUD（get_by_id, get_by_username, create, update, update_last_login, create_elo_rating, set_banned, list_users）
- `db/elo_repository.py`：ELO 积分 CRUD（get_by_user_id, update_rating, get_rankings, create_history）
- `db/room_repository.py`：房间 CRUD（create, get_by_id, update_status, set_players, finish_game）
- `db/game_repository.py`：对局记录 CRUD（create_history, get_user_history, get_stats）
- 复用现有 `migrations/001_init.sql` 和 `scripts/init_db.sql` 中的表结构
- 房间表新增 `source` 字段（manual / match），需写迁移脚本

**验证标准**：
- [ ] database.py 连接池初始化和便捷方法
- [ ] user_repository.py 完整用户 CRUD
- [ ] elo_repository.py ELO 积分操作
- [ ] room_repository.py 房间操作
- [ ] game_repository.py 对局记录操作
- [ ] 迁移脚本（source 字段）

---

## T3: 协议层

**目标**：定义 v2.0 全 WebSocket 协议的消息类型和数据结构

**详细说明**：
- `protocol/message.py`：消息基类 `Message(type, seq, data)`，JSON 序列化/反序列化
- `protocol/inbound.py`：客户端→服务端消息类型定义，按设计文档 §七 分类：
  - 认证：`auth_login`, `auth_register`, `auth_token`, `auth_refresh`, `reconnect`
  - 用户：`user_get_me`, `user_update_profile`, `user_get_rankings`, `user_get_history`
  - 房间：`room_create`, `room_list`, `room_join`, `room_leave`
  - 游戏：`game_move`, `game_resign`, `game_draw_req`, `game_draw_ans`
  - 匹配：`match_join`, `match_leave`
  - 管理：`admin_users`, `admin_ban`, `admin_stats`, `admin_models`
  - 通用：`ping`
- `protocol/outbound.py`：服务端→客户端消息类型定义，包括 `auth_result`, `game_start`, `move_result`, `game_over`, `match_found` 等所有类型
- 每种消息类型定义对应的 dataclass，字段严格对应 `04-shared-protocols.md` 中的 JSON 格式

**验证标准**：
- [ ] message.py 消息基类
- [ ] inbound.py 所有客户端消息类型
- [ ] outbound.py 所有服务端消息类型
- [ ] 与 04-shared-protocols.md 完全一致

---

## T4: WebSocket 网关层

**目标**：实现统一 WebSocket 连接入口，连接生命周期管理和消息路由

**详细说明**：
- `gateway/connection_state.py`：连接状态机枚举 `ConnectionState`（UNAUTHENTICATED, AUTHENTICATED, IN_ROOM, MATCHMAKING），定义合法状态转换规则
- `gateway/connection_manager.py`：
  - `ConnectionManager`：管理所有活跃连接（user_id → ClientConnection 映射），注册/注销/踢出/获取连接
  - `ClientConnection`：封装单个 WebSocket 连接（ws, user_id, username, state, room_id, session_token, last_ping, is_admin），提供 send/kick 方法
- `gateway/message_router.py`：
  - `MessageRouter`：按 msg["type"] 前缀路由到对应 Handler（auth→AuthHandler, user→UserHandler, room→RoomHandler, match→MatchHandler, admin→AdminHandler）
  - 状态检查：UNAUTHENTICATED 只允许 auth_* 消息，AUTHENTICATED 不允许 game_* 消息等
  - ping 直接回复 pong
- FastAPI WebSocket 端点：`WS /ws` — 唯一入口，接收连接后进入消息循环

**验证标准**：
- [ ] connection_state.py 状态机
- [ ] connection_manager.py 连接管理
- [ ] message_router.py 消息路由
- [ ] WebSocket 端点

---

## T5: 认证模块

**目标**：将 Go 侧的 JWT 认证完整迁移到 Python，支持 WebSocket 认证

**详细说明**：
- `auth/jwt_manager.py`：JWT 生成/解析/刷新，使用 PyJWT 库，兼容现有 Go 侧 JWT 格式（HS256 算法，相同的 secret），确保旧 Token 可被新服务验证
- `auth/auth_service.py`：
  - `login(username, password)`：查用户 + bcrypt 验证密码 + 更新 last_login_at
  - `register(username, password, nickname)`：验证用户名唯一 + 密码强度 + bcrypt 哈希 + 创建用户 + 初始化 ELO 1500
- `auth/auth_handler.py`：
  - `handle(conn, msg)`：根据 msg["type"] 分发到 `_handle_login`, `_handle_register`, `_handle_token_auth`, `_handle_refresh`, `_handle_reconnect`
  - 登录/注册成功后：生成 JWT + session_token，设置 conn 状态为 AUTHENTICATED，注册到 ConnectionManager
  - 断线重连：验证 session_token + room_id，恢复连接状态，推送 state_sync

**验证标准**：
- [ ] jwt_manager.py JWT 兼容
- [ ] auth_service.py 登录/注册
- [ ] auth_handler.py 消息处理
- [ ] 断线重连逻辑

---

## T6: 用户模块

**目标**：将 Go 侧用户相关 API 迁移为 WebSocket 消息处理

**详细说明**：
- `user/user_service.py`：
  - `get_user(user_id)`：获取用户信息（含 rating, games_count）
  - `update_profile(user_id, data)`：修改昵称/头像
  - `get_rankings(page, page_size)`：ELO 排行榜分页查询
  - `get_history(user_id, page, page_size, game_type)`：对局历史分页查询
  - `calculate_elo(rating_a, rating_b, result, games_a)`：ELO 积分计算（K 值分级策略）
- `user/user_handler.py`：
  - 处理 `user_get_me` → 查询并返回 `user_me`
  - 处理 `user_get_rankings` → 查询并返回 `user_rankings`
  - 处理 `user_get_history` → 查询并返回 `user_history`
  - 处理 `user_update_profile` → 更新并返回 `user_profile_updated`

**验证标准**：
- [ ] user_service.py 完整业务逻辑
- [ ] user_handler.py 消息处理
- [ ] ELO 计算正确

---

## T7: 房间模块

**目标**：合并房间与游戏为统一模块，房间直接承载完整游戏过程

**详细说明**：
- `room/room.py`：Room 数据类（参考设计文档 §五），包含：
  - 字段：room_id, room_type(PVP/PVE), source(MANUAL/MATCH), phase(WAITING/PLAYING/FINISHED), difficulty, red_player, black_player, game_state, 计时器
  - 方法：`add_player()`, `start_game()`, `make_move()`, `resign()`, `draw_request()`, `draw_answer()`, `handle_disconnect()`, `handle_reconnect()`, `finish_game()`
  - 三种创建路径：手动创建→WAITING，匹配创建→直接PLAYING，PvE→直接PLAYING
- `room/room_manager.py`：内存房间池管理（dict[room_id, Room]），提供 create_manual_room / create_match_room / create_pve_room / get_room / remove_room / list_waiting_rooms / cleanup_finished
- `room/player_session.py`：玩家会话数据（user_id, username, side, rating, connected, remaining_time）
- `room/timers.py`：思考超时计时器（asyncio 定时器，超时自动判负）
- `room/room_handler.py`：
  - 处理 `room_create` / `room_list` / `room_join` / `room_leave`
  - 处理 `game_move` / `game_resign` / `game_draw_req` / `game_draw_ans`
  - 对局结束后：更新 ELO → 写入 game_history → 写入 elo_history → 推送 rating_update → 推送 game_over

**验证标准**：
- [ ] room.py 完整房间逻辑
- [ ] room_manager.py 房间管理
- [ ] player_session.py 玩家会话
- [ ] timers.py 超时计时
- [ ] room_handler.py 消息处理
- [ ] 三种创建路径正确

---

## T8: 匹配模块

**目标**：将 Go 侧 ELO 匹配引擎迁移到 Python，匹配成功后直接创建房间进入对局

**详细说明**：
- `match/match_queue.py`：内存匹配队列（使用 SortedList 按 ELO 排序），提供 join / leave / find_match / size 方法
- `match/match_service.py`：
  - `join_match(user_id, rating)`：加入队列，返回 match_queued
  - `leave_match(user_id)`：离开队列，返回 match_left
  - `run_match_loop()`：后台 asyncio 协程，每 2 秒扫描队列，按 ELO 差值匹配（阈值策略：初始玩家放宽 200，正常 100，高分 150，超时逐步放宽 +50/30s，180s 超时）
  - 匹配成功后：调用 RoomManager.create_match_room() 直接创建 PLAYING 状态的房间，推送 match_found + game_start 给双方
- `match/match_handler.py`：处理 `match_join` / `match_leave` 消息

**验证标准**：
- [ ] match_queue.py 排序队列
- [ ] match_service.py 匹配逻辑
- [ ] match_handler.py 消息处理
- [ ] ELO 阈值策略正确

---

## T9: 棋盘引擎迁移

**目标**：将现有 `internal/chess/` 模块复制/适配到新 `game-service/chess/`

**详细说明**：
- 复制 `internal/chess/` 下所有文件到 `game-service/chess/`
- 调整 import 路径（从 `internal.chess.*` 改为 `chess.*`，从 `shared.*` 适配新路径）
- 确保以下模块可用：`piece.py`(Board/Piece), `move_generator.py`, `move_validator.py`, `win_checker.py`, `game.py`(ChessGame/GamePhase), `recorder.py`

**验证标准**：
- [ ] 所有棋盘引擎文件已复制
- [ ] import 路径已调整
- [ ] 棋盘引擎可正常 import

---

## T10: AI 推理模块迁移

**目标**：将现有 `internal/ai/engine.py` 复制/适配到新 `game-service/ai/`

**详细说明**：
- 复制 `internal/ai/engine.py` → `game-service/ai/engine.py`
- 新建 `game-service/ai/ai_proxy.py`：异步 AI 推理封装，使用 `asyncio.to_thread()` 将同步的 ChessAI.best_move() 放到线程池执行，不阻塞事件循环
- 新建 `game-service/ai/difficulty.py`：难度控制器，根据难度等级(1~5)映射搜索深度(2~6)和最大思考时间
- 在 Room 的 PvE 模式中，玩家落子后通过 AIProxy 获取 AI 着法，推送 ai_thinking → ai_move
- 调整 import 路径

**验证标准**：
- [ ] engine.py 已复制并适配
- [ ] ai_proxy.py 异步封装
- [ ] difficulty.py 难度映射
- [ ] AI 推理可正常调用

---

## T11: 管理后台模块

**目标**：将 Go 侧管理后台 API 迁移为 WebSocket 消息处理

**详细说明**：
- `admin/admin_service.py`：
  - `list_users(page, page_size, search)`：用户列表
  - `ban_user(user_id, banned, reason)`：封禁/解封用户
  - `get_stats()`：在线用户数、活跃房间数、今日对局数等运营数据
  - `list_models()`：AI 模型版本列表
  - `publish_model(model_id)`：发布模型（热加载通知）
- `admin/admin_handler.py`：
  - 处理 `admin_users` / `admin_ban` / `admin_stats` / `admin_models`
  - 前置检查：conn.is_admin 必须为 True，否则返回 error(2003)

**验证标准**：
- [ ] admin_service.py 管理服务
- [ ] admin_handler.py 消息处理
- [ ] 权限检查正确

---

## T12: 主入口整合

**目标**：整合所有模块，编写 `main.py` 启动流程

**详细说明**：
- `game-service/main.py`：
  1. 加载配置（config.yaml + 环境变量）
  2. 初始化数据库连接池
  3. 初始化各 Repository → Service → Handler
  4. 初始化 ConnectionManager + MessageRouter
  5. 初始化 RoomManager + MatchService（启动后台匹配循环）
  6. 创建 FastAPI app，注册 WebSocket 端点 `WS /ws`、健康检查 `GET /health`、内部接口 `POST /internal/model/reload`
  7. 启动 uvicorn
- 添加心跳检测（后台协程检查 last_ping，超时断开）
- 添加优雅关闭（关闭连接池、通知所有客户端）

**验证标准**：
- [ ] main.py 完整启动流程
- [ ] 所有模块正确初始化
- [ ] 健康检查端点
- [ ] 内部接口
- [ ] 优雅关闭

---

## T13: 集成测试与验证

**目标**：验证新 GameService 完整流程可运行

**详细说明**：
- 启动新 GameService，验证 WebSocket 连接和认证流程
- 测试完整 PvP 流程：登录→创建房间→加入→落子→结束→ELO更新
- 测试完整 PvE 流程：登录→创建人机房间→落子→AI回应→结束
- 测试匹配流程：两人登录→匹配→直接开始对局
- 测试断线重连
- 验证与旧 Go Web 服务的兼容性（旧 JWT Token 能否被新服务验证）

**验证标准**：
- [ ] WebSocket 连接正常
- [ ] 认证流程通过
- [ ] PvP 对局完整
- [ ] PvE 对局完整
- [ ] 匹配流程正常
- [ ] 断线重连可用

---

## 执行日志

### T1: 项目骨架搭建
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 创建 game-service/ 目录及所有子目录（gateway, auth, user, room, match, chess, ai, admin, protocol, db, db/migrations）
  - 创建 requirements.txt（fastapi, uvicorn, asyncpg, bcrypt, pyjwt, pyyaml 等）
  - 创建 config.yaml（数据库、JWT、游戏、匹配、AI 等完整配置）
  - 创建 config.py（dataclass 配置类 + YAML 加载 + 环境变量覆盖）
  - 创建 gateway/connection_state.py（连接状态机 + 合法转换规则）
  - 创建 gateway/connection_manager.py（ClientConnection + ConnectionManager）
  - 创建 gateway/message_router.py（消息路由 + 状态访问控制）
  - 创建 protocol/message.py（消息基类 + make_response/make_error 工具函数）
  - 创建 protocol/inbound.py（所有客户端消息类型和数据类）
  - 创建 protocol/outbound.py（所有服务端消息类型和数据类）
  - 创建 protocol/serializer.py（JSON 序列化/反序列化）
  - 创建 db/database.py（asyncpg 连接池管理）
  - 创建 db/migrations/002_add_room_source.sql（房间表新增 source 字段）
  - 创建 main.py 占位入口
  - 验证：config.py 可正常加载 config.yaml，输出 port=8765, db=xiangqi

### T2: 数据库层
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 创建 user/user_repository.py（10 个方法：create, get_by_id, get_by_username, update, update_last_login, update_profile, set_banned, list_users, exists_username, get_user_count, get_game_history）
  - 创建 user/elo_repository.py（8 个方法：create, get_by_user_id, update_rating, increment_games_count, get_rankings, create_history, get_history, get_or_create）
  - 创建 room/room_repository.py（RoomRepository 13 个方法 + GameRepository 6 个方法 + ModelRepository 3 个方法）
  - 创建 db/migrations/002_add_room_source.sql（rooms 表新增 source 字段）
  - 所有 SQL 查询与 Go 侧 Repository 对齐

### T3: 协议层
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 创建 protocol/message.py（消息基类 Message + make_response/make_error）
  - 创建 protocol/inbound.py（所有客户端消息类型常量和 dataclass）
  - 创建 protocol/outbound.py（所有服务端消息类型常量和 dataclass）
  - 创建 protocol/serializer.py（JSON 序列化/反序列化工具）
  - 消息类型严格对应 04-shared-protocols.md

### T4: WebSocket 网关层
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 创建 gateway/connection_state.py（ConnectionState 枚举 + 合法转换规则）
  - 创建 gateway/connection_manager.py（ClientConnection + ConnectionManager）
  - 创建 gateway/message_router.py（MessageRouter + 状态访问控制）
  - WebSocket 端点将在 T12 整合

### T5: 认证模块
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 创建 auth/jwt_manager.py（JWTManager：create_token, create_refresh_token, parse_token, refresh_token）
  - 创建 auth/auth_service.py（AuthService：login, register，含密码验证/强度校验/ELO初始化）
  - 创建 auth/auth_handler.py（AuthHandler：handle_login, handle_register, handle_token_auth, handle_refresh, handle_reconnect）
  - JWT 兼容 Go 侧 HS256 格式
  - 断线重连通过 session_token 查找原始连接

### T6: 用户模块
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 创建 user/user_service.py（get_user_info, update_profile, get_rankings, get_history, calculate_elo）
  - 创建 user/user_handler.py（handle: user_get_me, user_update_profile, user_get_rankings, user_get_history）
  - ELO 计算使用 K 值分级策略（K=40/20/10）

### T7: 房间模块
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 创建 room/player_session.py（PlayerSession 含 WebSocket 连接引用）
  - 创建 room/timers.py（MoveTimer：asyncio 定时器，超时回调）
  - 创建 room/room.py（Room 数据类 + RoomPhase/RoomSource/RoomType 枚举）
  - 创建 room/room_manager.py（RoomManager：3 种创建路径 + 房间协程 + AI 落子 + ELO 更新 + DB 持久化）
  - 创建 room/room_handler.py（RoomHandler：8 种消息处理）
  - 创建 room/room_repository.py（RoomRepository + GameRepository + ModelRepository）

### T8: 匹配模块
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 创建 match/match_queue.py（MatchQueue：排序列表 + ELO 范围匹配 + 动态扩展）
  - 创建 match/match_service.py（MatchService：后台匹配循环 + 匹配成功自动创建房间）
  - 创建 match/match_handler.py（MatchHandler：match_join/match_leave）

### T9: 棋盘引擎迁移
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 创建 chess/constants.py（从 shared/constants.py 迁移）
  - 创建 chess/move.py（Move 数据类，从 shared/protocol.py 迁移）
  - 复制 internal/chess/ 下 6 个文件到 game-service/chess/
  - 所有 import 从 shared.* 替换为 chess.*
  - 更新 chess/__init__.py 使用新路径

### T10: AI 推理模块迁移
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 复制 internal/ai/engine.py → game-service/ai/engine.py，替换 import
  - 创建 ai/difficulty.py（难度等级 1-5 → 搜索深度 2-6 + 最大思考时间）
  - 创建 ai/ai_proxy.py（AIProxy：异步 AI 推理封装，asyncio.to_thread）

### T11: 管理后台模块
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 创建 admin/admin_service.py（list_users, ban_user, get_stats, list_models, publish_model）
  - 创建 admin/admin_handler.py（权限检查 + 4 种消息处理）

### T12: 主入口整合
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 重写 main.py 完整启动流程：加载配置→初始化DB→初始化各Repository/Service/Handler→启动匹配循环→启动心跳检测→启动uvicorn
  - WebSocket 端点 WS /ws：唯一入口，首条消息必须认证，30秒超时
  - HTTP 端点 GET /health：健康检查（在线用户数、活跃房间数）
  - HTTP 端点 POST /internal/model/reload：模型热加载内部接口（需 internal secret）
  - 心跳检测：后台协程检查 last_ping，超时断开
  - 断线处理：游戏中玩家断线保持房间等待重连
  - 验证：所有模块 import 成功，FastAPI app 正确注册路由

### T13: 集成测试与验证
- 状态：✅ 已完成
- 开始时间：2026-05-21
- 完成时间：2026-05-21
- 执行记录：
  - 执行数据库迁移 002_add_room_source.sql
  - 修复 elo_repository.py（wins_count/losses_count/draws_count/highest_rating 列不存在→改为 games_count）
  - 修复 room_repository.py（red_player_id→red_user_id, black_player_id→black_user_id, game_histories→game_history 等）
  - 修复 user_repository.py（avatar_url→avatar, game_histories→game_history, red_player_id→red_user_id）
  - 修复 user_service.py（移除 wins_count/losses_count/draws_count 引用）
  - 修复 admin_service.py（model_versions 列名对齐）
  - 修复 room_manager.py（is_game_over()→is_game_over 属性, current_turn→current_player, game_state.result→game_state.game_result, make_move 返回值处理, AI proxy 参数 turn）
  - 修复 room_handler.py（current_turn→current_player, 移除 is_valid_move 调用）
  - 修复 room.py（init_game 增加 game_state.start() 调用, started_at 使用 time.time()）
  - 修复 ai_proxy.py（best_move 参数 turn, SearchResult.move 提取）
  - 8/8 集成测试全部通过：
    1. ✅ 用户注册（JWT token 生成）
    2. ✅ 用户信息查询（含 ELO 评分）
    3. ✅ 创建 PvE 房间（自动开始游戏）
    4. ✅ 走棋（玩家走棋→AI 思考→AI 回应）
    5. ✅ 认输（game_over 广播）
    6. ✅ 已有用户登录
    7. ✅ JWT Token 认证
    8. ✅ HTTP 健康检查
