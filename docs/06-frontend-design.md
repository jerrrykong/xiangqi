# 前端设计文档

> 中国象棋对战游戏 — Vue 3 前端架构与设计

## 1. 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | ^3.5.34 | UI 框架 (Composition API + `<script setup>`) |
| Vite | ^8.0.12 | 构建工具 |
| TypeScript | ~6.0.2 | 类型系统 |
| Pinia | — | 状态管理 |
| Vue Router | — | 路由管理 (history 模式, base: `/xiangqi/`) |
| Element Plus | — | UI 组件库 (自动导入 + 图标全局注册) |
| 原生 WebSocket | — | 全局唯一长连接，承载所有业务通信 |

## 2. 目录结构

```
cmd/web/src/
├── main.ts                     # 应用入口 (Pinia + Router + ElementPlus)
├── App.vue                     # 根组件 (RouterView + WS处理器注册 + 断线检测)
├── auto-imports.d.ts           # 自动生成 — 全局类型声明
├── components.d.ts             # 自动生成 — 组件类型声明
├── assets/
│   └── hero.png                # 启动页背景图
├── components/
│   └── ChessBoard.vue          # 棋盘组件 (SVG + 绝对定位, 棋子/选中/高亮/动画)
├── pages/                      # 页面组件
│   ├── Splash.vue              # 启动页 (自动重连/凭证认证/登录入口)
│   ├── Login.vue               # 登录页
│   ├── Register.vue            # 注册页
│   ├── Lobby.vue               # 游戏大厅 (用户信息/排行榜/对局历史/匹配/创建房间)
│   ├── RoomList.vue            # 房间列表页
│   ├── GameRoom.vue            # 游戏房间页 (HTTP轮询模式, 遗留兼容)
│   └── Game.vue                # 对局页面 (棋盘+计时+走棋+认输/求和/重赛)
├── router/
│   └── index.ts                # 路由定义 + 守卫 (6条路由, WS鉴权守卫)
├── stores/                     # Pinia 状态管理
│   ├── auth.ts                 # 认证 Store (凭证/登录/重连/状态机)
│   ├── game.ts                 # 游戏 Store (棋盘/走棋/将军检测/记谱/音效/动画)
│   ├── match.ts                # 匹配 Store (排队/匹配结果)
│   └── room.ts                 # 房间 Store (房间列表/当前房间/创建/加入/离开)
├── styles/
│   └── main.css                # 全局样式 (木纹主题CSS变量/棋子/卡片/滚动条)
├── types/
│   ├── api.ts                  # AI难度枚举
│   └── chess.ts                # 象棋领域类型 (棋子编码/Position/Move/FEN/初始棋盘)
├── utils/
│   ├── sound.ts                # 音效管理器 (音效+语音双通道, 音量控制, 预加载)
│   └── sound_example.vue       # 音效使用示例
└── ws/                         # WebSocket 通信层
    ├── client.ts               # WS 单例客户端 (连接/重连/心跳/消息收发)
    ├── request.ts              # 请求-响应封装 (seq匹配/Promise化/超时)
    ├── router.ts               # 消息路由器 (推送消息分发, 处理器注册/去重)
    ├── types.ts                # WS 协议类型 (消息类型/数据类型/状态枚举)
    └── handlers/               # 推送消息处理器
        ├── auth.handler.ts     # 认证 (auth_result/error/rating_update)
        ├── game.handler.ts     # 游戏 (game_start/opponent_move/game_over/...)
        ├── match.handler.ts    # 匹配 (match_queued/match_found/match_left)
        ├── room.handler.ts     # 房间 (player_joined/player_left/room_update/...)
        └── user.handler.ts     # 用户 (user_me/user_rankings/user_history)
```

## 3. 通信架构

前端采用 **全局单一 WebSocket 长连接** 架构，所有业务通信均通过 WS 完成：

