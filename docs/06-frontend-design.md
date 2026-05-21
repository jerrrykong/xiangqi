# 前端设计文档 (v1.0 现状分析)

> 中国象棋对战游戏 — Vue 3 前端架构分析与设计

## 1. 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | ^3.5.34 | UI 框架 (Composition API) |
| Vite | ^8.0.12 | 构建工具 |
| TypeScript | ~6.0.2 | 类型系统 |
| Pinia | — | 状态管理 |
| Vue Router | — | 路由管理 |
| Element Plus | — | UI 组件库 (自动导入) |
| Axios | — | HTTP 请求 |
| 原生 WebSocket | — | 游戏实时通信 |

## 2. 目录结构

```
cmd/web/src/
├── main.ts                     # 应用入口 (Pinia + Router + ElementPlus + Auth 初始化)
├── App.vue                     # 根组件 (仅 RouterView + authStore.init)
├── auto-imports.d.ts           # 自动生成 — 全局类型声明
├── components.d.ts             # 自动生成 — 组件类型声明
├── api/                        # API 通信层
│   ├── request.ts              # Axios 实例 (baseURL=/api/v1, token拦截, 401自动刷新)
│   ├── auth.ts                 # 认证 API (register/login/logout/refreshToken)
│   ├── user.ts                 # 用户 API (getCurrentUser/updateProfile/getRankings/getHistory)
│   ├── room.ts                 # 房间 API (createRoom/getMyRoom/getRoomList/getRoom/joinRoom/playerReady/leaveRoom/deleteRoom)
│   ├── match.ts                # 匹配 API (joinMatchQueue/leaveMatchQueue/getMatchStatus/joinPveQueue)
│   └── websocket.ts            # WebSocket 单例管理器 (连接/重连/心跳/消息路由)
├── components/
│   └── ChessBoard.vue          # 棋盘组件 (SVG + 绝对定位 div, 棋子渲染/选中/高亮/将军提示)
├── composables/                # (空目录，预留)
├── pages/                      # 页面组件
│   ├── Login.vue               # 登录页
│   ├── Register.vue            # 注册页
│   ├── Lobby.vue               # 游戏大厅 (用户信息+排行榜+对局历史)
│   ├── RoomList.vue            # 房间列表页 (自动刷新5s)
│   ├── GameRoom.vue            # 游戏房间 (等待/准备/轮询1s)
│   └── Game.vue                # 对局页面 (棋盘+计时+认输/求和)
├── router/
│   └── index.ts                # 路由定义 + 守卫 (7条路由, 鉴权守卫)
├── stores/                     # Pinia 状态管理
│   ├── auth.ts                 # 认证 Store (user/token/isLoading, localStorage持久化)
│   ├── game.ts                 # 游戏 Store (棋盘/计时/WS回调/走棋/认输/求和)
│   └── room.ts                 # 房间 Store (房间列表/当前房间/创建/加入/准备/离开)
├── styles/
│   └── main.css                # 全局样式 (木纹主题CSS变量/自定义滚动条)
├── types/                      # TypeScript 类型定义
│   ├── api.ts                  # HTTP API 响应类型 (ApiResponse/UserProfile/RoomListItem/...)
│   ├── chess.ts                # 象棋领域类型 (棋子编码/Position/Move/初始棋盘)
│   └── websocket.ts            # WebSocket 消息类型 (MsgType/ClientMessage/ServerMessage/ErrorCode)
└── utils/                      # (空目录，预留)
```

## 3. 架构分析

### 3.1 通信架构 (v1.0 现状)

前端当前采用 **HTTP REST + 游戏专属 WebSocket** 的混合通信架构：

```
┌─────────────────────────────────────────────────┐
│                   Vue App                       │
├─────────────────────────────────────────────────┤
│  Pages ──► Stores ──► API Layer                 │
│                          │                      │
│              ┌───────────┴───────────┐          │
│              ▼                       ▼          │
│         Axios (HTTP)         WebSocket (仅游戏)  │
│         /api/v1/*            /ws?token=xxx      │
│              │                       │          │
├──────────────┼───────────────────────┼──────────┤
│              ▼                       ▼          │
│         Go Web 服务 :8080    Game 服务 :8081     │
│         (REST API)          (游戏WS)            │
└─────────────────────────────────────────────────┘
```

