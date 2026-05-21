# 前端全 WS 长连接改造 — 任务拆解

> 中国象棋对战游戏 — 前端改造任务拆解与详细执行计划

## 任务总览

| ID | 任务 | 依赖 | 预估工时 |
|----|------|------|---------|
| F1 | WS 类型定义 | — | 0.5h |
| F2 | WS Client 核心模块 | F1 | 1h |
| F3 | WS 请求-响应封装 | F2 | 0.5h |
| F4 | WS 消息路由器 | F2 | 0.5h |
| F5 | 认证模块改造 | F2, F3, F4 | 1.5h |
| F6 | 用户模块改造 | F3, F4 | 1h |
| F7 | 房间模块改造 | F3, F4 | 1.5h |
| F8 | 游戏模块改造 | F3, F4 | 2h |
| F9 | 匹配模块改造 | F3, F4 | 1h |
| F10 | 路由与守卫改造 | F5 | 0.5h |
| F11 | 页面改造 | F5~F9 | 3h |
| F12 | 清理与配置 | F11 | 0.5h |
| F13 | 端到端验证 | F12 | 2h |

**执行顺序**：

```
F1 → F2 → F3 + F4 (并行) → F5 + F6 + F7 + F8 + F9 (并行) → F10 → F11 → F12 → F13
```

---

## F1: WS 类型定义

**目标**：创建与 v2.0 后端协议完全对齐的 TypeScript 类型定义

**文件**：`src/ws/types.ts` (新建)

**详细内容**：

### 1. 统一消息格式

```typescript
// 基础消息结构 (对齐 protocol/message.py)
export interface WSMessage {
  type: string
  seq: number
  data: Record<string, any>
  timestamp: number
}
```

### 2. 客户端→服务端消息类型常量

对齐 `game-service/protocol/inbound.py`：

```typescript
export const WSMsgType = {
  // 认证
  AUTH_LOGIN: 'auth_login',
  AUTH_REGISTER: 'auth_register',
  AUTH_TOKEN: 'auth_token',
  AUTH_REFRESH: 'auth_refresh',
  RECONNECT: 'reconnect',
  // 用户
  USER_GET_ME: 'user_get_me',
  USER_UPDATE_PROFILE: 'user_update_profile',
  USER_GET_RANKINGS: 'user_get_rankings',
  USER_GET_HISTORY: 'user_get_history',
  // 房间
  ROOM_CREATE: 'room_create',
  ROOM_LIST: 'room_list',
  ROOM_JOIN: 'room_join',
  ROOM_LEAVE: 'room_leave',
  // 游戏
  GAME_MOVE: 'game_move',
  GAME_RESIGN: 'game_resign',
  GAME_DRAW_REQ: 'game_draw_req',
  GAME_DRAW_ANS: 'game_draw_ans',
  // 匹配
  MATCH_JOIN: 'match_join',
  MATCH_LEAVE: 'match_leave',
  // 管理
  ADMIN_USERS: 'admin_users',
  ADMIN_BAN: 'admin_ban',
  ADMIN_STATS: 'admin_stats',
  ADMIN_MODELS: 'admin_models',
  // 通用
  PING: 'ping',
} as const
```

### 3. 服务端→客户端消息类型常量

对齐 `game-service/protocol/outbound.py`：

```typescript
export const WSRespType = {
  // 认证
  AUTH_RESULT: 'auth_result',
  AUTH_REGISTER_RESULT: 'auth_register_result',
  AUTH_TOKEN_RESULT: 'auth_token_result',
  AUTH_REFRESH_RESULT: 'auth_refresh_result',
  RECONNECT_RESULT: 'reconnect_result',
  // 用户
  USER_ME: 'user_me',
  USER_PROFILE_UPDATED: 'user_profile_updated',
  USER_RANKINGS: 'user_rankings',
  USER_HISTORY: 'user_history',
  RATING_UPDATE: 'rating_update',
  // 房间
  ROOM_CREATED: 'room_created',
  ROOM_LIST_RESULT: 'room_list_result',
  ROOM_JOINED: 'room_joined',
  ROOM_LEFT: 'room_left',
  ROOM_REMOVED: 'room_removed',
  PLAYER_JOINED: 'player_joined',
  PLAYER_LEFT: 'player_left',
  // 游戏
  GAME_START: 'game_start',
  MOVE_RESULT: 'move_result',
  OPPONENT_MOVE: 'opponent_move',
  AI_THINKING: 'ai_thinking',
  AI_MOVE: 'ai_move',
  GAME_OVER: 'game_over',
  DRAW_REQUEST: 'draw_request',
  DRAW_RESULT: 'draw_result',
  // 匹配
  MATCH_QUEUED: 'match_queued',
  MATCH_LEFT: 'match_left',
  MATCH_FOUND: 'match_found',
  // 管理
  ADMIN_USERS_RESULT: 'admin_users_result',
  ADMIN_BAN_RESULT: 'admin_ban_result',
  ADMIN_STATS_RESULT: 'admin_stats_result',
  ADMIN_MODELS_RESULT: 'admin_models_result',
  // 状态同步
  STATE_SYNC: 'state_sync',
  // 通用
  PONG: 'pong',
  ERROR: 'error',
} as const
```