```
┌──────────────────────────────────────────────────────┐
│                     Vue App                          │
├──────────────────────────────────────────────────────┤
│  Pages ──► Stores ──► WS 通信层                      │
│                         │                            │
│              ┌──────────┴──────────┐                 │
│              ▼                     ▼                 │
│       WSRequestManager      MessageRouter            │
│       (请求-响应 seq匹配)    (推送消息分发)            │
│              │                     │                 │
│              ▼                     ▼                 │
│              WSClient (全局单例)                      │
│              连接/重连/心跳/收发                       │
│                      │                               │
├──────────────────────┼───────────────────────────────┤
│                      ▼                               │
│              WebSocket :8080/ws                       │
│              (统一服务, 全生命周期)                     │
└──────────────────────────────────────────────────────┘
```

### 3.1 消息格式

**统一消息结构**：

```typescript
{
  type: string,           // 消息类型 (如 'auth_login', 'game_move')
  seq: number,            // 序列号: 0=推送/心跳, >0=请求-响应匹配
  data: Record<string, any>,
  timestamp: number
}
```

- `seq > 0`：请求-响应模式，客户端发送时生成 `seq`，服务端在响应消息中带回相同 `seq`
- `seq = 0`：服务端推送消息，无需客户端请求

### 3.2 客户端→服务端消息 (C→S)

| 类别 | 消息类型 | data 格式 | 说明 |
|------|---------|-----------|------|
| **认证** | `auth_login` | `{ username, password }` | 登录 |
| | `auth_register` | `{ username, password, nickname? }` | 注册 |
| | `auth_token` | `{ token }` | JWT Token 认证(重连) |
| | `auth_refresh` | `{ refresh_token }` | 刷新 Token |
| | `reconnect` | `{ session_token }` | Session 重连 |
| **用户** | `user_get_me` | `{}` | 获取当前用户 |
| | `user_update_profile` | profile 字段 | 更新资料 |
| | `user_get_rankings` | `{ page, page_size }` | 排行榜 |
| | `user_get_history` | `{ page, page_size }` | 对局历史 |
| **房间** | `room_create` | `{ room_type, difficulty? }` | 创建房间 |
| | `room_list` | `{ page, page_size }` | 房间列表 |
| | `room_join` | `{ room_id }` | 加入房间 |
| | `room_leave` | — | 离开房间 |
| **游戏** | `game_move` | `{ from_pos: [row,col], to_pos: [row,col] }` | 走棋 |
| | `game_resign` | — | 认输 |
| | `game_draw_req` | — | 求和请求 |
| | `game_draw_ans` | `{ accept: boolean }` | 求和回复 |
| | `game_ready` | — | 准备开始(READY阶段) |
| | `game_rematch` | — | 再来一局(FINISHED阶段) |
| **匹配** | `match_join` | `{ game_type }` | 加入匹配队列 |
| | `match_leave` | — | 离开匹配队列 |
| **心跳** | `ping` | — | 每30秒自动发送 |

### 3.3 服务端→客户端消息 (S→C)