**HTTP REST 请求** — 用于非实时业务：
- 认证：`POST /auth/register`, `/auth/login`, `/auth/refresh`
- 用户：`GET /users/me`, `PUT /users/me`, `GET /users/rankings`, `GET /users/:id/history`
- 房间：`POST /rooms`, `GET /rooms`, `GET /rooms/:id`, `POST /rooms/:id/join`, `/ready`, `/leave`, `DELETE /rooms/:id`
- 匹配：`POST /match/queue`, `DELETE /match/queue`, `GET /match/status`, `POST /match/pve`

**WebSocket 连接** — 仅用于游戏对局实时通信：
- 连接时机：双方准备后，获取 `game_ws_url` + `game_token`，在 Game 页面建立独立 WS
- 认证方式：URL 参数 `?token=xxx&user_id=xxx`
- 消息格式：扁平 JSON `{ type, move/red_time/black_time/... }`
- 消息类型：`move`, `resign`, `draw_req`, `draw_ans`, `ping`, `reconnect` (C→S)；`state_sync`, `opponent_move`, `game_start`, `game_over`, `check`, `draw_notify`, `error`, `pong` (S→C)

### 3.2 状态管理架构

```
┌──────────────────────────────────────────────┐
│ auth Store (认证)                             │
│   user / token / isLoading                   │
│   localStorage 持久化                        │
│   依赖: authApi, userApi                     │
├──────────────────────────────────────────────┤
│ room Store (房间)                             │
│   roomList / currentRoom / isLoading         │
│   currentRoom: { roomId, status, yourSide,   │
│     opponent, redReady, blackReady,          │
│     gameStarted, gameWsUrl, gameToken }      │
│   依赖: roomApi, authStore                   │
├──────────────────────────────────────────────┤
│ game Store (游戏)                             │
│   board / currentTurn / redTime / blackTime  │
│   yourColor / isGameStarted / isGameOver     │
│   selectedPosition / validMoves / lastMove   │
│   依赖: wsManager, authStore                 │
└──────────────────────────────────────────────┘
```

### 3.3 页面流转

```
Login ──► Lobby ──► RoomList ──► GameRoom ──► Game
Register─┘   │                                 │
             └── 创建房间 ──► GameRoom ──► Game

路由守卫: 未登录 → /login; 已登录 → /lobby
```

| 路径 | 组件 | 认证 | 关键逻辑 |
|------|------|------|---------|
| `/login` | Login.vue | 否 | 表单验证 → authStore.login → redirect |
| `/register` | Register.vue | 否 | 表单验证 → authApi.register → /login |
| `/lobby` | Lobby.vue | 是 | 加载用户/排行/历史; 检查已入房间跳转 |
| `/rooms` | RoomList.vue | 是 | 每5秒刷新; getRoom获取详情 |
| `/room/:id` | GameRoom.vue | 是 | 每1秒轮询; restoreRoom/joinRoom; 准备→获取WS信息 |
| `/game/:id` | Game.vue | 是 | 连接游戏WS; 棋盘交互; 认输/求和 |

### 3.4 轮询问题

当前存在两处 HTTP 轮询：

1. **RoomList.vue** — 每 5 秒 `fetchRoomList` 刷新房间列表
2. **GameRoom.vue** — 每 1 秒 `fetchCurrentRoom` 轮询房间状态（等待对手加入/准备）

这些轮询在改造为全 WS 架构后应全部消除，改为服务端主动推送。

## 4. 关键模块详解

### 4.1 API 层 (HTTP)

**request.ts** — Axios 实例配置：
- `baseURL: /api/v1`，10秒超时
- 请求拦截器：从 localStorage 读取 token，添加 `Authorization: Bearer xxx`
- 响应拦截器：401 + code=2002 自动刷新 token；刷新失败跳转 /login

**auth.ts** — 认证 API：
- `register(data)` → `POST /auth/register` → UserProfile
- `login(data)` → `POST /auth/login` → LoginResponse (自动保存 token)
- `logout()` → 清除 localStorage
- `refreshToken()` → `POST /auth/refresh` → LoginResponse

**user.ts** — 用户 API：
- `getCurrentUser()` → `GET /users/me`
- `updateProfile(data)` → `PUT /users/me`
- `getRankings(page, pageSize)` → `GET /users/rankings`
- `getHistory(page, pageSize, type)` → `GET /users/:id/history` (先获取 userId)

**room.ts** — 房间 API：
- `createRoom()` → `POST /rooms`
- `getMyRoom()` → `GET /rooms/me`
- `getRoomList(page, pageSize)` → `GET /rooms`
- `getRoom(roomId)` → `GET /rooms/:id` → RoomDetail
- `joinRoom(roomId)` → `POST /rooms/:id/join`
- `playerReady(roomId)` → `POST /rooms/:id/ready`
- `leaveRoom(roomId)` → `POST /rooms/:id/leave`
- `deleteRoom(roomId)` → `DELETE /rooms/:id`

