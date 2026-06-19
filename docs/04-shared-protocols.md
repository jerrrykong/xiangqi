# 通用协议与数据结构设计

> 所属服务：Game 服务（统一）/ AI 服务（共用）
> 文档版本：v2.0
> 架构变更：所有客户端通信统一为 WebSocket 长连接，取消 HTTP REST API

---

## 一、编码体系总览

### 1.1 编码体系分层

```
本规范定义了三个层面的编码：
├── 棋子编码        棋子类型 + 颜色（int8）
├── 棋盘编码        10×9 平面坐标系（字符）
├── 着法编码        UCI 变种（字符串 / 结构体）
└── 游戏状态编码    局面特征张量（AI 专用）
```

---

## 二、棋盘坐标系

### 2.1 坐标定义（红方视角）

使用标准中国象棋坐标，**红方视角**：

```
   0   1   2   3   4   5   6   7   8
0  车  马  相  仕  将  仕  相  马  车     ← 黑方底线（行号 0）
1  ·   ·   ·   ·   ·   ·   ·   ·   ·     ← 黑方巡河线
2  ·   炮   ·   ·   ·   ·   ·   炮   ·   ←
3  兵   ·   兵   ·   兵   ·   兵   ·   兵
4  ·   ·   ·   ·   ·   ·   ·   ·   ·
5  ·   ·   ·   ·   ·   ·   ·   ·   ·     ← 河界
6  ·   ·   ·   ·   ·   ·   ·   ·   ·
7  卒   ·   卒   ·   卒   ·   卒   ·   卒
8  ·   炮   ·   ·   ·   ·   ·   炮   ·
9  ·   ·   ·   ·   ·   ·   ·   ·   ·     ← 红方巡河线
10 车  马  相  仕  帅  仕  相  马  车     ← 红方底线（行号 10）
```

- **列（Col）**：0~8，从左到右
- **行（Row）**：0~10，从上到下（黑方视角 0 行在上，红方视角 10 行在下）
- **坐标表示**：`"e1"` = Col=4, Row=2（炮初始位置红方）；`"e10"` = Col=4, Row=10（帅位置）

### 2.2 坐标转换

| 用途 | 格式 | 示例 |
|---|---|---|
| 显示（前端） | 列字母 + 行数字 | `"e10"` |
| 内部计算 | `(col, row)` 元组 | `(4, 10)` |
| 数组索引 | `[row][col]` | `board[10][4]` |
| AI 输入 | 展平一维索引 | `row * 9 + col` |

```
// 坐标字符串转内部坐标
func parsePos(s string) (col int, row int) {
    col = int(s[0] - 'a')  // 'a'→0, 'e'→4
    row = int(s[1] - '0')  // '0'→0, '9'→9
    return
}

// 行号方向：黑方向上移动 row 递减，红方向上移动 row 递增
// 红方 move_forward = +1（向下走），黑方 move_forward = -1（向上走）
```

---

## 三、棋子编码

### 3.1 棋子类型枚举

| 常量名 | 值 | 含义 | 红方符号 | 黑方符号 |
|---|---|---|---|---|
| `PIECE_KING` | 0 | 将/帅 | 帅 | 将 |
| `PIECE_ADVISOR` | 1 | 仕/士 | 仕 | 士 |
| `PIECE_BISHOP` | 2 | 相/象 | 相 | 象 |
| `PIECE_KNIGHT` | 3 | 马 | 马 | 马 |
| `PIECE_ROOK` | 4 | 车 | 车 | 车 |
| `PIECE_CANNON` | 5 | 炮 | 炮 | 炮 |
| `PIECE_PAWN` | 6 | 兵/卒 | 兵 | 卒 |

### 3.2 棋子颜色

```go
// Go
type Color int8
const (
    COLOR_NONE  Color = 0
    COLOR_RED   Color = 1  // 红方，先手
    COLOR_BLACK Color = 2  // 黑方，后手
)
```

```python
# Python
from enum import IntEnum
class Color(IntEnum):
    NONE  = 0
    RED   = 1  # 先手
    BLACK = 2  # 后手
```