| 类别 | 消息类型 | data 关键字段 | 触发方式 |
|------|---------|-------------|---------|
| **认证** | `auth_result` | `success, user_id, username, nickname, rating, token, refresh_token, session_token, error` | 请求响应 |
| | `auth_register_result` | 同 `auth_result` | 请求响应 |
| | `auth_token_result` | 同上 + `state, room_id, room_phase` | 请求响应 |
| | `auth_refresh_result` | `token, session_token` | 请求响应 |
| | `reconnect_result` | `success, session_token, state, room_id` | 请求响应 |
| | `rating_update` | `rating, change, games_count` | 推送 |
| | `error` | `code, message` | 推送/响应 |
| **用户** | `user_me` | `id, username, nickname, rating, games_count, is_admin` | 请求响应 |
| | `user_profile_updated` | 同 `user_me` | 推送 |
| | `user_rankings` | `rankings[], total, page, page_size` | 请求响应 |
| | `user_history` | `games[], total, page, page_size` | 请求响应 |
| **房间** | `room_created` | `room_id, room_type, difficulty` | 请求响应 |
| | `room_list_result` | `rooms[]` | 请求响应 |
| | `room_joined` | `room_id, room_type, players[]` | 请求响应 |
| | `room_left` | — | 请求响应 |
| | `room_update` | — | 推送(房间变更通知) |
| | `player_joined` | `user_id, username, nickname, side, rating, phase?` | 推送 |
| | `player_left` | `user_id, phase?` | 推送 |
| **游戏** | `game_start` | `room_id, your_side, red_player, black_player, initial_time, increment, fen` | 推送 |
| | `move_result` | `success, fen, move?, message` | 请求响应 |
| | `opponent_move` | `from_pos, to_pos, fen, captured?` | 推送 |
| | `ai_thinking` | — | 推送 |
| | `ai_move` | `from_pos, to_pos, fen, captured?, think_time_ms` | 推送 |
| | `game_over` | `room_id, winner, reason, total_moves, red_rating_change, black_rating_change` | 推送 |
| | `draw_request` | `from_user_id, from_username` | 推送 |
| | `draw_result` | `accepted, reason?` | 推送 |
| | `ready_accepted` | — | 请求响应 |
| | `opponent_ready` | `user_id` | 推送 |
| | `opponent_rematch` | `user_id` | 推送 |
| **匹配** | `match_queued` | `position, estimated_wait` | 推送/响应 |
| | `match_found` | `room_id, opponent, your_side` | 推送 |
| | `match_left` | — | 推送 |
| **状态同步** | `state_sync` | `room_id, room_type, phase, fen, your_side, red_player, black_player, red_remaining_time, black_remaining_time, moves[], ready_players[], rematch_players[]` | 推送(重连恢复) |
| **心跳** | `pong` | — | 推送 |

## 4. 通信时序

### 4.1 认证流程

```
┌────────┐                          ┌────────┐
│ Client │                          │ Server │
└───┬────┘                          └───┬────┘
    │  WS 连接 /ws                       │
    │──────────────────────────────────► │
    │  连接建立                           │
    │ ◄───────────────────────────────── │
    │                                     │
    │  [新用户] auth_login {username,pwd}  │
    │──────────────────────────────────► │
    │  auth_result {token, session_token} │
    │ ◄───────────────────────────────── │
    │                                     │
    │  [重连用户] auth_token {token}       │
    │──────────────────────────────────► │
    │  auth_token_result {state,room_id}  │
    │ ◄───────────────────────────────── │
    │                                     │
    │  [Token过期] reconnect {session_token}│
    │──────────────────────────────────► │
    │  reconnect_result                   │
    │ ◄───────────────────────────────── │
```

认证优先级：JWT Token > Session Token。若 JWT 失效则自动降级为 session_token 重连。

### 4.2 房间创建与对局流程

```
┌────────┐              ┌────────┐              ┌────────┐
│ 玩家A  │              │ Server │              │ 玩家B  │
└───┬────┘              └───┬────┘              └───┬────┘
    │ room_create            │                       │
    │──────────────────────► │                       │
    │ room_created           │                       │
    │ ◄───────────────────── │                       │
    │                        │                       │
    │                        │  room_join {room_id}  │
    │                        │ ◄──────────────────── │
    │                        │  room_joined          │
    │                        │ ────────────────────► │
    │  player_joined         │                       │
    │ ◄───────────────────── │                       │
    │                        │                       │
    │  game_ready            │  game_ready           │
    │──────────────────────► │ ◄──────────────────── │
    │                        │                       │
    │  game_start (双方ready后推送)                     │
    │ ◄───────────────────── │ ────────────────────► │
    │                        │                       │
    │  game_move             │                       │
    │──────────────────────► │                       │
    │  move_result           │  opponent_move        │
    │ ◄───────────────────── │ ────────────────────► │
    │                        │                       │
    │         ... 对局进行 ...                        │
    │                        │                       │
    │  game_over (双方推送)                           │
    │ ◄───────────────────── │ ────────────────────► │
    │                        │                       │
    │  game_rematch          │  game_rematch         │
    │──────────────────────► │ ◄──────────────────── │
    │  game_start (重赛)                             │
    │ ◄───────────────────── │ ────────────────────► │
```

