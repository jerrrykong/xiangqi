# 前端全 WS 长连接架构改造方案

> 中国象棋对战游戏 — 从 HTTP+WS 混合架构改造为全 WebSocket 长连接 C/S 架构

## 1. 改造目标

将前端从 **HTTP REST + 游戏独立 WebSocket** 的混合架构，改造为 **全局唯一 WebSocket 长连接** 架构，与 v2.0 后端统一 Game 服务对齐。

### 1.1 改造前后对比

```
┌─ 改造前 (v1.0) ──────────────────────────┐    ┌─ 改造后 (v2.0) ──────────────────────────┐
│                                          │    │                                          │
│  Vue App                                 │    │  Vue App                                 │
│    ├── Axios ──► Go Web 服务 :8080       │    │    ├── 全局 WS ──► Game 服务 :8080       │
│    │         (REST API: 认证/用户/房间)  │    │    │         (统一 WS: 全部业务)         │
│    │                                     │    │    │                                     │
│    └── WS ──► Game 服务 :8081            │    │    └── HTTP (仅静态资源)               │
│           (仅游戏对局)                    │    │                                          │
│                                          │    │                                          │
│  2个服务端点, HTTP+WS混合, 轮询依赖      │    │  1个服务端点, 纯WS通信, 服务端推送      │
└──────────────────────────────────────────┘    └──────────────────────────────────────────┘
```

### 1.2 核心改造原则

1. **单一连接**：整个应用生命周期只维护一个 WebSocket 连接
2. **统一协议**：所有消息遵循 `{ type, seq, data, timestamp }` 格式
3. **请求-响应**：通过 `seq` 序列号实现请求-响应对应
4. **事件推送**：消除所有轮询，改为服务端主动推送
5. **状态驱动**：WS 连接状态驱动 UI 状态，而非路由驱动

## 2. 新架构设计

### 2.1 通信架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Vue App                              │
│                                                             │
│  Pages ◄──► Stores ◄──► WS Client (全局唯一)              │
│                        │                                    │
│               ┌────────┼────────┐                          │
│               ▼        ▼        ▼                          │
│          Request/   Message   Event                        │
│          Response   Router    Emitter                      │
│               │        │        │                          │
│               └────────┼────────┘                          │
│                        │                                    │
│               WebSocket 长连接                              │
│               ws://host/ws                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
                  Game 服务 :8080
                  (统一 WS 端点)
```

### 2.2 WS 连接生命周期

```
App 启动
  │
  ├─ 无 token → 显示 Login/Register 页面
  │              (Login/Register 通过 WS auth_* 消息完成)
  │
  ├─ 有 token → WS 连接 → auth_token 认证
  │   │
  │   ├─ 认证成功 → AUTHENTICATED 状态 → 进入 Lobby
  │   └─ 认证失败 → 清除 token → 显示 Login
  │
  └─ 有 session_token → WS 连接 → reconnect
      │
      ├─ 重连成功 → 恢复状态 (AUTHENTICATED / IN_ROOM)
      └─ 重连失败 → auth_token 回退

WS 连接建立后:
  ┌─ AUTHENTICATED ──► 用户浏览大厅/创建房间/加入匹配
  │      │
  │      ├─ room_create / room_join ──► IN_ROOM
  │      ├─ match_join ──► MATCHMAKING
  │      │
  │      │  (user_*, room_list 等查询在此状态下进行)
  │
  ├─ IN_ROOM ──► 对局进行中
  │      │
  │      ├─ game_move / game_resign / game_draw_* ──► 仍在 IN_ROOM
  │      ├─ game_over ──► 回到 AUTHENTICATED
  │      ├─ room_leave ──► 回到 AUTHENTICATED
  │      │
  │      │  (断线重连时，reconnect + state_sync 恢复棋盘)
  │
  ├─ MATCHMAKING ──► 等待匹配
  │      │
  │      ├─ match_found ──► IN_ROOM (直接进入对局)
  │      ├─ match_leave ──► 回到 AUTHENTICATED
  │
  └─ 任意状态 ──► WS 断开 ──► 自动重连 (指数退避)