### 3.3 棋子完整编码

棋子编码 = `color * 10 + piece_type`，这样任意棋子可用一个 int8 表示：

```python
RED_KING    = 1 * 10 + 0 = 10   # 红帅
RED_ROOK    = 1 * 10 + 4 = 14   # 红车
BLACK_KING  = 2 * 10 + 0 = 20   # 黑将
BLACK_PAWN  = 2 * 10 + 6 = 26   # 黑卒
EMPTY       = 0                  # 空位
```

解码：
```python
def decode_piece(code: int) -> tuple[Color, PieceType]:
    if code == 0:
        return Color.NONE, 0
    color = Color(code // 10)
    ptype = code % 10
    return color, ptype
```

---

## 四、棋盘数据结构

### 4.1 平面棋盘（10×9 数组）

```python
# Python: board[row][col]，row∈[0,10], col∈[0,8]
# 红方视角初始化：
INITIAL_BOARD = [
    [14, 13, 12, 11, 10, 11, 12, 13, 14],  # row 0: 黑车马象士将士象马车
    [ 0,  0,  0,  0,  0,  0,  0,  0,  0],  # row 1
    [ 0, 15,  0,  0,  0,  0,  0, 15,  0],  # row 2: 黑炮
    [26,  0, 26,  0, 26,  0, 26,  0, 26],  # row 3: 黑卒
    [ 0,  0,  0,  0,  0,  0,  0,  0,  0],  # row 4
    [ 0,  0,  0,  0,  0,  0,  0,  0,  0],  # row 5: 河界
    [ 0,  0,  0,  0,  0,  0,  0,  0,  0],  # row 6
    [ 6,  0,  6,  0,  6,  0,  6,  0,  6],  # row 7: 红兵
    [ 0,  5,  0,  0,  0,  0,  0,  5,  0],  # row 8: 红炮
    [ 0,  0,  0,  0,  0,  0,  0,  0,  0],  # row 9
    [ 4,  3,  2,  1,  0,  1,  2,  3,  4],  # row 10: 红车马相仕帅
]
```

### 4.2 位棋盘（可选，用于 AI 高效查询）

```python
# Python: 位棋盘，每种棋子一个 64 位整数（10行×9列=90格，用 128 位分两段）
class BitBoard:
    def __init__(self):
        # 每个棋子颜色+类型 = 14 种棋子，各用 1 个 uint64
        # 额外 2 个 uint64 标记红/黑 所有棋子位置
        self.pieces: dict[int, int] = {}  # piece_code -> bitboard
        self.red_mask: int = 0
        self.black_mask: int = 0
        self.all_mask: int = 0

    def get_bit(self, row: int, col: int) -> int:
        idx = row * 9 + col
        return 1 << idx

    def set_piece(self, row: int, col: int, piece: int):
        mask = self.get_bit(row, col)
        self.pieces[piece] |= mask
        self.all_mask |= mask
        color = piece // 10
        if color == Color.RED:
            self.red_mask |= mask
        else:
            self.black_mask |= mask
```

---

## 五、着法编码

### 5.1 UCI 变种格式

沿用国际象棋 UCI 的基本格式，扩展以支持中国象棋的特殊走法：

```
着法字符串格式：[起点][终点][特殊标记]

示例：
  "e10e9"   → 帅从 e10 走到 e9（向上一步）
  "e2e5"    → 炮从 e2 跳到 e5（吃子）
  "a4a3"    → 兵从 a4 走到 a3（过河前）
  "a3a4"    → 兵从 a3 走到 a4（过河后）
```

### 5.2 Move 结构体

```python
# Python
from dataclasses import dataclass, frozen

@frozen
class Move:
    from_col: int      # 起点列 0-8
    from_row: int      # 起点行 0-10
    to_col: int        # 终点列 0-8
    to_row: int        # 终点行 0-10

    @property
    def from_pos(self) -> str:
        return f"{chr(ord('a') + self.from_col)}{self.from_row}"

    @property
    def to_pos(self) -> str:
        return f"{chr(ord('a') + self.to_col)}{self.to_row}"

    def __str__(self) -> str:
        return f"{self.from_pos}{self.to_pos}"

    def __eq__(self, other) -> bool:
        return (self.from_col == other.from_col
                and self.from_row == other.from_row
                and self.to_col == other.to_col
                and self.to_row == other.to_row)

    def __hash__(self):
        return hash((self.from_col, self.from_row,
                     self.to_col, self.to_row))
```