### 4.3 匹配流程

```
┌────────┐              ┌────────┐              ┌────────┐
│ 玩家A  │              │ Server │              │ 玩家B  │
└───┬────┘              └───┬────┘              └───┬────┘
    │ match_join             │  match_join           │
    │──────────────────────► │ ◄──────────────────── │
    │ match_queued           │  match_queued         │
    │ ◄───────────────────── │ ────────────────────► │
    │                        │                       │
    │      ... 等待匹配 ...                           │
    │                        │                       │
    │  match_found {room_id, opponent, your_side}    │
    │ ◄───────────────────── │ ────────────────────► │
    │                        │                       │
    │  game_start            │                       │
    │ ◄───────────────────── │ ────────────────────► │
```

### 4.4 断线重连流程

```
┌────────┐                          ┌────────┐
│ Client │                          │ Server │
└───┬────┘                          └───┬────┘
    │  WS 断连                            │
    │  (自动记录 phaseBeforeDisconnect)    │
    │                                     │
    │  指数退避重连 (2s→4s→8s→16s→32s)    │
    │──────────────────────────────────► │
    │  连接恢复                           │
    │ ◄───────────────────────────────── │
    │                                     │
    │  auth_token {token}                 │
    │──────────────────────────────────► │
    │  auth_token_result {state:in_room}  │
    │ ◄───────────────────────────────── │
    │                                     │
    │  state_sync {fen, phase, times...}  │
    │ ◄───────────────────────────────── │
    │  (恢复棋盘/计时/着法/阶段)           │
```

### 4.5 求和流程

```
┌────────┐              ┌────────┐              ┌────────┐
│ 玩家A  │              │ Server │              │ 玩家B  │
└───┬────┘              └───┬────┘              └───┬────┘
    │ game_draw_req          │                       │
    │──────────────────────► │  draw_request         │
    │                        │ ────────────────────► │
    │                        │                       │
    │                        │  game_draw_ans         │
    │                        │ ◄──────────────────── │
    │                        │                       │
    │  [接受] draw_result {accepted:true}             │
    │  ◄──────────────────── │ ────────────────────► │
    │  game_over (reason: agreement)                 │
    │  ◄──────────────────── │ ────────────────────► │
    │                        │                       │
    │  [拒绝] draw_result {accepted:false}           │
    │  ◄──────────────────── │                       │
    │  (继续对局)              │                       │
```

## 5. WS 通信层

### 5.1 WSClient (`ws/client.ts`)

全局单例 `wsClient`，管理 WebSocket 生命周期。

| 属性/方法 | 说明 |
|----------|------|
| `connectionState: Ref<WSConnectionState>` | 连接状态: `disconnected` / `connecting` / `connected` |
| `authState: Ref<WSAuthState>` | 认证状态: `unauthenticated` / `authenticated` / `in_room` / `matchmaking` |
| `connect(url)` | 建立 WS 连接 (10秒超时) |
| `disconnect()` | 手动断连 (关闭自动重连) |
| `enableReconnect()` | 开启自动重连 |
| `send({type, seq, data})` | 发送原始消息 |
| `request(type, data, timeout)` | 请求-响应模式 (Promise, 10秒超时) |
| `onAuthSuccess()` | 认证成功: 开启重连 + 心跳 (30s/次) |
| `isConnected` | getter, 连接是否就绪 |

**重连策略**：指数退避 (2s → 4s → 8s → 16s → 32s)，最多5次。仅在认证成功后 (`shouldReconnect=true`) 触发。

**消息处理流程**：
1. `onmessage` → JSON 解析
2. `seq > 0` → 匹配 `WSRequestManager` 挂起请求
3. `type='pong'` → 忽略
4. `type='error'` → 路由到 error handler
5. 其他 → `MessageRouter.route(type, data)` 分发

### 5.2 WSRequestManager (`ws/request.ts`)