### 4. 各消息 data 接口

对齐 `game-service/protocol/outbound.py` 中的 dataclass：

```typescript
// ---- 认证响应 ----
export interface AuthResultData {
  success: boolean
  user_id?: number
  username?: string
  nickname?: string
  rating?: number
  games_count?: number
  is_admin?: boolean
  token?: string
  refresh_token?: string
  expires_at?: string
  session_token?: string
  error?: string  // 失败时
}

export interface AuthTokenResultData {
  success: boolean
  user_id?: number
  username?: string
  nickname?: string
  rating?: number
  games_count?: number
  is_admin?: boolean
  session_token?: string
  error?: string
}

export interface ReconnectResultData {
  success: boolean
  user_id?: number
  username?: string
  session_token?: string
  state?: string  // 'authenticated' | 'in_room' | 'matchmaking'
  room_id?: string
  error?: string
}

// ---- 用户响应 ----
export interface UserMeData {
  id: number
  username: string
  nickname: string
  avatar: string
  rating: number
  games_count: number
  is_admin: boolean
}

export interface UserRankingsData {
  rankings: Array<{
    user_id: number
    username: string
    nickname: string
    rating: number
    games_count: number
  }>
  total: number
  page: number
  page_size: number
}

export interface UserHistoryData {
  games: Array<{
    game_id: string
    result: string
    my_side: string
    opponent: { user_id: number; username: string; rating: number }
    rating_change: number
    total_moves: number
    played_at: string
  }>
  total: number
  page: number
  page_size: number
}

export interface RatingUpdateData {
  rating: number
  change: number
  games_count: number
}

// ---- 房间响应 ----
export interface RoomCreatedData {
  room_id: string
  room_type: string
  difficulty: number
}

export interface RoomListResultData {
  rooms: Array<{
    room_id: string
    room_type: string
    phase: string
    red_player?: { user_id: number; username: string; rating: number }
    black_player?: { user_id: number; username: string; rating: number }
    created_at: string
  }>
}

export interface RoomJoinedData {
  room_id: string
  room_type: string
  players: Array<{
    user_id: number
    username: string
    nickname: string
    side: string
    rating: number
  }>
}

export interface PlayerJoinedData {
  user_id: number
  username: string
  nickname: string
  side: string
  rating: number
}

// ---- 游戏响应 ----
export interface GameStartData {
  room_id: string
  red_player: { user_id: number; username: string; rating: number }
  black_player: { user_id: number; username: string; rating: number }
  initial_time: number
  increment: number
  fen: string
}

export interface MoveResultData {
  success: boolean
  fen: string
  move?: { from_pos: number[]; to_pos: number[] }
  message: string
}

export interface OpponentMoveData {
  from_pos: number[]   // [row, col]
  to_pos: number[]     // [row, col]
  fen: string
  captured?: { piece: number; pos: number[] }
}

export interface AIMoveData {
  from_pos: number[]
  to_pos: number[]
  fen: string
  captured?: { piece: number; pos: number[] }
  think_time_ms: number
}

export interface GameOverData {
  room_id: string
  winner: string  // 'red' | 'black' | 'draw'
  reason: string  // 'checkmate' | 'resign' | 'timeout' | 'draw' | 'disconnect'
  red_rating_change: number
  black_rating_change: number
}

export interface StateSyncData {
  room_id: string
  room_type: string
  phase: string
  fen: string
  your_side: string
  red_player?: { user_id: number; username: string; rating: number }
  black_player?: { user_id: number; username: string; rating: number }
  red_remaining_time: number
  black_remaining_time: number
  moves: Array<{ from_pos: number[]; to_pos: number[] }>
}

// ---- 匹配响应 ----
export interface MatchQueuedData {
  position: number
  estimated_wait: number
}

export interface MatchFoundData {
  room_id: string
  opponent: { user_id: number; username: string; rating: number }
  your_side: string
}

// ---- 错误 ----
export interface ErrorData {
  code: number
  message: string
}
```

### 5. 连接状态枚举

对齐 `gateway/connection_state.py`：

```typescript
export type WSConnectionState = 'disconnected' | 'connecting' | 'connected'
export type WSAuthState = 'unauthenticated' | 'authenticated' | 'in_room' | 'matchmaking'
```

**删除**：旧 `src/types/websocket.ts` 中的 MsgType, ClientMessage, ServerMessage 等全部定义

---

## F2: WS Client 核心模块

**目标**：实现全局唯一的 WebSocket 客户端，管理连接生命周期

**文件**：`src/ws/client.ts` (新建)