```

### 2.3 WS Client 模块设计

替代现有的 `api/` 目录（Axios HTTP 请求）和 `api/websocket.ts`（游戏 WS），统一为新的 WS Client：

```
src/ws/
├── client.ts              # WS 客户端核心 (连接/重连/心跳/消息收发)
├── request.ts             # 请求-响应封装 (seq管理/超时/Promise化)
├── router.ts              # 消息路由器 (type → handler 分发)
├── state.ts               # 连接状态管理 (状态机/状态ref)
├── handlers/              # 业务消息处理器
│   ├── auth.handler.ts    # 认证相关消息处理
│   ├── user.handler.ts    # 用户相关消息处理
│   ├── room.handler.ts    # 房间相关消息处理
│   ├── game.handler.ts    # 游戏相关消息处理
│   ├── match.handler.ts   # 匹配相关消息处理
│   └── admin.handler.ts   # 管理后台消息处理
└── types.ts               # WS 消息类型定义 (对齐 v2.0 协议)
```

### 2.4 请求-响应机制

v2.0 协议中，客户端发消息携带 `seq`，服务端响应对应 `seq`，实现请求-响应匹配：

```typescript
// ws/request.ts
class WSRequest {
  private seqCounter = 0
  private pendingRequests = new Map<number, { resolve, reject, timer }>()

  // 发送请求并等待响应
  async request(type: string, data?: any, timeout = 10000): Promise<any> {
    const seq = ++this.seqCounter
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(seq)
        reject(new Error(`Request timeout: ${type}`))
      }, timeout)
      this.pendingRequests.set(seq, { resolve, reject, timer })
      this.send({ type, seq, data })
    })
  }

  // 收到响应时匹配
  handleResponse(seq: number, data: any) {
    const pending = this.pendingRequests.get(seq)
    if (pending) {
      clearTimeout(pending.timer)
      this.pendingRequests.delete(seq)
      pending.resolve(data)
    }
  }
}
```

**使用方式**：
```typescript
// 替代 HTTP POST /auth/login
const result = await wsClient.request('auth_login', { username, password })

// 替代 HTTP GET /users/me
const profile = await wsClient.request('user_get_me', {})

// 替代 HTTP POST /rooms
const room = await wsClient.request('room_create', { room_type: 'pvp' })
```

### 2.5 消息路由机制

服务端推送消息（非请求-响应）通过消息路由器分发到各 Store：

```typescript
// ws/router.ts
class MessageRouter {
  private handlers = new Map<string, (data: any) => void>()

  register(type: string, handler: (data: any) => void) {
    this.handlers.set(type, handler)
  }

  route(message: { type: string; data: any }) {
    const handler = this.handlers.get(message.type)
    if (handler) handler(message.data)
    else console.warn('Unhandled message type:', message.type)
  }
}

// 注册路由 — 在各 Store 中
router.register('game_start', (data) => gameStore.handleGameStart(data))
router.register('game_over', (data) => gameStore.handleGameOver(data))
router.register('rating_update', (data) => authStore.handleRatingUpdate(data))
router.register('match_found', (data) => matchStore.handleMatchFound(data))
```

### 2.6 认证流程改造

**改造前**：HTTP `POST /auth/login` → 获取 JWT token → 存 localStorage → 后续 HTTP 携带 Bearer token

**改造后**：
1. 建立 WS 连接（无需 token）
2. 发送 `auth_login { username, password }`
3. 收到 `auth_result { success, token, session_token, ... }`
4. 持久化 `token` + `session_token` + `user` 到 localStorage
5. 后续页面刷新时，先发 `auth_token { token }` 或 `reconnect { session_token }` 恢复认证

**Token 刷新**：
- 发送 `auth_refresh { refresh_token }` → 收到 `auth_refresh_result { token, expires_at }`
- 无需 HTTP 拦截器，在 WS 请求响应中处理

### 2.7 房间流程改造

**改造前**：
```
HTTP createRoom → HTTP 轮询房间状态 → HTTP playerReady → HTTP 获取 WS URL → 建立 WS
```

**改造后**：
```
WS room_create → 收到 room_created → 等待 player_joined 推送
→ (PvP: 对手加入后自动 game_start; PvE: 直接 game_start)
→ 收到 game_start → 更新棋盘状态 → 开始对局
```

**关键变化**：
- 无需 `playerReady`（v2.0 房间逻辑：PvP 手动房间对手加入即开始；PvE 创建即开始）
- 无需轮询（服务端主动推送 `player_joined`, `game_start`）
- 无需单独的游戏 WS 连接（全局 WS 承载所有游戏消息）

### 2.8 匹配流程改造

**改造前**：
```
HTTP joinMatchQueue → HTTP 轮询匹配状态 → HTTP 获取结果
```

**改造后**：
```
WS match_join → 收到 match_queued (排队中)
→ 等待 match_found 推送 (匹配成功, 含 room_id, opponent, your_side)
→ 收到 game_start → 开始对局
```

### 2.9 断线重连改造

**改造前**：
- 游戏中断线 → 旧 WS 连接丢失 → 建立新游戏 WS → 发送 `reconnect { token }`

**改造后**：
- 全局 WS 断线 → 自动重连 → 发送 `auth_token { token }` 或 `reconnect { session_token, room_id }`
- 若在游戏中 → 收到 `state_sync` 恢复棋盘
- `session_token` 比 JWT token 更适合重连（JWT 有过期时间，session_token 服务端可控）

### 2.10 走棋格式改造

**改造前** (v1.0 WS 协议)：
```json
{ "type": "move", "move": { "from_col": 4, "from_row": 9, "to_col": 4, "to_row": 7 } }
```

**改造后** (v2.0 WS 协议)：
```json
{ "type": "game_move", "seq": 1, "data": { "from_pos": [9, 4], "to_pos": [7, 4] } }
```

走棋响应也变了：
- 改造前：`opponent_move { move: {from_col, from_row, to_col, to_row}, red_time, black_time }`
- 改造后：`opponent_move { from_pos, to_pos, fen, captured }` 或 `ai_move { from_pos, to_pos, fen, captured, think_time_ms }`

## 3. Store 改造设计

### 3.1 auth Store 改造

```
改造前: 依赖 authApi (HTTP) + userApi (HTTP)
改造后: 依赖 wsClient.request + 消息路由