将请求-响应模式 Promise 化：
- 发送消息时生成递增 `seq`
- 将 `{ seq, resolve, reject, timer }` 存入 `pending` Map
- 收到相同 `seq` 的响应时 resolve Promise
- 10秒超时抛出 `WSTimeoutError`
- `data.code !== 0` 且有 `message` 时抛出 `WSError`

### 5.3 MessageRouter (`ws/router.ts`)

推送消息分发器：
- `on(type, handler)` — 注册处理器 (自动去重)
- `off(type, handler)` — 移除处理器
- `route(type, data)` — 分发到所有注册处理器
- `clear()` — 清除所有处理器 (HMR 防范)

### 5.4 消息处理器 (`ws/handlers/`)

5 个处理器文件，在 `App.vue` 的 `onMounted` 中注册，将 WS 推送消息桥接到 Store：

| 文件 | 注册的消息类型 | 桥接目标 |
|------|-------------|---------|
| `auth.handler.ts` | `auth_result`, `auth_register_result`, `auth_token_result`, `auth_refresh_result`, `reconnect_result`, `rating_update`, `error` | `authStore` |
| `game.handler.ts` | `game_start`, `move_result`, `opponent_move`, `ai_thinking`, `ai_move`, `game_over`, `draw_request`, `draw_result`, `state_sync`, `opponent_ready`, `opponent_rematch`, `player_left` | `gameStore` |
| `match.handler.ts` | `match_queued`, `match_found`, `match_left` | `matchStore` |
| `room.handler.ts` | `room_created`, `room_joined`, `room_left`, `player_joined`, `player_left`, `room_update`, `room_list_result` | `roomStore` |
| `user.handler.ts` | `user_me`, `user_profile_updated`, `user_rankings`, `user_history` | `authStore` |

## 6. 状态管理

### 6.1 auth Store (`stores/auth.ts`)

管理认证状态、凭证持久化、断线重连。

**状态**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `user` | `UserProfile \| null` | 用户信息 `{user_id, username, nickname, rating, games_count, is_admin}` |
| `token` | `string \| null` | JWT Token (localStorage 持久化) |
| `sessionToken` | `string \| null` | Session Token (localStorage 持久化) |
| `refreshToken` | `string \| null` | Refresh Token |
| `authState` | `WSAuthState` | `unauthenticated` / `authenticated` / `in_room` / `matchmaking` |
| `isReconnecting` | `boolean` | 是否正在重连 |
| `phaseBeforeDisconnect` | `string \| null` | 断线前的游戏阶段 |
| `reconnectMessages` | `string[]` | 重连提示消息队列 |

**计算属性**：`isAuthenticated` = `authState !== 'unauthenticated'`

**核心方法**：

| 方法 | 说明 |
|------|------|
| `init()` | 从 localStorage 恢复用户信息 |
| `login(username, password)` | 连接 WS + `auth_login` → 保存凭证 |
| `register(username, password, nickname?)` | 连接 WS + `auth_register` → 保存凭证 |
| `logout()` | 清除重连回调 → 断开 WS → 清除认证 |
| `authenticate()` | 优先 JWT token 认证，降级 session_token 重连 |
| `markReconnecting(phaseBefore)` | 标记断线状态，保存断线前阶段 |

**认证状态流转**：

```
unauthenticated
    ├── login/register 成功 ──► authenticated
    ├── auth_token 成功 + in_room ──► in_room
    ├── room_create/join ──► in_room
    ├── match_join ──► matchmaking
    │       ├── match_found ──► in_room
    │       └── match_leave ──► authenticated
    └── WS 断连 ──► unauthenticated (自动重连 → 重新认证)
```

### 6.2 game Store (`stores/game.ts`)

管理对局核心状态、走棋逻辑、将军检测、记谱、音效。