**详细内容**：

```typescript
class WSClient {
  // === 连接管理 ===
  private ws: WebSocket | null = null
  private url: string = ''   // 如 ws://localhost:8080/ws

  // === 状态 ===
  public connectionState = ref<WSConnectionState>('disconnected')
  public authState = ref<WSAuthState>('unauthenticated')

  // === 重连 ===
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private baseReconnectDelay = 1000
  private shouldReconnect = true

  // === 心跳 ===
  private heartbeatInterval: number | null = null
  private heartbeatTimeout = 30000  // 30s

  // === 依赖模块 ===
  private requestManager: WSRequestManager  // F3
  private messageRouter: MessageRouter      // F4

  // === 方法 ===

  connect(url: string): void
    // 建立 WebSocket 连接
    // onopen: connectionState = 'connected', 启动心跳
    // onmessage: 解析 JSON → 区分请求响应(seq匹配) vs 推送消息(路由分发)
    // onclose: connectionState = 'disconnected', 尝试重连
    // onerror: connectionState = 'disconnected'

  disconnect(): void
    // 主动断开, shouldReconnect = false

  send(message: { type: string; seq: number; data?: any }): void
    // 序列化 JSON 发送

  // === 心跳 ===
  private startHeartbeat(): void
    // 每30s发送 { type: 'ping', seq: 0, data: {} }

  private stopHeartbeat(): void

  // === 重连 ===
  private attemptReconnect(): void
    // 指数退避: delay = base * 2^(attempt-1), 最大10次
    // 重连后自动尝试 auth_token 或 reconnect 恢复认证
}

export const wsClient = new WSClient()
```

**关键设计**：
- 单例导出，全局唯一
- 连接 URL 固定为 `/ws`，通过 Vite 代理转发到 `ws://localhost:8080/ws`
- onmessage 中根据 seq 是否在 pendingRequests 中判断是响应还是推送
- 重连后自动恢复认证状态

---

## F3: WS 请求-响应封装

**目标**：将 WS 消息封装为 Promise 风格的请求-响应

**文件**：`src/ws/request.ts` (新建)

**详细内容**：

```typescript
class WSRequestManager {
  private seqCounter = 0
  private pendingRequests = new Map<number, {
    resolve: (data: any) => void
    reject: (error: Error) => void
    timer: number
  }>()

  // 发送请求并等待响应
  async request(type: string, data: Record<string, any> = {}, timeout = 10000): Promise<any> {
    const seq = ++this.seqCounter
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => {
        this.pendingRequests.delete(seq)
        reject(new WSTimeoutError(type, timeout))
      }, timeout)

      this.pendingRequests.set(seq, { resolve, reject, timer })
      wsClient.send({ type, seq, data })
    })
  }

  // 处理响应 (由 WSClient.onmessage 调用)
  handleResponse(seq: number, data: any): boolean {
    const pending = this.pendingRequests.get(seq)
    if (!pending) return false  // 不是请求响应
    clearTimeout(pending.timer)
    this.pendingRequests.delete(seq)

    // 检查是否是错误响应
    if (data?.code && data?.code !== 0 && data?.message) {
      pending.reject(new WSError(data.code, data.message))
    } else {
      pending.resolve(data)
    }
    return true
  }

  // 清理所有挂起请求 (断线时)
  clearAll(reason: string): void {
    for (const [seq, pending] of this.pendingRequests) {
      clearTimeout(pending.timer)
      pending.reject(new Error(reason))
    }
    this.pendingRequests.clear()
  }
}

// 自定义错误
class WSTimeoutError extends Error { ... }
class WSError extends Error { code: number; ... }
```

---

## F4: WS 消息路由器

**目标**：将服务端推送消息分发到对应的处理函数

**文件**：`src/ws/router.ts` (新建)

**详细内容**：

```typescript
type MessageHandler = (data: any) => void

class MessageRouter {
  private handlers = new Map<string, MessageHandler[]>()

  // 注册处理器
  on(type: string, handler: MessageHandler): void {
    const existing = this.handlers.get(type) || []
    existing.push(handler)
    this.handlers.set(type, existing)
  }

  // 移除处理器
  off(type: string, handler: MessageHandler): void {
    const existing = this.handlers.get(type)
    if (existing) {
      this.handlers.set(type, existing.filter(h => h !== handler))
    }
  }

  // 路由消息
  route(type: string, data: any): void {
    const handlers = this.handlers.get(type)
    if (handlers) {
      handlers.forEach(h => h(data))
    } else {
      console.warn(`[WS Router] Unhandled message type: ${type}`)
    }
  }
}

export const messageRouter = new MessageRouter()
```

---

## F5: 认证模块改造

**目标**：将认证流程从 HTTP 改为 WS，支持 session_token 持久化和断线重连