新增:
  - sessionToken: string | null
  - connectionState: 'disconnected' | 'connecting' | 'connected' | 'error'
  - wsState: 'unauthenticated' | 'authenticated' | 'in_room' | 'matchmaking'

修改:
  - login() → wsClient.request('auth_login', { username, password })
  - register() → wsClient.request('auth_register', { username, password, nickname })
  - init() → WS 连接 + auth_token / reconnect
  - 新增 handleRatingUpdate() 处理 rating_update 推送

移除:
  - fetchCurrentUser() (不再需要 HTTP GET /users/me，信息在认证响应中)
```

### 3.2 room Store 改造

```
改造前: 依赖 roomApi (HTTP) + 轮询
改造后: 依赖 wsClient.request + 消息路由推送

新增:
  - handlePlayerJoined(data) — 服务端推送对手加入
  - handleGameStart(data) — 服务端推送游戏开始
  - handleOpponentLeft(data) — 服务端推送对手离开
  - handleRoomRemoved(data) — 服务端推送房间解散

修改:
  - createRoom() → wsClient.request('room_create', { room_type })
  - joinRoom(roomId) → wsClient.request('room_join', { room_id })
  - leaveRoom() → wsClient.request('room_leave', { room_id })
  - fetchRoomList() → wsClient.request('room_list', {})
  - 移除 fetchCurrentRoom() (不再轮询)
  - 移除 playerReady() (v2.0 无需手动准备)
  - 移除 restoreRoom() (通过 reconnect + state_sync 恢复)

移除:
  - 对 roomApi 的全部依赖
  - 所有轮询逻辑
```

### 3.3 game Store 改造

```
改造前: 依赖 wsManager (独立游戏WS)
改造后: 依赖全局 WS Client + 消息路由

新增:
  - handleMoveResult(data) — 服务端确认走棋结果
  - handleAIMove(data) — AI 走棋推送
  - handleAIThinking(data) — AI 思考中提示
  - handleStateSync(data) — 断线重连状态恢复 (格式已变)

修改:
  - sendMove() → wsClient.request('game_move', { from_pos, to_pos })
  - sendResign() → wsClient.send('game_resign')
  - sendDrawRequest() → wsClient.send('game_draw_req')
  - sendDrawAnswer(accept) → wsClient.send('game_draw_ans', { accept })
  - 移除 connect()/disconnect() (全局 WS，不需要单独连接)
  - 移除 setWebSocketCallbacks() (改为消息路由)

移除:
  - gameWsUrl, gameToken 状态 (不再需要独立 WS 连接信息)
  - 对 wsManager 的依赖
```

### 3.4 新增 match Store

```
改造前: 无独立 Store，直接调用 match API
改造后: 新增 match Store，管理匹配状态

状态:
  - isMatchmaking: boolean
  - matchPosition: number
  - estimatedWait: number

方法:
  - joinMatch() → wsClient.request('match_join', { game_type })
  - leaveMatch() → wsClient.request('match_leave')