```go
// Go
type Move struct {
    FromCol int8  `json:"from_col"`
    FromRow int8  `json:"from_row"`
    ToCol   int8  `json:"to_col"`
    ToRow   int8  `json:"to_row"`
}

func (m Move) String() string {
    return fmt.Sprintf("%c%d%c%d",
        rune('a'+m.FromCol), m.FromRow,
        rune('a'+m.ToCol), m.ToRow)
}

// 规范化：始终以"从哪到哪"表示，吃子不吃子不在字符串中区分
// 吃子由 board[to] != 0 判断
```

### 5.3 规范化着法（解决歧义）

当同类型棋子可走到同一目标位置时（如同列两车），着法需唯一：
- 同列两车可走：`"e10e0a"` / `"e10e0b"` — 加后缀 `a`/`b` 表示同列第几个
- 同列两马可走：`"b1b3a"` / `"b10b8a"`

**简化方案**（推荐 MVP）：不允许同列存在同类型棋子（着法通过位置唯一确定，无需后缀）。

---

## 六、游戏状态机

### 6.1 房间状态枚举

```python
class RoomStatus(IntEnum):
    WAITING   = 1  # 等待玩家加入
    READY     = 2  # 玩家已就绪，等待开始
    PLAYING   = 3  # 对局进行中
    FINISHED  = 4  # 对局结束
```

### 6.2 对局结果枚举

```python
class GameResult(IntEnum):
    ONGOING      = 0  # 对局进行中
    RED_WINS     = 1  # 红方胜
    BLACK_WINS   = 2  # 黑方胜
    DRAW         = 3  # 和棋
    RED_RESIGN   = 4  # 红方认输
    BLACK_RESIGN = 5  # 黑方认输
    RED_TIMEOUT  = 6  # 红方超时
    BLACK_TIMEOUT= 7  # 黑方超时
    RED_DISCONNECT = 8  # 红方断线超时
    BLACK_DISCONNECT = 9  # 黑方断线超时
```

### 6.3 难度等级枚举

```python
class Difficulty(IntEnum):
    ENTRY    = 1  # 入门  （50~100 次 MCTS）
    EASY     = 2  # 简单  （100~200 次）
    MEDIUM   = 3  # 中等  （400~800 次）
    HARD     = 4  # 困难  （1600~3200 次）
    MASTER   = 5  # 大师  （6400+ 次）

    @property
    def mcts_sims(self) -> int:
        mapping = {
            1: 100,      # 入门
            2: 200,      # 简单
            3: 800,      # 中等
            4: 3200,     # 困难
            5: 6400,     # 大师
        }
        return mapping[self.value]
```

---

## 七、WebSocket 消息协议（v2.0 — 全 WebSocket 通信）

### 7.1 消息格式

所有 WebSocket 消息统一 JSON 格式：

```json
{
  "type": "message_type",
  "seq": 42,
  "data": { ... }
}
```

- `type`：消息类型，字符串，必填
- `seq`：消息序列号，递增，用于消息顺序保证，非必填但推荐
- `data`：消息数据，对象，必填（空对象 `{}` 也必须存在）

### 7.2 消息类型总览