**涉及文件**：
- `src/stores/auth.ts` — 重大改造
- `src/ws/handlers/auth.handler.ts` — 新建
- `src/main.ts` — 修改初始化逻辑
- `src/App.vue` — 修改初始化逻辑

### 5.1 auth Store 改造

**修改 `src/stores/auth.ts`**：

```typescript
// 新增状态
const sessionToken = ref<string | null>(localStorage.getItem('session_token'))
const connectionState = ref<WSConnectionState>('disconnected')
const authState = ref<WSAuthState>('unauthenticated')

// 修改 init()
async function init() {
  // 1. 恢复用户信息
  restoreUser()

  // 2. 建立 WS 连接
  await wsClient.connect('/ws')  // 通过 Vite 代理

  // 3. 认证
  if (sessionToken.value) {
    // 优先尝试 session_token 重连
    try {
      const result = await wsClient.request('reconnect', {
        session_token: sessionToken.value,
        room_id: currentRoomId,  // 从 room store 获取
      })
      if (result.success) {
        authState.value = mapState(result.state)
        sessionToken.value = result.session_token
        // ...
        return
      }
    } catch { /* fallback */ }
  }

  if (token.value) {
    // 回退到 JWT token 认证
    try {
      const result = await wsClient.request('auth_token', { token: token.value })
      if (result.success) {
        sessionToken.value = result.session_token
        authState.value = 'authenticated'
        // ...
        return
      }
    } catch { /* fallback */ }
  }

  // 无有效凭证，清除状态
  logout()
}

// 修改 login()
async function login(username: string, password: string) {
  const result = await wsClient.request('auth_login', { username, password })
  if (!result.success) throw new Error(result.error || 'Login failed')

  token.value = result.token
  sessionToken.value = result.session_token
  user.value = {
    user_id: result.user_id,
    username: result.username,
    nickname: result.nickname,
    rating: result.rating,
    games_count: result.games_count,
  }
  localStorage.setItem('token', result.token)
  localStorage.setItem('session_token', result.session_token)
  localStorage.setItem('user', JSON.stringify(user.value))
  localStorage.setItem('refresh_token', result.refresh_token)
  authState.value = 'authenticated'
}

// 修改 register()
async function register(username: string, password: string, nickname?: string) {
  const result = await wsClient.request('auth_register', { username, password, nickname })
  if (!result.success) throw new Error(result.error || 'Register failed')

  token.value = result.token
  sessionToken.value = result.session_token
  // ... 同 login 的存储逻辑
  authState.value = 'authenticated'
}

// 修改 logout()
function logout() {
  wsClient.send({ type: 'auth_logout', seq: 0, data: {} })  // 可选：通知服务端
  wsClient.disconnect()
  user.value = null
  token.value = null
  sessionToken.value = null
  authState.value = 'unauthenticated'
  localStorage.removeItem('token')
  localStorage.removeItem('session_token')
  localStorage.removeItem('user')
  localStorage.removeItem('refresh_token')
}

// 新增: 处理 rating_update 推送
function handleRatingUpdate(data: RatingUpdateData) {
  if (user.value) {
    user.value.rating = data.rating
    user.value.games_count = data.games_count
    localStorage.setItem('user', JSON.stringify(user.value))
  }
}
```

### 5.2 auth.handler.ts

```typescript
// src/ws/handlers/auth.handler.ts
export function registerAuthHandlers() {
  messageRouter.on(WSRespType.AUTH_RESULT, (data) => authStore.handleAuthResult(data))
  messageRouter.on(WSRespType.AUTH_REGISTER_RESULT, (data) => authStore.handleAuthResult(data))
  messageRouter.on(WSRespType.AUTH_TOKEN_RESULT, (data) => authStore.handleAuthTokenResult(data))
  messageRouter.on(WSRespType.RATING_UPDATE, (data) => authStore.handleRatingUpdate(data))
  messageRouter.on(WSRespType.RECONNECT_RESULT, (data) => authStore.handleReconnectResult(data))
  messageRouter.on(WSRespType.ERROR, (data) => authStore.handleError(data))
}
```

### 5.3 main.ts / App.vue 改造

```typescript
// main.ts — 移除 Element Plus 样式导入之外的 HTTP 相关初始化
// App.vue — init() 中建立 WS 连接 + 认证，而非仅恢复 localStorage
```

---

## F6: 用户模块改造

**目标**：将用户相关 HTTP 请求改为 WS 请求

**涉及文件**：
- `src/stores/auth.ts` — 补充用户查询方法
- `src/ws/handlers/user.handler.ts` — 新建
- 删除 `src/api/user.ts`

### 6.1 用户请求方法

在 auth Store 或独立的 user Store 中添加：

```typescript
// 获取当前用户
async function getMe() {
  return await wsClient.request('user_get_me')
}

// 更新资料
async function updateProfile(data: { nickname?: string; avatar?: string }) {
  return await wsClient.request('user_update_profile', data)
}

// 排行榜
async function getRankings(page = 1, pageSize = 20) {
  return await wsClient.request('user_get_rankings', { page, page_size: pageSize })
}

// 对局历史
async function getHistory(page = 1, pageSize = 20, gameType?: string) {
  return await wsClient.request('user_get_history', { page, page_size: pageSize, game_type: gameType })
}
```