推送处理:
  - handleMatchQueued(data) — 排队中
  - handleMatchFound(data) — 匹配成功 (含 room_id, opponent, your_side)
```

## 4. 页面流程改造

### 4.1 Login / Register 页面

**改造要点**：WS 连接建立在前，登录/注册消息在 WS 上发送

```
用户打开 Login 页面
  → 检查 WS 连接状态
  → 若未连接: 建立 WS 连接 (无认证)
  → 用户提交表单 → wsClient.request('auth_login', { username, password })
  → 收到 auth_result { success: true, ... }
  → 保存 token/session_token/user 到 localStorage
  → 跳转 Lobby
```

### 4.2 Lobby 页面

**改造要点**：所有数据通过 WS 请求获取，不再 HTTP

```
进入 Lobby
  → wsClient.request('user_get_me') → 更新用户信息
  → wsClient.request('user_get_rankings', { page: 1, page_size: 10 }) → 排行榜
  → wsClient.request('user_get_history', { page: 1, page_size: 10 }) → 对局历史
  → 创建房间: wsClient.request('room_create', { room_type })
  → PvE 对战: wsClient.request('room_create', { room_type: 'pve', difficulty: 3 })
  → 匹配: wsClient.request('match_join', { game_type: 'pvp' })
```

### 4.3 RoomList 页面

**改造要点**：消除5秒轮询，改为首次加载 + 服务端推送更新

```
进入 RoomList
  → wsClient.request('room_list') → 初始列表
  → 注册 room_list_result / player_joined / room_removed 推送 → 自动更新
```

### 4.4 GameRoom 页面

**改造要点**：大幅简化，消除1秒轮询和准备流程

```
v1.0 流程: 创建/加入 → 等待 → 轮询 → 准备 → 轮询 → 获取WS → 跳转Game
v2.0 流程: 创建/加入 → 等待 player_joined/game_start 推送 → 跳转Game

PvP: room_create → 等待 → player_joined → game_start → 跳转
PvE: room_create { pve } → 直接 game_start → 跳转
匹配: match_found → game_start → 跳转
```

**GameRoom 页面可能不再需要**：v2.0 中 PvP 手动房间对手加入即开始，无需等待双方准备。GameRoom 的"等待对手"功能可以合并到 Lobby 中作为一个浮动面板/弹窗。

### 4.5 Game 页面

**改造要点**：不再建立独立游戏 WS，使用全局 WS

```
v1.0: 进入Game → 连接游戏WS → 注册回调 → 走棋/认输/求和
v2.0: 进入Game → (WS已连接) → 注册游戏消息路由 → 走棋/认输/求和
```

**走棋交互变化**：
- 点击棋子 → 选中 → 点击目标位置 → 构建 `{ from_pos: [row, col], to_pos: [row, col] }` → 发送 `game_move`
- 服务端响应 `move_result { success, fen, move }` → 更新本地棋盘
- 对手走棋推送 `opponent_move { from_pos, to_pos, fen, captured }` → 更新本地棋盘
- AI 走棋推送 `ai_move { from_pos, to_pos, fen, captured, think_time_ms }` → 更新本地棋盘

## 5. Vite 代理配置改造

```typescript
// vite.config.ts
server: {
  proxy: {
    // 移除 /api/v1 代理 (不再需要 HTTP API)
    // 保留 /ws 代理 (WebSocket 连接)
    '/ws': {
      target: 'ws://localhost:8080',  // 指向统一 Game 服务
      ws: true,
    },
    // 可选: 保留 /health 用于健康检查
    '/health': {
      target: 'http://localhost:8080',
    },
  }
}
```

## 6. 可删除的模块

| 文件 | 原因 |
|------|------|
| `src/api/request.ts` | Axios 实例，不再需要 HTTP 请求 |
| `src/api/auth.ts` | 改为 WS 认证 |
| `src/api/user.ts` | 改为 WS 请求 |
| `src/api/room.ts` | 改为 WS 请求 |
| `src/api/match.ts` | 改为 WS 请求 |
| `src/api/websocket.ts` | 旧 WS 管理器，被新 WS Client 替代 |
| `src/types/websocket.ts` | 旧消息类型定义，被新 WS types 替代 |

## 7. 依赖变化

**移除**：
- `axios` — 不再需要 HTTP 请求库

**保留**：
- `vue`, `vue-router`, `pinia`, `element-plus`, `typescript`, `vite` — 核心框架不变