```
客户端 → 服务端消息类型：
├── 认证
│   ├── auth_login         登录
│   ├── auth_register      注册
│   ├── auth_token         Token 认证
│   ├── auth_refresh       刷新 Token
│   └── reconnect          断线重连
├── 用户
│   ├── user_get_me           获取个人信息
│   ├── user_update_profile   修改个人信息
│   ├── user_get_rankings     积分排行榜
│   └── user_get_history      对局历史
├── 房间
│   ├── room_create        创建房间
│   ├── room_list          房间列表
│   ├── room_join          加入房间
│   └── room_leave         离开房间
├── 游戏（在房间中）
│   ├── game_move          落子
│   ├── game_resign        认输
│   ├── game_draw_req      和棋请求
│   └── game_draw_ans      和棋应答
├── 匹配
│   ├── match_join         加入匹配队列
│   └── match_leave        离开匹配队列
├── 管理后台
│   ├── admin_users        用户列表
│   ├── admin_ban          封禁用户
│   ├── admin_stats        运营数据
│   └── admin_models       模型列表
└── 通用
    └── ping               心跳

服务端 → 客户端消息类型：
├── 认证
│   ├── auth_result        认证结果
│   └── kicked             被踢出（重复登录）
├── 用户
│   ├── user_me                个人信息
│   ├── user_profile_updated   个人信息更新结果
│   ├── user_rankings          排行榜
│   ├── user_history           对局历史
│   └── rating_update          积分变化通知
├── 房间
│   ├── room_created       房间已创建
│   ├── room_list          房间列表
│   └── room_start         房间开始游戏
├── 游戏
│   ├── game_start         对局开始
│   ├── move_result        着法结果
│   ├── ai_thinking        AI 思考中
│   ├── ai_move            AI 落子
│   ├── game_over          对局结束
│   ├── draw_request       和棋请求
│   ├── draw_answered      和棋应答
│   ├── opponent_left      对手断线
│   ├── opponent_rejoin    对手重连
│   ├── opponent_ready     对手已准备（READY 阶段，含 user_id）
│   ├── opponent_rematch   对手发起续局（FINISHED 阶段，含 user_id）
│   └── state_sync         状态同步（断线重连后）
├── 匹配
│   ├── match_queued       已加入队列
│   ├── match_found        匹配成功
│   └── match_left         已离开队列
├── 管理后台
│   ├── admin_users_result   用户列表结果
│   ├── admin_ban_result     封禁结果
│   ├── admin_stats_result   运营数据结果
│   └── admin_models_result  模型列表结果
├── 通用
│   ├── pong               心跳回复
│   └── error              错误通知
```

### 7.3 认证消息（详细）

#### 客户端 → 服务端

**auth_login — 登录**
```json
{ "type": "auth_login", "data": { "username": "player1", "password": "SecurePass123" } }
```

**auth_register — 注册**
```json
{ "type": "auth_register", "data": { "username": "player1", "password": "SecurePass123", "nickname": "象棋新手" } }
```

**auth_token — Token 认证**
```json
{ "type": "auth_token", "data": { "token": "eyJhbGciOiJIUzI1NiIs..." } }
```

**auth_refresh — 刷新 Token**
```json
{ "type": "auth_refresh", "data": {} }
```

**reconnect — 断线重连**
```json
{ "type": "reconnect", "data": { "session_token": "uuid", "room_id": "uuid" } }
```

#### 服务端 → 客户端

**auth_result — 认证结果**
```json
// 成功
{
  "type": "auth_result",
  "data": {
    "success": true,
    "user_id": 1,
    "username": "player1",
    "nickname": "象棋新手",
    "rating": 1500,
    "games_count": 0,
    "token": "eyJhbGci...",
    "expires_at": "2026-05-22T10:00:00Z",
    "session_token": "uuid-for-reconnect"
  }
}
// 失败
{
  "type": "auth_result",
  "data": {
    "success": false,
    "error": "invalid_credentials"   // invalid_credentials / username_exists / token_invalid / user_banned
  }
}
```

**kicked — 被踢出（重复登录）**
```json
{ "type": "kicked", "data": { "reason": "duplicate_login" } }
```

### 7.4 用户消息（详细）

**user_get_me → user_me**
```json
// 请求
{ "type": "user_get_me", "data": {} }
// 响应
{
  "type": "user_me",
  "data": {
    "user_id": 1,
    "username": "player1",
    "nickname": "象棋新手",
    "avatar": "https://...",
    "rating": 1580,
    "games_count": 25,
    "created_at": "2026-05-01T10:00:00Z"
  }
}
```