### 6.2 user.handler.ts

```typescript
export function registerUserHandlers() {
  messageRouter.on(WSRespType.USER_ME, (data) => authStore.updateUser(data))
  messageRouter.on(WSRespType.USER_PROFILE_UPDATED, (data) => authStore.updateUser(data))
  messageRouter.on(WSRespType.RATING_UPDATE, (data) => authStore.handleRatingUpdate(data))
}
```

---

## F7: 房间模块改造

**目标**：将房间管理从 HTTP+轮询改为 WS 请求+推送

**涉及文件**：
- `src/stores/room.ts` — 重大改造
- `src/ws/handlers/room.handler.ts` — 新建
- 删除 `src/api/room.ts`

### 7.1 room Store 改造

```typescript
// 修改状态
const currentRoom = ref<{
  roomId: string
  roomType: string    // 新增: pvp/pve
  phase: string       // waiting/playing/finished (替代 status)
  yourSide: 'red' | 'black'
  opponent?: { userId: number; username: string; rating: number }
  redPlayer?: { userId: number; username: string; rating: number }  // 新增
  blackPlayer?: { userId: number; username: string; rating: number } // 新增
} | null>(null)

// 移除: redReady, blackReady, gameStarted, gameWsUrl, gameToken

// 修改方法
async function createRoom(roomType: string = 'pvp', difficulty: number = 3) {
  const result = await wsClient.request('room_create', { room_type: roomType, difficulty })
  currentRoom.value = {
    roomId: result.room_id,
    roomType: result.room_type,
    phase: 'waiting',
    yourSide: 'red',
  }
  return result
}

async function joinRoom(roomId: string) {
  const result = await wsClient.request('room_join', { room_id: roomId })
  currentRoom.value = {
    roomId: result.room_id,
    roomType: result.room_type,
    phase: 'playing',  // PvP 手动房间加入即开始
    yourSide: determineSide(result.players),
    opponent: findOpponent(result.players),
  }
  return result
}

async function leaveRoom() {
  if (!currentRoom.value) return
  await wsClient.request('room_leave', { room_id: currentRoom.value.roomId })
  currentRoom.value = null
}

async function fetchRoomList() {
  const result = await wsClient.request('room_list', {})
  roomList.value = result.rooms || []
  return result
}

// 新增推送处理
function handlePlayerJoined(data: PlayerJoinedData) {
  if (!currentRoom.value) return
  currentRoom.value.opponent = {
    userId: data.user_id,
    username: data.username,
    rating: data.rating,
  }
}

function handleGameStart(data: GameStartData) {
  // 转交给 game Store
  gameStore.handleGameStart(data)
  if (currentRoom.value) {
    currentRoom.value.phase = 'playing'
  }
}

function handleRoomRemoved() {
  currentRoom.value = null
}

// 移除方法
// - fetchCurrentRoom()  (不再轮询)
// - playerReady()       (v2.0 无准备阶段)
// - restoreRoom()       (通过 reconnect 恢复)
// - deleteRoom()        (v2.0 房主离开即解散)
```

### 7.2 room.handler.ts

```typescript
export function registerRoomHandlers() {
  messageRouter.on(WSRespType.PLAYER_JOINED, (data) => roomStore.handlePlayerJoined(data))
  messageRouter.on(WSRespType.PLAYER_LEFT, (data) => roomStore.handlePlayerLeft(data))
  messageRouter.on(WSRespType.ROOM_REMOVED, () => roomStore.handleRoomRemoved())
  messageRouter.on(WSRespType.GAME_START, (data) => {
    roomStore.handleGameStart(data)
    gameStore.handleGameStart(data)
  })
}
```

---

## F8: 游戏模块改造

**目标**：将游戏对局从独立 WS 连接改为全局 WS 消息，对齐新走棋格式

**涉及文件**：
- `src/stores/game.ts` — 重大改造
- `src/ws/handlers/game.handler.ts` — 新建
- `src/types/chess.ts` — 修改 Move 类型/走棋格式

### 8.1 走棋格式改造

**修改 `src/types/chess.ts`**：

```typescript
// Move 类型增加 from_pos / to_pos 格式支持
export interface Move {
  // 原始格式 (内部使用)
  from_col: number
  from_row: number
  to_col: number
  to_row: number
}

// 新增: 与 v2.0 协议兼容的格式转换
export function moveToPos(move: Move): { from_pos: number[]; to_pos: number[] } {
  return {
    from_pos: [move.from_row, move.from_col],
    to_pos: [move.to_row, move.to_col],
  }
}

export function posToMove(fromPos: number[], toPos: number[]): Move {
  return {
    from_row: fromPos[0], from_col: fromPos[1],
    to_row: toPos[0], to_col: toPos[1],
  }
}
```