**状态**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `board` | `number[][]` | 10×9 棋盘 |
| `currentTurn` | `0 \| 1` | 当前走棋方 (0=红, 1=黑) |
| `redTime` / `blackTime` | `number` | 剩余时间(秒) |
| `yourColor` | `0 \| 1` | 我的颜色 |
| `phase` | `string` | `waiting` / `ready` / `playing` / `finished` |
| `isGameStarted` / `isGameOver` | `boolean` | 对局状态 |
| `gameResult` / `gameReason` | `string \| null` | 结果/原因 |
| `myRatingChange` | `number` | 积分变化 |
| `selectedPosition` | `Position \| null` | 选中棋子 |
| `validMoves` | `Position[]` | 合法走法 |
| `lastMove` | `Move \| null` | 上一步走法 |
| `isInCheck` / `checkPosition` | `boolean` / `Position \| null` | 将军状态 |
| `isAIThinking` | `boolean` | AI思考中 |
| `moveHistory` | `MoveRecord[]` | 走棋历史 |
| `animatingMove` | 对象 \| null | 走棋动画状态 |
| `iAmReady` / `opponentReady` | `boolean` | 准备状态 |
| `iWantRematch` / `opponentWantsRematch` | `boolean` | 重赛状态 |
| `drawRequestFrom` | `string \| null` | 求和请求来源 |

**计算属性**：`isBoardFrozen` / `isMyTurn` / `myColorName` / `opponentColorName`

**核心方法**：

| 方法 | 说明 |
|------|------|
| `sendMove(move)` | 发送走棋 (Move → `from_pos/to_pos` 格式) |
| `sendResign()` | 发送认输 |
| `sendDrawRequest/Answer` | 求和 |
| `sendReady()` | 准备开始 |
| `sendRematch()` | 再来一局 |
| `selectPiece(position)` | 选中棋子 + 计算合法走法 |
| `computeValidMoves(row, col)` | 计算合法走法 (含过滤送将/对将) |
| `isKingAttacked(brd, color)` | 将军检测 (车/马/炮/兵/将对将) |
| `applyMoveWithAnimation(move)` | 执行走棋 + 动画 + 音效 + 语音 + 记录 |
| `handleStateSync(data)` | 断线重连: 恢复棋盘/计时/着法/阶段 |

**走棋语音规则** (优先级递减)：

| 优先级 | 条件 | 语音键 |
|--------|------|--------|
| 1 | 将军 | `check` + `check_voice` |
| 2 | 吃子 | `eat_xxx` (按被吃棋子类型) |
| 3 | 士向前走 | `advisor` |
| 4 | 士向后走 | `drop_advisor` |
| 5 | 象向前走 | `elephant` |
| 6 | 象向后走 | `drop_elephant` |
| 7 | 当头炮(初始位置平移到中路) | `cannon` |
| 8 | 平炮(横向走) | `level_cannon` |
| 9 | 出车(从初始位置移出) | `chariot` |
| 10 | 跳马 | `horse` |
| 11 | 兵/卒向前 | `pawn` |

### 6.3 room Store (`stores/room.ts`)

管理房间列表、当前房间状态。

**状态**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `roomList` | `Room[]` | 房间列表 |
| `currentRoom` | 对象 \| null | `{ roomId, roomType, phase, yourSide, opponent?, difficulty? }` |
| `isLoading` | `boolean` | |

**计算属性**：`isInRoom` = `!!currentRoom`

**核心方法**：

| 方法 | 说明 |
|------|------|
| `fetchRoomList(page, pageSize)` | WS 请求房间列表 |
| `createRoom(roomType, difficulty?)` | WS 创建房间 |
| `joinRoom(roomId)` | WS 加入房间 |
| `leaveRoom()` | WS 离开房间 |
| `setCurrentRoom(room)` | 外部设置 (匹配/重连场景) |
| `handlePlayerJoined(data)` | 对手加入 → 设置 opponent |
| `handlePlayerLeft(data)` | 对手离开 → 清除 opponent |
| `handleGameStart(data)` | 游戏开始 → phase='playing' |

### 6.4 match Store (`stores/match.ts`)

管理匹配队列状态。

**状态**：`isMatchmaking`, `matchPosition`, `estimatedWait`

**方法**：`joinMatch(gameType)`, `leaveMatch()`, `handleMatchQueued/Found/Left()`

## 7. 组件

### 7.1 ChessBoard.vue