**user_get_rankings → user_rankings**
```json
// 请求
{ "type": "user_get_rankings", "data": { "page": 1, "page_size": 20 } }
// 响应
{
  "type": "user_rankings",
  "data": {
    "total": 1234,
    "page": 1,
    "page_size": 20,
    "rankings": [
      { "rank": 1, "user_id": 5, "username": "master", "rating": 2100, "games_count": 500 }
    ]
  }
}
```

**user_get_history → user_history**
```json
// 请求
{ "type": "user_get_history", "data": { "page": 1, "page_size": 20, "type": "pvp" } }
// 响应
{
  "type": "user_history",
  "data": {
    "total": 50,
    "history": [
      {
        "game_id": "uuid",
        "result": "win",
        "my_side": "red",
        "opponent": { "user_id": 2, "username": "player2", "rating": 1550 },
        "rating_change": 15,
        "total_moves": 82,
        "played_at": "2026-05-12T14:00:00Z"
      }
    ]
  }
}
```

**rating_update — 积分变化通知（对局结束后推送）**
```json
{
  "type": "rating_update",
  "data": { "change": 15, "new_rating": 1515, "game_id": "uuid" }
}
```

### 7.5 房间消息（详细）

**room_create → room_created**
```json
// 请求
{ "type": "room_create", "data": {} }
// 响应
{
  "type": "room_created",
  "data": {
    "room_id": "uuid",
    "your_side": "red",
    "status": "waiting"
  }
}
```

**room_list → room_list**
```json
// 请求
{ "type": "room_list", "data": {} }
// 响应
{
  "type": "room_list",
  "data": {
    "rooms": [
      {
        "room_id": "uuid",
        "red_player": { "user_id": 2, "username": "player2", "rating": 1550 },
        "created_at": "2026-05-12T14:00:00Z"
      }
    ]
  }
}
```

**room_join — 加入房间**
```json
// 请求
{ "type": "room_join", "data": { "room_id": "uuid" } }
// 加入后由 RoomManager 广播 game_start（见 7.6）
```

**room_leave — 离开房间**
```json
{ "type": "room_leave", "data": {} }
```

### 7.6 游戏消息（详细）

**game_start — 对局开始（服务端推送）**
```json
{
  "type": "game_start",
  "data": {
    "room_id": "uuid",
    "game_type": "pvp",
    "your_side": "red",
    "opponent": { "user_id": 2, "username": "player2", "rating": 1550 }
  }
}
```

**game_move — 玩家落子**
```json
{ "type": "game_move", "data": { "from": "e10", "to": "e9" } }

**opponent_ready — 对手已准备（服务端推送）**
```json
{ "type": "opponent_ready", "data": { "user_id": 123 } }
```
说明：当对手为 AI 或通过其它客户端自动 ready 时，服务端会通知在线的人类玩家对手已就绪。

**opponent_rematch — 对手请求再来一局（服务端推送）**
```json
{ "type": "opponent_rematch", "data": { "user_id": 123 } }
```
说明：对手发起 rematch（或 AI 自动 rematch）时发出通知。客户端可显示“对手想再来一局”的提示。
```

**move_result — 着法结果（服务端推送）**
```json
{
  "type": "move_result",
  "data": {
    "player": "red",
    "from": "e10",
    "to": "e9",
    "captured": 0,
    "move_no": 1,
    "check": false
  }
}
```

**ai_thinking / ai_move — AI 对局**
```json
{ "type": "ai_thinking", "data": {} }
{ "type": "ai_move", "data": { "from": "a0", "to": "a2", "captured": 0, "move_no": 2 } }
```

**game_over — 对局结束（服务端推送）**
```json
{
  "type": "game_over",
  "data": {
    "room_id": "uuid",
    "winner": "red",
    "result": 1,
    "reason": "checkmate",
    "total_moves": 82
  }
}

  补充：在 `game_over` 后客户端可以选择发送 `game_rematch` 来请求再来一局。服务端在 `FINISHED` 状态会等待双方 rematch（等待时长由服务配置 `rematch_timeout` 决定），满足条件后服务端会交换颜色并开始下一局；若超时则回退到 `WAITING` 状态。
```