### 8.2 game Store 改造

```typescript
// 移除状态
// - gameWsUrl, gameToken (不再需要独立 WS 连接信息)

// 修改方法
function sendMove(move: Move) {
  const { from_pos, to_pos } = moveToPos(move)
  wsClient.request('game_move', { from_pos, to_pos })
    .then((result) => {
      if (result.success) {
        // 更新棋盘 (使用 FEN 或本地计算)
        board.value[move.to_row][move.to_col] = board.value[move.from_row][move.from_col]
        board.value[move.from_row][move.from_col] = -1
        lastMove.value = move
        currentTurn.value = currentTurn.value === 0 ? 1 : 0
      }
    })
    .catch((err) => {
      ElMessage.error(`走棋失败: ${err.message}`)
    })

  // 注意: 不再本地乐观更新，等服务端 move_result 确认后再更新
  // 或者保留乐观更新 + 失败回滚
  selectedPosition.value = null
  validMoves.value = []
}

function sendResign() {
  wsClient.send({ type: 'game_resign', seq: 0, data: {} })
}

function sendDrawRequest() {
  wsClient.send({ type: 'game_draw_req', seq: 0, data: {} })
}

function sendDrawAnswer(accept: boolean) {
  wsClient.send({ type: 'game_draw_ans', seq: 0, data: { accept } })
}

// 修改推送处理
function handleGameStart(data: GameStartData) {
  roomId.value = data.room_id
  // 从 FEN 解析棋盘，或使用初始棋盘
  board.value = getInitialBoard()
  yourColor.value = determineColor(data)
  redTime.value = data.initial_time
  blackTime.value = data.initial_time
  currentTurn.value = 0  // 红方先手
  isGameStarted.value = true
  isGameOver.value = false
  startTimer()
}

function handleMoveResult(data: MoveResultData) {
  if (data.success) {
    // 服务端确认走棋成功 (如果乐观更新则忽略)
    // 切换回合
    currentTurn.value = currentTurn.value === 0 ? 1 : 0
  }
}

function handleOpponentMove(data: OpponentMoveData) {
  const move = posToMove(data.from_pos, data.to_pos)
  board.value[move.to_row][move.to_col] = board.value[move.from_row][move.from_col]
  board.value[move.from_row][move.from_col] = -1
  lastMove.value = move
  currentTurn.value = currentTurn.value === 0 ? 1 : 0
  isInCheck.value = false  // 对手走棋后清除将军状态
}

function handleAIMove(data: AIMoveData) {
  const move = posToMove(data.from_pos, data.to_pos)
  board.value[move.to_row][move.to_col] = board.value[move.from_row][move.from_col]
  board.value[move.from_row][move.from_col] = -1
  lastMove.value = move
  currentTurn.value = currentTurn.value === 0 ? 1 : 0
  isInCheck.value = false
}

function handleAIThinking() {
  // UI 提示: AI 正在思考...
  isAIThinking.value = true
}

function handleGameOver(data: GameOverData) {
  isGameOver.value = true
  gameResult.value = data.winner  // 'red' / 'black' / 'draw'
  gameReason.value = data.reason
  winner.value = data.winner === 'red' ? 0 : data.winner === 'black' ? 1 : -1
  stopTimer()
}

function handleStateSync(data: StateSyncData) {
  // 从 FEN 恢复棋盘，或使用 data 中的完整棋盘
  yourColor.value = data.your_side === 'red' ? 0 : 1
  redTime.value = data.red_remaining_time
  blackTime.value = data.black_remaining_time
  roomId.value = data.room_id
}

// 移除方法
// - connect() / disconnect() — 不再建立独立游戏 WS
// - setWebSocketCallbacks() — 改为消息路由
```

### 8.3 game.handler.ts

```typescript
export function registerGameHandlers() {
  messageRouter.on(WSRespType.MOVE_RESULT, (data) => gameStore.handleMoveResult(data))
  messageRouter.on(WSRespType.OPPONENT_MOVE, (data) => gameStore.handleOpponentMove(data))
  messageRouter.on(WSRespType.AI_MOVE, (data) => gameStore.handleAIMove(data))
  messageRouter.on(WSRespType.AI_THINKING, () => gameStore.handleAIThinking())
  messageRouter.on(WSRespType.GAME_OVER, (data) => gameStore.handleGameOver(data))
  messageRouter.on(WSRespType.DRAW_REQUEST, (data) => gameStore.handleDrawRequest(data))
  messageRouter.on(WSRespType.DRAW_RESULT, (data) => gameStore.handleDrawResult(data))
  messageRouter.on(WSRespType.STATE_SYNC, (data) => gameStore.handleStateSync(data))
}
```

---

## F9: 匹配模块改造