基于 SVG + CSS 绝对定位的中国象棋棋盘组件。

**Props**：

| Prop | 类型 | 说明 |
|------|------|------|
| `board` | `number[][]` | 10×9 棋盘数据 |
| `selectedPosition` | `Position \| null` | 选中棋子位置 |
| `validMoves` | `Position[]` | 合法走法 |
| `lastMove` | `Move \| null` | 上一步走法 |
| `isInCheck` | `boolean` | 是否将军 |
| `checkPosition` | `Position \| null` | 被将军位置 |
| `yourColor` | `0 \| 1` | 玩家颜色 (1=翻转棋盘) |
| `isMyTurn` | `boolean` | 是否轮到我 |
| `isGameStarted` | `boolean` | 游戏是否开始 |
| `frozen` | `boolean?` | 冻结棋盘 (finished) |
| `animatingMove` | 对象 \| null | 走棋动画 `{from_row, from_col, to_row, to_col, duration}` |

**Events**：
- `piece-click(position)` — 点击棋子
- `position-click(position)` — 点击目标位置(走棋)
- `board-click` — 点击棋盘空白区域(取消选中)

**渲染特性**：
- SVG: 棋盘线、九宫对角线、楚河汉界、炮/兵标记点
- 3D 边框效果 (投影 + 凸起边框)
- 黑方视角翻转 (旋转180°)
- 选中高亮(金色)、最后一步(绿色)、将军(红色闪烁)
- 合法走法提示: 绿色圆点(空位)、红色边框(吃子)
- 走棋动画: CSS `piece-slide-in`
- 响应式缩放: 宽度超出父容器时自动缩小

**常量**: `CELL_SIZE=55px`, `BORDER_WIDTH=30px`, `PieceConfig.Size=50px`

## 8. 页面

### 8.1 Splash.vue — 启动页

**状态机**: `idle → connecting → connected | failed | token_invalid`

**流程**：
1. 入场动画 (logo → 标题 → 状态信息)
2. 有本地 token → 自动连接 (最多3次重试)
3. 连接成功 → `authStore.authenticate()` → 跳转 `/lobby`
4. 凭证失效 → 显示登录按钮
5. 全部失败 → 显示"连接服务器"按钮

### 8.2 Login.vue — 登录页

表单字段: `username` (4-32字符), `password` (≥8字符)。支持 redirect 参数。

### 8.3 Register.vue — 注册页

表单字段: `username`, `nickname`(选填), `password`(含字母+数字), `confirmPassword`。

### 8.4 Lobby.vue — 大厅页

**功能模块**：
- 用户信息卡片 (头像/用户名/积分/对局数)
- 操作按钮: 创建PvP房间、PvE人机(1-5级难度选择)、房间列表
- 快速匹配: `match_join`，显示排队位置和预计等待
- 排行榜: 前10名
- 最近对局: 前10局
- 等待对手卡片 (创建房间后显示)
- 断线重连提示

**关键 watch**: `gameStore.isGameStarted` → 跳转 `/game/:roomId`

### 8.5 RoomList.vue — 房间列表页

WS 请求房间列表，支持分页(20条/页)。点击房间 → 加入 → 跳转 Game 页。

### 8.6 Game.vue — 对局页面 (核心)

**双布局**：
- 宽屏 (≥1024px): 左面板(对手+自己) | 棋盘 | 右面板(操作+着法历史)
- 窄屏 (<1024px): 对手信息行 | 棋盘 | 自己信息行 | 操作按钮行

**功能按钮**：
- Playing: 认输、求和、返回大厅
- Ready: 开始 (棋盘中央浮动按钮, 3D效果)
- Finished: 再来一局、返回大厅

**浮层提示**: WS断连、AI思考中、等待对手加入、等待对方开始、对方已准备

**结果弹窗**: 胜负描述 + 积分变化 + 再来一局/返回

**求和弹窗**: 同意/拒绝

**着法历史**: 实时中文记谱 (如"1. 红 炮二平五")，自动滚动

**音效开关**: 右面板/操作栏音效按钮