**match.ts** — 匹配 API：
- `joinMatchQueue()` → `POST /match/queue`
- `leaveMatchQueue()` → `DELETE /match/queue`
- `getMatchStatus()` → `GET /match/status`
- `joinPveQueue(difficulty)` → `POST /match/pve`

### 4.2 WebSocket 管理器 (websocket.ts)

**WebSocketManager** 类 — 单例模式：
- **连接方式**：
  - `connect(url, token)` — 自动拼接 `?token=xxx`
  - `connectRaw(fullUrl, token)` — 使用完整 URL (游戏WS已含参数)
- **状态**：`isConnected` (ref), `connectionState` (shallowRef: disconnected/connecting/connected/error)
- **重连**：指数退避，最大5次，初始1秒
- **心跳**：每30秒发送 `{ type: 'ping', time: Date.now() }`
- **消息路由**：按 `message.type` switch 分发到8个回调
- **不可重试错误码**：3001(房间满), 3002(房间不存在), 4003 → 停止重连并断开

### 4.3 棋盘引擎 (chess.ts)

**棋子编码**：`color * 10 + piece_type` (与后端 `shared/constants.go` 一致)
- 红(0): King=0, Advisor=1, Bishop=2, Knight=3, Rook=4, Cannon=5, Pawn=6
- 黑(1): King=10, Advisor=11, Bishop=12, Knight=13, Rook=14, Cannon=15, Pawn=16
- Empty=-1

**棋盘**：10行 × 9列，`board[row][col]` 存储棋子编码

**工具函数**：`getPieceColor(piece)`, `isRedPiece(piece)`, `isBlackPiece(piece)`

**类型**：`Position {col, row}`, `Move {from_col, from_row, to_col, to_row}`

### 4.4 棋盘组件 (ChessBoard.vue)

**渲染**：SVG 线条 + 绝对定位 div 棋子
- SVG：棋盘线、九宫对角线、楚河汉界、炮/兵标记点、选中/最后一步/将军高亮
- Div：棋子圆形，红色/黑色棋子样式
- 坐标：`getX(col) = padding + col * 55`, `getY(row) = padding + row * 55`

**交互**：点击棋子 → `piece-click` emit → 选中 → 点击位置 → `position-click` emit → 走棋

## 5. 现状问题与改造要点

### 5.1 与 v2.0 后端的差距

| 项目 | v1.0 前端现状 | v2.0 后端要求 |
|------|-------------|-------------|
| 通信方式 | HTTP REST + 游戏独立 WS | 全 WS 长连接 |
| WS 连接数 | 每局游戏一个独立 WS | 全生命周期单一 WS |
| WS 入口 | `/ws?token=xxx` (游戏服务 :8081) | `/ws` (统一服务 :8080) |
| 认证流程 | HTTP `/auth/login` → token → WS | WS `auth_login` → session_token |
| 消息格式 | 扁平 `{ type, move, ... }` | 统一 `{ type, seq, data, timestamp }` |
| 消息类型 | 6种 C→S + 8种 S→C | 22种 C→S + 28种 S→C |
| 走棋格式 | `{ from_col, from_row, to_col, to_row }` | `{ from_pos: [row, col], to_pos: [row, col] }` |
| 房间准备 | HTTP `/rooms/:id/ready` + 轮询 | WS `room_join` → 自动开始 (无需准备) |
| 断线重连 | WS `reconnect { token }` | WS `reconnect { session_token, room_id }` |
| 匹配 | HTTP REST API | WS `match_join` / `match_leave` |
| 排行/历史 | HTTP GET | WS `user_get_rankings` / `user_get_history` |
| AI 对局 | 无直接支持 | WS `room_create { room_type: "pve" }` → 直接开始 |
| ELO 更新 | 无推送 | WS `rating_update` 主动推送 |

### 5.2 需要彻底改造的模块

1. **API 层** — 全部 HTTP 请求改为 WS 消息，删除 Axios 依赖
2. **WebSocket 管理器** — 从"游戏专用"改为"全局唯一长连接"，支持完整消息路由
3. **认证流程** — 从 HTTP 登录改为 WS 认证，引入 session_token 持久化
4. **房间管理** — 从 HTTP + 轮询改为 WS 消息 + 推送
5. **匹配流程** — 从 HTTP REST 改为 WS 消息
6. **类型定义** — 对齐 v2.0 协议的完整消息类型
7. **页面流程** — 简化准备阶段，支持 AI 对局、匹配等新流程