**目标**：新增匹配 Store，支持 WS 匹配流程

**涉及文件**：
- `src/stores/match.ts` — 新建
- `src/ws/handlers/match.handler.ts` — 新建
- 删除 `src/api/match.ts`

### 9.1 match Store

```typescript
// src/stores/match.ts (新建)
export const useMatchStore = defineStore('match', () => {
  const isMatchmaking = ref(false)
  const matchPosition = ref(0)
  const estimatedWait = ref(30)

  async function joinMatch(gameType: string = 'pvp') {
    const result = await wsClient.request('match_join', { game_type: gameType })
    isMatchmaking.value = true
    matchPosition.value = result.position || 0
    estimatedWait.value = result.estimated_wait || 30
    authStore.setAuthState('matchmaking')
    return result
  }

  async function leaveMatch() {
    await wsClient.request('match_leave')
    isMatchmaking.value = false
    authStore.setAuthState('authenticated')
  }

  function handleMatchFound(data: MatchFoundData) {
    isMatchmaking.value = false
    authStore.setAuthState('in_room')
    // 设置当前房间
    roomStore.setCurrentRoom({
      roomId: data.room_id,
      yourSide: data.your_side,
      opponent: data.opponent,
      phase: 'playing',
    })
    // 等待 game_start 推送
  }

  return { isMatchmaking, matchPosition, estimatedWait, joinMatch, leaveMatch, handleMatchFound }
})
```

### 9.2 match.handler.ts

```typescript
export function registerMatchHandlers() {
  messageRouter.on(WSRespType.MATCH_QUEUED, (data) => matchStore.handleMatchQueued(data))
  messageRouter.on(WSRespType.MATCH_FOUND, (data) => matchStore.handleMatchFound(data))
  messageRouter.on(WSRespType.MATCH_LEFT, () => matchStore.handleMatchLeft())
}
```

---

## F10: 路由与守卫改造

**目标**：将路由守卫从 HTTP token 检查改为 WS 认证状态检查

**涉及文件**：`src/router/index.ts`

### 10.1 路由表调整

```typescript
// 移除: /room/:id 路由 (v2.0 无需单独的房间等待页面，合并到 Lobby 或直接进入 Game)
// 保留: /login, /register, /lobby, /rooms, /game/:id

const routes = [
  { path: '/', redirect: '/lobby' },
  { path: '/login', name: 'Login', component: () => import('@/pages/Login.vue'), meta: { requiresAuth: false } },
  { path: '/register', name: 'Register', component: () => import('@/pages/Register.vue'), meta: { requiresAuth: false } },
  { path: '/lobby', name: 'Lobby', component: () => import('@/pages/Lobby.vue'), meta: { requiresAuth: true } },
  { path: '/rooms', name: 'RoomList', component: () => import('@/pages/RoomList.vue'), meta: { requiresAuth: true } },
  { path: '/game/:id', name: 'Game', component: () => import('@/pages/Game.vue'), meta: { requiresAuth: true } },
]
```

### 10.2 守卫改造

```typescript
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // 检查 WS 认证状态
  if (to.meta.requiresAuth && authStore.authState !== 'authenticated' && authStore.authState !== 'in_room') {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (!to.meta.requiresAuth && authStore.authState !== 'unauthenticated') {
    next({ name: 'Lobby' })
  } else {
    next()
  }
})
```

---

## F11: 页面改造

**目标**：将所有页面适配新的 WS 架构

### 11.1 Login.vue 改造

**关键修改**：
- 不再调用 `authApi.login()`，改为 `authStore.login()` (内部 WS 请求)
- 错误处理：从 `error.response?.data?.message` 改为 `error.message` (WS 错误)
- 确保在 WS 连接已建立后才允许提交登录表单
- 新增：WS 连接状态提示（连接中/连接失败）

### 11.2 Register.vue 改造

**关键修改**：
- 同 Login，改为 `authStore.register()`
- 错误处理适配 WS 响应

### 11.3 Lobby.vue 改造

**关键修改**：
- 移除 `getMyRoom()` HTTP 调用，改为通过 authState 判断
- 排行/历史数据：从 `userApi.getRankings/getHistory` 改为 `wsClient.request('user_get_rankings/user_get_history')`
- 创建房间按钮：增加 PvE 选项（选择难度）
- 匹配按钮：调用 `matchStore.joinMatch()`
- 新增：监听 match_found 推送，匹配成功后跳转
- 新增：监听 player_joined / game_start 推送，创建 PvP 房间后显示等待状态
- 移除：`hasError` 处理中的 HTTP 错误逻辑

**新增功能**：
- PvE 快速对战：点击按钮 → 选择难度 → `room_create { room_type: 'pve', difficulty }` → 直接进入 Game
- PvP 快速匹配：点击按钮 → `match_join` → 等待 `match_found` → 跳转 Game
- 房间等待面板：创建 PvP 房间后，在 Lobby 显示等待弹窗，收到 `player_joined` + `game_start` 后跳转