## 9. 棋盘引擎 (`types/chess.ts`)

### 棋子编码

`color * 10 + piece_type`，与后端一致：

| 红(0) | King=0 | Advisor=1 | Bishop=2 | Knight=3 | Rook=4 | Cannon=5 | Pawn=6 |
|-------|--------|-----------|----------|----------|--------|----------|--------|
| 黑(1) | King=10 | Advisor=11 | Bishop=12 | Knight=13 | Rook=14 | Cannon=15 | Pawn=16 |

Empty = -1。棋盘: 10行 × 9列，`board[row][col]`。

### 核心函数

| 函数 | 说明 |
|------|------|
| `getPieceColor(piece)` | 返回 0(红) / 1(黑) / -1(空) |
| `isRedPiece/isBlackPiece` | 棋子颜色判断 |
| `moveToPos(move)` | Move → `{from_pos: [row,col], to_pos: [row,col]}` |
| `posToMove(fromPos, toPos)` | `from_pos/to_pos` → Move |
| `getInitialBoard()` | 返回 10×9 初始棋盘 |
| `parseFEN(fen)` | 从 FEN 字符串恢复棋盘 |

### 棋盘常量

- `Rows=10, Cols=9`; 红方九宫: row 7-9, col 3-5; 黑方九宫: row 0-2, col 3-5

## 10. 音效管理器 (`utils/sound.ts`)

全局单例 `getSoundManager()`，双通道 (音效 + 语音) 管理。

| 类别 | 键 | 文件 |
|------|-----|------|
| 音效 | `pickup`, `putdown`, `capture`, `check`, `win`, `lose`, `draw`, `button_click` | `/sounds/sfx_*.wav` |
| 走棋语音 | `chariot`, `pawn`, `horse`, `advisor`, `elephant`, `cannon` | `/sounds/voice_move_*.wav` |
| 落子语音 | `drop_advisor`, `drop_elephant`, `level_cannon` | `/sounds/voice_drop_*.wav` / `voice_ping_*.wav` |
| 吃子语音 | `eat_advisor`, `eat_elephant`, `eat_cannon`, `eat_pawn`, `eat_chariot`, `eat_horse` | `/sounds/voice_eat_*.wav` |
| 将军语音 | `check_voice` | `/sounds/voice_check.wav` |
| 游戏语音 | `start`, `your_turn`, `red_win`, `black_win`, `draw_voice` | `/sounds/voice_*.wav` |

**核心 API**: `init()` 预加载, `play(key)` 播放(clone支持重叠), `setEnabled/isEnabled` 音效开关, `setVoiceEnabled/isVoiceEnabled` 语音开关, `setSfxVolume/setVoiceVolume` 音量控制。

## 11. 路由

| 路径 | 名称 | 组件 | 认证 | 说明 |
|------|------|------|------|------|
| `/` | Splash | Splash.vue | 否 | 启动/重连 |
| `/login` | Login | Login.vue | 否 | 登录 |
| `/register` | Register | Register.vue | 否 | 注册 |
| `/lobby` | Lobby | Lobby.vue | 是 | 大厅 |
| `/rooms` | RoomList | RoomList.vue | 是 | 房间列表 |
| `/game/:id` | Game | Game.vue | 是 | 对局 |

**路由守卫**：
1. 需要认证但 WS 未连接 → 重定向 Splash (携带 redirect)
2. 需要认证但未认证 → 重定向 Splash
3. 已认证访问登录/注册页 → 重定向 Lobby

## 12. 全局样式 (`styles/main.css`)

**CSS 变量**：
- `--color-piece-red: #c41e3a` / `--color-piece-black: #1a1a1a`
- `--color-board-line: #8b5a2b` / `--color-board-bg: #deb887`
- `--color-wood-50` ~ `--color-wood-900` (木纹色系)

**字体**: Google Fonts `Noto Serif SC` (思源宋体)

**预定义类**: `.piece` (棋子), `.page-container` (页面容器), `.card` (卡片), `.board-texture` (棋盘纹理)