**game_resign / game_draw_req / game_draw_ans**
```json
{ "type": "game_resign", "data": {} }
{ "type": "game_draw_req", "data": {} }
{ "type": "game_draw_ans", "data": { "accept": true } }
```

**draw_request — 和棋请求通知（服务端推送）**
```json
{ "type": "draw_request", "data": { "from": "black" } }
```

**draw_answered — 和棋应答通知（服务端推送）**
```json
{ "type": "draw_answered", "data": { "from": "red", "accept": false } }
```

**opponent_left / opponent_rejoin**
```json
{ "type": "opponent_left", "data": { "reason": "disconnect", "timeout": 60 } }
{ "type": "opponent_rejoin", "data": { "username": "player2" } }
```

**opponent_ready — 对手准备通知（服务端推送）**
```json
{ "type": "opponent_ready", "data": { "user_id": 0 } }
```

**opponent_rematch — 对手发起续局（服务端推送）**
```json
{ "type": "opponent_rematch", "data": { "user_id": 0 } }
```

这些消息用于 READY / FINISHED 流程中通知对手的就绪或续局意向。机器人通常使用约定的 `user_id`（例如 `0`）来标识。

**state_sync — 完整状态同步（断线重连后推送）**
```json
{
  "type": "state_sync",
  "data": {
    "room_id": "uuid",
    "board": [[14,13,...],[0,...],...],
    "current_turn": "red",
    "move_no": 15,
    "result": 0,
    "move_history": ["e10e9","a0a2",...],
    "your_side": "red",
    "remaining_time": 45
  }
}
```

### 7.7 匹配消息（详细）

**match_join → match_queued / match_found**
```json
// 请求
{ "type": "match_join", "data": {} }
// 已加入队列
{
  "type": "match_queued",
  "data": { "status": "queued", "rating": 1500 }
}
// 匹配成功（服务端推送）
{
  "type": "match_found",
  "data": {
    "room_id": "uuid",
    "your_side": "red",
    "opponent": { "user_id": 2, "username": "player2", "rating": 1520 }
  }
}
```

**match_leave → match_left**
```json
// 请求
{ "type": "match_leave", "data": {} }
// 响应
{ "type": "match_left", "data": { "status": "left" } }
```

### 7.8 管理后台消息（详细）

**admin_users → admin_users_result**
```json
{ "type": "admin_users", "data": { "page": 1, "page_size": 20, "search": "" } }
```

**admin_ban → admin_ban_result**
```json
{ "type": "admin_ban", "data": { "user_id": 5, "banned": true, "reason": "使用外挂" } }
```

**admin_stats → admin_stats_result**
```json
{ "type": "admin_stats", "data": {} }
```

**admin_models → admin_models_result**
```json
{ "type": "admin_models", "data": {} }
```

### 7.9 通用消息

**ping / pong**
```json
{ "type": "ping", "data": {} }
{ "type": "pong", "data": {} }
```

**error — 错误通知**
```json
{ "type": "error", "data": { "code": 3007, "message": "invalid move" } }
```

### 7.10 断线重连协议

```
1. 客户端断线，保留 session_token 和 room_id
2. 客户端重连，发送：
   { "type": "reconnect", "data": { "session_token": "...", "room_id": "..." } }
3. 服务端验证：
   - session_token 有效 → 房间仍在 PLAYING → 返回 state_sync
   - session_token 无效或房间已结束 → 返回 error { code: 4003 }
4. 客户端收到 state_sync 后恢复棋盘 UI
5. 重连超时 60s → 判负 → 对手收到 game_over
```

---

## 八、HTTP API 协议（仅保留健康检查）

> v2.0 架构取消 HTTP REST API，所有客户端通信通过 WebSocket 完成。
> 以下 HTTP 端点仅用于运维和内部调用。

### 8.1 健康检查

```
GET /health
→ { "status": "ok", "online_users": 45, "active_rooms": 12, "match_queue_size": 5 }
```

### 8.2 统一响应格式（v1.0 兼容，过渡期使用）