### 11.4 RoomList.vue 改造

**关键修改**：
- 移除5秒轮询 `setInterval(fetchRoomList, 5000)`
- 首次加载 `wsClient.request('room_list')`
- 新增：监听推送更新（可选，或手动刷新按钮）
- 加入房间：改为 `roomStore.joinRoom(roomId)`
- 房间详情：不再需要单独的 `getRoom` 请求，列表数据已足够

### 11.5 GameRoom.vue → 移除或合并

**改造方案**：v2.0 中 PvP 手动房间加入即开始，无需"准备"阶段。此页面功能合并到 Lobby：

- **PvP 等待**：Lobby 中创建 PvP 房间后显示等待弹窗
- **直接开始**：收到 `game_start` 推送后跳转 `/game/:id`

**决策**：保留 GameRoom.vue 但大幅简化，仅作为"等待对手加入"的过渡页面。或者完全移除，等待逻辑放在 Lobby 中。

### 11.6 Game.vue 改造

**关键修改**：
- 移除：`gameStore.connect(gameWsUrl, gameToken)` — 不再建立独立 WS
- 移除：`wsManager.connectionState` 监听 — 改为监听 `authStore.connectionState`
- 修改：走棋交互从 `{ from_col, from_row, to_col, to_row }` 改为 `{ from_pos, to_pos }`
- 新增：AI 思考中提示 (监听 `ai_thinking` 消息)
- 新增：AI 走棋展示 (监听 `ai_move` 消息)
- 修改：游戏结束弹窗，使用新的 GameOverData 格式 (winner: 'red'/'black'/'draw', reason)
- 修改：重连逻辑，改为全局 WS 重连 + `reconnect` + `state_sync`
- 移除：独立的连接失败弹窗和重连按钮

---

## F12: 清理与配置

**目标**：移除旧的 HTTP API 层和不再需要的依赖

### 12.1 删除文件

| 文件 | 原因 |
|------|------|
| `src/api/request.ts` | Axios 实例，不再需要 |
| `src/api/auth.ts` | 改为 WS 认证 |
| `src/api/user.ts` | 改为 WS 请求 |
| `src/api/room.ts` | 改为 WS 请求 |
| `src/api/match.ts` | 改为 WS 请求 |
| `src/api/websocket.ts` | 旧 WS 管理器 |
| `src/types/websocket.ts` | 旧消息类型 |

### 12.2 修改 Vite 配置

```typescript
// vite.config.ts
server: {
  proxy: {
    // 移除 /api/v1 代理
    '/ws': {
      target: 'ws://localhost:8080',
      ws: true,
    },
  }
}
```

### 12.3 修改 package.json

- 移除 `axios` 依赖
- 运行 `npm uninstall axios`

### 12.4 清空空目录

- 删除 `src/composables/` (空)
- 删除 `src/utils/` (空)
- 删除 `src/api/` 目录

---

## F13: 端到端验证

**目标**：验证前端与 v2.0 后端的完整业务流程

### 13.1 测试场景

| # | 场景 | 验证点 |
|---|------|--------|
| 1 | 用户注册 | WS 连接 → auth_register → auth_register_result → 自动认证 |
| 2 | 用户登录 | WS 连接 → auth_login → auth_result → Lobby 加载 |
| 3 | Token 认证 | 刷新页面 → WS 重连 → auth_token → 恢复认证 |
| 4 | 断线重连 | 游戏中断线 → WS 重连 → reconnect → state_sync → 棋盘恢复 |
| 5 | 创建 PvE 房间 | room_create { pve } → game_start → 走棋 → ai_thinking → ai_move → game_over |
| 6 | 创建 PvP 房间 | room_create { pvp } → 等待 → player_joined → game_start |
| 7 | 加入房间 | room_list → room_join → game_start |
| 8 | 匹配 | match_join → match_queued → match_found → game_start |
| 9 | 走棋 | game_move → move_result → (对手) opponent_move |
| 10 | 认输 | game_resign → game_over |
| 11 | 求和 | game_draw_req → draw_request (对手) → game_draw_ans → draw_result |
| 12 | 排行榜 | user_get_rankings → 数据展示 |
| 13 | 对局历史 | user_get_history → 数据展示 |
| 14 | ELO 更新 | game_over → rating_update → 积分变化 |

### 13.2 验证清单

- [ ] WS 连接建立与断线重连正常
- [ ] 认证流程 (登录/注册/Token认证/断线重连) 正常
- [ ] 所有 HTTP 请求已移除，无 Axios 调用
- [ ] 无轮询逻辑残留
- [ ] 走棋格式正确 (from_pos/to_pos)
- [ ] AI 对局流程完整 (创建→走棋→AI回应→结束)
- [ ] 页面刷新后状态恢复正常
- [ ] 错误处理正常 (WS 错误/请求超时/非法操作)
