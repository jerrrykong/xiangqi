# 通用协议与数据结构设计

> 所属服务：Web 服务 / Game 服务 / AI 服务（共用）
> 文档版本：v1.0

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

## 七、WebSocket 消息协议

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

### 7.2 客户端 → Game 服务（玩家操作）

| type | data | 说明 |
|---|---|---|
| `move` | `{ "from": "e10", "to": "e9" }` | 玩家落子 |
| `resign` | `{}` | 认输 |
| `draw_req` | `{}` | 请求和棋 |
| `draw_ans` | `{ "accept": true }` | 和棋应答 |
| `chat` | `{ "content": "你好" }` | 聊天消息 |
| `ping` | `{}` | 心跳 ping |

### 7.3 Game 服务 → 客户端（状态推送）

| type | data | 说明 |
|---|---|---|
| `game_start` | `{ "room_id": "...", "your_side": "red" }` | 对局开始 |
| `move_result` | `{ "player": "red", "from": "e10", "to": "e9", "captured": 0, "check": false }` | 着法结果 |
| `opponent_move` | `{ "player": "black", "from": "a0", "to": "a2", "captured": 0, "check": false }` | 对手落子通知（game_start 后的前两条） |
| `game_over` | `{ "winner": "red", "result": 1, "reason": "checkmate" }` | 对局结束 |
| `opponent_left` | `{ "reason": "disconnect", "timeout": 60 }` | 对手断线 |
| `opponent_rejoin` | `{ "username": "player2" }` | 对手重连 |
| `draw_request` | `{ "from": "black" }` | 收到和棋请求 |
| `draw_answered` | `{ "from": "red", "accept": false }` | 和棋应答通知 |
| `ai_thinking` | `{}` | AI 正在思考（人机对战） |
| `ai_move` | `{ "from": "a0", "to": "a2", "captured": 0 }` | AI 落子 |
| `timeout_warning` | `{ "remaining": 10 }` | 超时预警（剩余秒数） |
| `error` | `{ "code": 4001, "message": "invalid move" }` | 错误通知 |
| `pong` | `{}` | 心跳 pong |
| `state_sync` | `{ "board": [...], "turn": "red", "move_no": 5, ... }` | 状态同步（断线重连后） |

### 7.4 断线重连协议

```
1. 客户端断线，保留 session_token 和 room_id
2. 客户端重连，发送：
   { "type": "reconnect", "data": { "token": "...", "room_id": "..." } }
3. Game 服务验证：
   - token 有效 → 房间仍在进行 → 返回 state_sync（完整状态）
   - token 无效或房间已结束 → 返回 error { code: 4003 }
4. 客户端收到 state_sync 后恢复棋盘 UI
```

---

## 八、HTTP API 协议

### 8.1 统一响应格式

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

### 12.1 Web 服务 → Game 服务（HTTP 回调）

```http
POST /internal/game/assign
Content-Type: application/json
X-Internal-Key: {INTERNAL_SECRET}

{
  "room_id": "uuid",
  "game_type": "pvp",
  "players": [
    { "user_id": 1, "username": "red_player", "side": "red", "ws_session": "uuid1" },
    { "user_id": 2, "username": "black_player", "side": "black", "ws_session": "uuid2" }
  ],
  "callback_url": "http://web-service:8080/internal/game/result"
}
```

### 12.2 Game 服务 → Web 服务（对局结束回调）

```http
POST {callback_url}
Content-Type: application/json
X-Internal-Key: {INTERNAL_SECRET}

{
  "room_id": "uuid",
  "game_id": "uuid",
  "result": 1,
  "winner": "red",
  "red_user_id": 1,
  "black_user_id": 2,
  "total_moves": 82,
  "duration_seconds": 1800,
  "pve_level": null
}
```

### 12.3 内部 RPC（可选，gRPC）

```protobuf
syntax = "proto3";

service GameService {
    rpc AssignGame(AssignRequest) returns (AssignResponse);
    rpc ReportResult(GameResultRequest) returns (google.protobuf.Empty);
    rpc GetGameState(GameStateRequest) returns (GameStateResponse);
    rpc AIMove(AIMoveRequest) returns (AIMoveResponse);
}

message AssignRequest {
    string room_id = 1;
    string game_type = 2;  // "pvp" / "pve"
    repeated Player players = 3;
    int32 difficulty = 4;   // 1-5, PvE only
    string callback_url = 5;
}

message AIMoveRequest {
    string room_id = 1;
    int32 board_state = 2;  // serialized board
    int32 difficulty = 3;
}
```