```json
{
  "code": 0,
  "message": "ok",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | int | 0=成功，非 0=失败 |
| `message` | string | 状态描述，失败时返回错误信息 |
| `data` | object/null | 响应数据，失败时为 null |

### 8.2 错误码定义

#### 系统级错误（1xxx）

| code | message | 说明 |
|---|---|---|
| 1000 | `"system error"` | 系统内部错误 |
| 1001 | `"service unavailable"` | 服务不可用 |
| 1002 | `"rate limit exceeded"` | 请求频率超限 |
| 1003 | `"invalid request"` | 请求格式错误 |
| 1004 | `"unauthorized"` | 未认证 |
| 1005 | `"forbidden"` | 无权限 |

#### 认证错误（2xxx）

| code | message | 说明 |
|---|---|---|
| 2001 | `"user not found"` | 用户不存在 |
| 2002 | `"invalid credentials"` | 密码错误 |
| 2003 | `"username already exists"` | 用户名已存在 |
| 2004 | `"token expired"` | Token 过期 |
| 2005 | `"token invalid"` | Token 无效 |

#### 房间/匹配错误（3xxx）

| code | message | 说明 |
|---|---|---|
| 3001 | `"room not found"` | 房间不存在 |
| 3002 | `"room full"` | 房间已满 |
| 3003 | `"room not waiting"` | 房间不在等待状态 |
| 3004 | `"already in room"` | 已在其他房间中 |
| 3005 | `"not in room"` | 不在任何房间 |
| 3006 | `"not your turn"` | 非当前回合 |
| 3007 | `"invalid move"` | 无效着法 |
| 3008 | `"not room owner"` | 非房主 |
| 3009 | `"opponent not ready"` | 对手未准备 |
| 3010 | `"match timeout"` | 匹配超时 |
| 3011 | `"user banned"` | 用户已被封禁 |

#### Game 服务错误（4xxx）

| code | message | 说明 |
|---|---|---|
| 4001 | `"invalid move"` | 着法不合法 |
| 4002 | `"not your turn"` | 当前不是你的回合 |
| 4003 | `"reconnect failed"` | 断线重连失败 |
| 4004 | `"game already started"` | 游戏已开始 |
| 4005 | `"game already finished"` | 游戏已结束 |
| 4006 | `"ai timeout"` | AI 推理超时 |
| 4007 | `"invalid difficulty"` | 无效难度等级 |

---

## 九、Redis 数据结构（ELO 匹配队列）

### 9.1 匹配队列

使用 Redis Sorted Set 存储匹配等待队列：

```
Key: match:pvp:waiting
Score: 玩家 ELO 积分（用于按积分排序）
Member: JSON 字符串
  {
    "user_id": 123,
    "username": "player1",
    "rating": 1500,
    "ws_session_id": "uuid",
    "joined_at": 1715500000
  }
```

### 9.2 房间状态缓存

```
Key: room:{room_id}:state
Type: String（JSON）
TTL: 24h（对局结束后清理）
```

---

## 十、着法存档格式

```json
{
  "game_id": "uuid",
  "total_moves": 82,
  "winner": "red",
  "result": 1,
  "start_time": "2026-05-12T10:00:00Z",
  "end_time": "2026-05-12T10:30:00Z",
  "moves": [
    { "no": 1,  "player": "red",   "from": "i9", "to": "i7", "piece": "r" },
    { "no": 2,  "player": "black", "from": "a9", "to": "a7", "piece": "r" },
    { "no": 3,  "player": "red",   "from": "h8", "to": "i10","piece": "n" }
  ]
}
```

---

## 十一、AI 棋盘特征编码

### 11.1 多通道输入张量

棋盘 10×9 = 90 格，用多个通道表示不同特征：

| 通道 | 内容 | 尺寸 |
|---|---|---|
| 0-1 | 红方棋子（K,R,N,B,A,P） | 6 通道 |
| 2-3 | 黑方棋子（K,R,N,B,A,P） | 6 通道 |
| 4 | 红方回合标记（全 1） | 1 通道 |
| 5-6 | 历史着法（重复局面检测） | 2 通道 |
| 7 | 红方皇宫区域（士/帅活动范围）| 1 通道 |
| 8 | 黑方皇宫区域 | 1 通道 |
| 9 | 兵/卒过河标记 | 1 通道 |
| **合计** | | **18 通道** |

```
输入张量形状: (batch, 18, 10, 9)
```

### 11.2 棋子位置编码

```python
import torch

def encode_board(board: list[list[int]]) -> torch.Tensor:
    """
    board: 10x9 数组，每格为 0(空) 或棋子编码(color*10+type)
    返回: (18, 10, 9) 张量
    """
    channels = []

    # 红方棋子（6 种类型 × 1 通道）
    for ptype in range(6):
        ch = torch.zeros((10, 9))
        for r in range(10):
            for c in range(9):
                if board[r][c] // 10 == 1 and board[r][c] % 10 == ptype:
                    ch[r, c] = 1.0
        channels.append(ch)

    # 黑方棋子（6 种类型 × 1 通道）
    for ptype in range(6):
        ch = torch.zeros((10, 9))
        for r in range(10):
            for c in range(9):
                if board[r][c] // 10 == 2 and board[r][c] % 10 == ptype:
                    ch[r, c] = 1.0
        channels.append(ch)

    # 红方回合（全 1）
    channels.append(torch.ones(10, 9))

    # 历史着法（初始全 0）
    channels.append(torch.zeros(10, 9))
    channels.append(torch.zeros(10, 9))

    # 皇宫区域
    red_palace = torch.zeros(10, 9)
    red_palace[7:10, 3:6] = 1.0
    channels.append(red_palace)

    black_palace = torch.zeros(10, 9)
    black_palace[0:3, 3:6] = 1.0
    channels.append(black_palace)

    # 过河标记
    crossed = torch.zeros(10, 9)
    for r in range(10):
        for c in range(9):
            if board[r][c] != 0:
                color = board[r][c] // 10
                ptype = board[r][c] % 10
                if ptype == 6:  # 兵/卒
                    if (color == 1 and r < 5) or (color == 2 and r > 4):
                        crossed[r, c] = 1.0
    channels.append(crossed)

    return torch.stack(channels)  # (18, 10, 9)
```

### 11.3 着法索引（Policy Head 输出）

全连接层输出 2085 维向量（10×9×9×9 映射的稀疏表示）：

```python
# 着法数量上限：每个位置最多 9 个方向，每方向最多 9 格
MAX_MOVES = 90 * 9 * 9 = 7290  # 实际中国象棋远少于这个数

# 简化实现：枚举所有合法着法，按索引对应
# 索引 = from_col * 9 * 9 + from_row * 9 + to_col * 9 + to_row
def move_to_idx(move: Move) -> int:
    return move.from_col * 81 + move.from_row * 9 + move.to_col * 9 + move.to_row

def idx_to_move(idx: int) -> Move:
    to_row = idx % 9
    col = (idx // 9) % 9
    from_col = idx // 81
    from_row = (idx // 9) // 9
    return Move(from_col, from_row, col, to_row)
```

---

## 十二、服务间通信协议

> v2.0 架构中，Game 服务是统一服务，不再有 Web→Game 的服务间通信。
> 对局结果直接写入数据库，无需 HTTP 回调。

### 12.1 Game 服务内部（无服务间调用）

```
所有业务逻辑在 Game 服务内部完成：
- 房间创建、匹配、对局、结算 → RoomManager
- ELO 积分更新 → EloService（直接写 DB）
- 对局记录保存 → 直接写 DB

无需 HTTP 回调，无需 gRPC
```

### 12.2 训练服务 → Game 服务（模型热加载通知）

训练服务完成新模型训练后，通过信号文件或 HTTP 通知 Game 服务热加载模型：

```http
POST /internal/model/reload
Content-Type: application/json
X-Internal-Key: {INTERNAL_SECRET}

{
  "model_path": "./models/v1.2.3.pt",
  "version": "v1.2.3",
  "elo_score": 2850
}
```

### 12.3 旧 Web 服务通信（过渡期，验证后移除）

```http
POST /internal/game/assign
Content-Type: application/json
X-Internal-Key: {INTERNAL_SECRET}

⚠️ 过渡期使用，新服务完成后移除
```
