# 中国象棋对战游戏 — 系统架构设计文档

> 文档版本：v1.0
> 创建时间：2026-05-12
> 状态：初稿，待评审

---

## 一、需求概述

### 1.1 功能需求

| 需求 | 说明 |
|---|---|
| 双人对战 | 两人通过 Web 浏览器实时对战 |
| 人机对战 | 玩家选择难度，与 AI 对弈 |
| 房间功能 | 开房间、自动进入等待中的房间 |
| ELO 匹配 | 人人对战时根据积分匹配实力相当的对手 |
| AI 多难度 | 根据玩家选择提供不同难度的 AI |
| Web 管理后台 | 后台管理人员查看数据、管理 AI 模型 |
| 可自我学习的 AI | 服务器空闲时通过自我对弈提升水平 |

### 1.2 非功能需求

- 单台 Linux 服务器部署
- Web 端通过 API 分配对局，对局后端独立运行
- AI 强化学习方向（AlphaZero 风格）

---

## 二、系统整体架构

### 2.1 服务划分

系统分为三大独立服务：

```
┌─────────────────────────────────────────────────────┐
│                   玩家浏览器（Web）                    │
│              HTTP REST + WebSocket                    │
└────────────────────────┬──────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│   Web 服务      │ │  Game 服务     │ │  训练服务      │
│   （Go）        │ │  （Python）    │ │  （Python）    │
│                │ │               │ │               │
│ 用户 / 房间     │ │ 实时对局引擎   │ │ 自对弈 / 训练  │
│ 匹配 / 积分     │ │ MCTS + NN     │ │ 模型更新       │
│ 管理后台 API    │ │ 推理          │ │               │
└────────────────┘ └───────┬───────┘ └───────────────┘
                            │
                            ▼
                   ┌────────────────┐
                   │  PostgreSQL    │
                   │                │
                   │ 用户 / 积分     │
                   │ 对局记录        │
                   │ 训练数据       │
                   │ 模型版本        │
                   └────────────────┘
```

### 2.2 服务职责

| 服务 | 技术栈 | 职责 |
|---|---|---|
| **Web 服务** | Go + Gin/Echo + PostgreSQL | 用户认证、房间管理、ELO 匹配、管理后台、对局分配 |
| **Game 服务** | Python + FastAPI + asyncio + PyTorch | 实时对局引擎、棋盘规则、胜负判定、AI 推理调用 |
| **训练服务** | Python + PyTorch | 自对弈数据生成、神经网络训练、模型验证与发布 |

### 2.3 服务间通信

```
客户端  ←→  Web 服务（Go）
  │          ├── HTTP REST（用户操作、房间管理）
  │          └── WebSocket（房间状态轮询 / 对局分配结果）

  │  Web 服务分配对局后返回 Game 服务地址和房间 token

客户端  ←→  Game 服务（Python）
               WebSocket（实时对局：落子、超时、认输、和棋请求）

Game 服务  →  Web 服务（Go）
               HTTP 回调（对局结束 → 更新 ELO → 写入战绩）

Game 服务  →  AI 推理（Python 进程内调用，无网络开销）
               共享 PyTorch 模型，MCTS 推理
```

---

## 三、Web 服务架构（Go）

### 3.1 技术选型

- **框架**：Gin 或 Echo（轻量、高性能）
- **数据库**：PostgreSQL（用户数据、积分、房间、战绩）
- **认证**：JWT（无状态，便于水平扩展）
- **通信**：HTTP REST + WebSocket

### 3.2 模块划分

```
HTTP Server（Gin 框架）
├── 认证中间件（JWT 校验 / 限流）
│
├── 用户 & 认证模块
│   ├── POST /auth/register          用户注册
│   ├── POST /auth/login             登录 → JWT
│   ├── GET  /users/me               当前用户信息
│   ├── PATCH /users/me              修改个人信息
│   └── GET  /users/rankings         积分排行榜
│
├── 房间 & 匹配模块
│   ├── POST /rooms                  创建房间（人人对战）
│   ├── GET  /rooms                  查询等待中的房间列表
│   ├── POST /rooms/:id/join         加入房间
│   ├── POST /rooms/:id/ready        玩家就绪
│   ├── POST /match/pvp               ELO 匹配（加入匹配队列）
│   └── POST /match/pve/:level       人机对战（直接分配 Game 服务）
│
├── 管理后台模块（Admin JWT 权限）
│   ├── GET  /admin/users             用户列表
│   ├── PATCH /admin/users/:id/ban    封禁用户
│   ├── GET  /admin/stats             全局运营数据
│   ├── POST /admin/models/upload     上传新 AI 模型
│   ├── PATCH /admin/models/:id/publish  发布模型（替换在线模型）
│   └── GET  /admin/models            模型版本列表
│
└── 业务逻辑层
    ├── UserService      用户 / 积分 / ELO 计算
    ├── RoomService      房间 CRUD / 等待队列
    └── GameProxy        对局分配 / 结果回调
```

### 3.3 ELO 匹配算法

匹配流程：
1. 玩家调用 `POST /match/pvp`，携带自己的 ELO 积分
2. Web 服务将玩家加入匹配队列（Redis Sorted Set 或内存队列）
3. 后台 goroutine 定期扫描队列，匹配积分差值在阈值内的两位玩家
4. 匹配成功后，调用 Game 服务创建房间，WebSocket 通知双方进入对局

```
阈值策略：
  - 初始玩家（games_count < 5）：差值放宽至 200
  - 正常玩家：差值 100 以内
  - 高分玩家（rating > 2000）：差值 150 以内
  - 超时未匹配：逐步放宽阈值
```

---

## 四、游戏对局服务架构（Python）

### 4.1 技术选型

- **框架**：FastAPI + asyncio（异步网络、高并发）
- **WebSocket**：websockets 库（asyncio 原生）
- **棋盘引擎**：Python 实现（中国象棋规则、着法验证、胜负判定）
- **AI 推理**：PyTorch 模型 + MCTS 搜索
- **进程内调用**：AI 推理与 Game 服务在同一进程，零网络开销

### 4.2 模块划分

```
WebSocket Gateway（FastAPI / websockets）
├── 连接管理（协程映射 / 心跳检测 / 断线超时）
├── 消息路由（落子 / 悔棋 / 认输 / 和棋请求）
└── 断线重连（token 验证 + 状态恢复）

RoomManager（asyncio Task 池）
├── 每个房间独立协程
├── 定时器管理（思考超时 / 回合超时）
├── 断线检测（玩家断线 → 等待重连 / 超时判负）
└── 房间销毁（对局结束 → 写入战绩 → 清理资源）

ChessGame（棋盘状态机）— PvP / PvE 共用
├── 棋盘表示（10×9 二维数组 / 位棋盘）
├── MoveValidator（走法规则校验：将军/将帅照面/蹩马腿等）
├── WinChecker（胜负判定：困毙、将死）
└── GameRecorder（着法记录 → 存档）

AIProxy（人机对战专用）
├── 异步调用推理引擎（不阻塞其他房间）
├── DifficultyController（根据难度调整 MCTS 模拟次数）
└── 超时处理（AI 思考时间上限，强制返回最佳着法）
```

### 4.3 多难度实现

**共用同一个最强模型**，通过 MCTS 模拟次数控制难度：

| 难度 | MCTS 模拟次数 | 预期思考时间 | 对应水平 |
|---|---|---|---|
| 入门 | 50~100 | < 0.5s | 初学者 |
| 简单 | 100~200 | 0.5~1s | 业余初级 |
| 中等 | 400~800 | 2~5s | 业余高手 |
| 困难 | 1600~3200 | 10~20s | 高手 |
| 大师 | 6400+ | 30s+ | 接近 AI 极限 |

> 初期可以先用传统 Minimax + Alpha-Beta 剪枝作为基础 AI，后期替换为 RL 模型。

---

## 五、AI 服务架构（强化学习方向）

### 5.1 技术选型

- **深度学习框架**：PyTorch
- **强化学习算法**：AlphaZero 风格（MCTS + 神经网络）
- **棋盘表示**：卷积神经网络输入（将棋盘编码为多通道张量）
- **训练硬件**：单台服务器，GPU 可选（CPU 可行，训练速度较慢）

### 5.2 AlphaZero 风格自学习闭环

```
┌─────────────────────────────────────────────────────────┐
│                    训练循环（后台离线）                    │
│                                                         │
│  自对弈引擎 ──→ Replay Buffer ──→ 神经网络训练            │
│   (MCTS+NN)                      (梯度更新)            │
│       │                                  │               │
│       └──────────────────────────────────┘               │
│              定期生成新模型 → Elo 验证 → 热更新            │
└─────────────────────────────────────────────────────────┘
                          │
                          │ 共享模型文件（热加载）
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    推理循环（实时在线）                    │
│                                                         │
│  Game 服务 ──→ AIProxy ──→ MCTS 推理引擎                 │
│  (玩家落子)      (难度控制)   (NN 评估 + 搜索)            │
└─────────────────────────────────────────────────────────┘
```

### 5.3 自对弈数据生成

```
每局自对弈生成的数据（存入 Replay Buffer）：
{
  "model_version": "v1.2.3",
  "moves": [
    {"state": [10,9,1,...], "pi": [0.1, 0.05, ...], "z": 1},  // 红方胜
    {"state": [...], "pi": [...], "z": -1},                    // 黑方视角
  ],
  "winner": "red"
}
```

### 5.4 模型训练流程

```
1. 从 Replay Buffer 采样批量数据
2. 神经网络前向传播，计算策略头（π）和价值头（v）
3. 损失函数：L = (z - v)² - π · log(π_pred) + λ||θ||²
4. Adam 优化器梯度更新
5. 每 N 局自对弈后生成新模型
6. 新模型与旧模型 Elo 对比评测：
   - 新模型 Elo 更高 → 替换为在线模型
   - 新模型 Elo 更低 → 保留旧模型（可回滚）
```

### 5.5 训练调度策略

- **触发条件**：服务器 CPU 空闲 + Replay Buffer 积累足够数据（建议 > 10,000 局）
- **训练间隔**：每小时检查一次，满足条件则启动训练
- **后台运行**：训练进程与 Game 进程隔离，共享模型文件
- **热更新**：训练完成后通过信号量通知推理服务重新加载模型

---

## 六、数据库设计（PostgreSQL）

### 6.1 核心表结构

```sql
-- 用户表
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    username    VARCHAR(32) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW(),
    is_banned   BOOLEAN DEFAULT FALSE
);

-- ELO 积分表
CREATE TABLE elo_ratings (
    user_id     BIGINT PRIMARY KEY REFERENCES users(id),
    rating      INTEGER DEFAULT 1500,
    games_count INTEGER DEFAULT 0,
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- 房间表
CREATE TABLE rooms (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type        VARCHAR(8)  CHECK (type IN ('pvp', 'pve')),
    status      VARCHAR(16) CHECK (status IN ('waiting', 'playing', 'finished')),
    difficulty  INTEGER,                    -- PvE 难度等级，1-5
    red_user_id BIGINT REFERENCES users(id),
    black_user_id BIGINT REFERENCES users(id),
    winner      VARCHAR(8),                  -- 'red' / 'black' / 'draw'
    created_at  TIMESTAMP DEFAULT NOW(),
    started_at  TIMESTAMP,
    ended_at    TIMESTAMP
);

-- 对局记录
CREATE TABLE game_history (
    id          BIGSERIAL PRIMARY KEY,
    room_id     UUID REFERENCES rooms(id),
    winner      VARCHAR(8) NOT NULL,
    total_moves INTEGER NOT NULL,
    start_time  TIMESTAMP NOT NULL,
    end_time    TIMESTAMP NOT NULL,
    pve_level   INTEGER                       -- PvE 时记录 AI 难度
);

-- 着法记录
CREATE TABLE moves (
    id          BIGSERIAL PRIMARY KEY,
    game_id     BIGINT REFERENCES game_history(id),
    move_no     INTEGER NOT NULL,
    player      VARCHAR(8) CHECK (player IN ('red', 'black')),
    from_pos    VARCHAR(4) NOT NULL,          -- "e1"
    to_pos      VARCHAR(4) NOT NULL,          -- "e2"
    move_uci    VARCHAR(8),                   -- 完整着法编码
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 自对弈数据（训练用）
CREATE TABLE selfplay_games (
    id            BIGSERIAL PRIMARY KEY,
    model_version VARCHAR(32) NOT NULL,
    winner        VARCHAR(8) NOT NULL,
    total_moves   INTEGER NOT NULL,
    moves_json    JSONB NOT NULL,             -- 完整着法序列
    created_at    TIMESTAMP DEFAULT NOW()
);

-- AI 模型版本
CREATE TABLE model_versions (
    id          BIGSERIAL PRIMARY KEY,
    version     VARCHAR(32) UNIQUE NOT NULL,
    model_path  VARCHAR(255) NOT NULL,
    elo_score   INTEGER,
    status      VARCHAR(16) CHECK (status IN ('training', 'validating', 'online', 'archived')),
    note        TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 用户历史积分（便于查看积分变化曲线）
CREATE TABLE elo_history (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(id),
    rating      INTEGER NOT NULL,
    change      INTEGER NOT NULL,
    game_id     BIGINT REFERENCES game_history(id),
    created_at  TIMESTAMP DEFAULT NOW()
);
```

### 6.2 索引

```sql
CREATE INDEX idx_elo_ratings_rating ON elo_ratings(rating DESC);
CREATE INDEX idx_rooms_status ON rooms(status) WHERE status IN ('waiting', 'playing');
CREATE INDEX idx_game_history_room_id ON game_history(room_id);
CREATE INDEX idx_moves_game_id ON moves(game_id);
CREATE INDEX idx_selfplay_games_version ON selfplay_games(model_version);
CREATE INDEX idx_elo_history_user_id ON elo_history(user_id, created_at DESC);
```

---

## 七、WebSocket 协议设计

### 7.1 消息格式（JSON）

```json
// 客户端 → Game 服务（玩家操作）
{ "type": "move",    "data": { "from": "e1", "to": "e2" } }
{ "type": "resign",  "data": {} }
{ "type": "draw_req","data": {} }
{ "type": "draw_ans","data": { "accept": true } }

// Game 服务 → 客户端（状态推送）
{ "type": "move_result",   "data": { "player": "red", "from": "e1", "to": "e2", "captured": "p1" } }
{ "type": "game_start",    "data": { "room_id": "...", "your_side": "red" } }
{ "type": "game_over",     "data": { "winner": "red", "reason": "checkmate" } }
{ "type": "opponent_left","data": { "reason": "disconnect" } }
{ "type": "ai_thinking",   "data": {} }          // AI 正在思考
{ "type": "draw_request",  "data": { "from": "black" } }
```

### 7.2 断线重连

1. 客户端断线后保留 `session_token`
2. 重新连接时携带 `session_token` + `room_id`
3. Game 服务验证 token 有效且房间仍在进行
4. 推送完整棋盘状态 + 剩余思考时间
5. 超时未重连（60s）则判负

---

## 八、部署架构（单台 Linux 服务器）

```
┌─────────────────────────────────────────────┐
│                  Linux 服务器                 │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Web 服务  │  │ Game 服务  │  │ 训练服务  │ │
│  │  (Go)     │  │ (Python)  │  │ (Python) │ │
│  │  :8080    │  │  :8081    │  │ 后台进程  │ │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘ │
│        │              │              │       │
│        └──────────────┼──────────────┘       │
│                       │                      │
│                 ┌─────┴─────┐                │
│                 │ PostgreSQL │                │
│                 │   :5432    │                │
│                 └───────────┘                │
└─────────────────────────────────────────────┘

Nginx（反向代理）
├── /api/*        → Web 服务 :8080
├── /ws/*         → Game 服务 :8081
└── /admin/*      → Web 服务 :8080（Admin 专用）
```

### 8.1 进程管理

- 使用 **systemd** 管理各服务进程（自动重启、开机自启）
- 或使用 **Docker Compose** 容器化部署（推荐，便于环境隔离）

### 8.2 目录结构

```
/opt/chinese-chess/
├── web-service/           # Go Web 服务
│   ├── main
│   ├── config.yaml
│   └── migrations/         # SQL 迁移脚本
├── game-service/          # Python Game 服务
│   ├── main.py
│   ├── chess_engine/      # 棋盘引擎
│   ├── ai/                # AI 推理模块
│   └── config.yaml
├── training/              # Python 训练服务
│   ├── selfplay.py
│   ├── train.py
│   └── models/            # 模型文件目录
├── data/
│   ├── postgres/          # PostgreSQL 数据目录
│   └── selfplay_games/    # 自对弈存档
└── nginx.conf
```

---

## 九、技术选型汇总

| 模块 | 选型 | 理由 |
|---|---|---|
| Web 前端 | Vue 3 + Vite | 响应式、组件化、生态成熟 |
| Web 后端 | Go + Gin | 高并发、低内存、部署简单 |
| 游戏对局 | Python + FastAPI + asyncio | AI 原生集成、异步高并发 |
| AI 推理/训练 | Python + PyTorch | 强化学习标准技术栈 |
| 数据库 | PostgreSQL | 全功能关系型数据库 |
| 网络协议 | WebSocket + JSON | 实时双向、低延迟 |
| 进程管理 | systemd / Docker Compose | 单机部署首选 |
| 消息队列 | 无（单机直连） | 单机部署无需额外队列 |

---

## 十、关键设计决策

### 决策 1：Web 服务与 Game 服务分离

**理由**：
- 关注点分离：Web 服务专注业务逻辑，Game 服务专注实时对局
- 独立扩缩容：人人对战负载和 AI 推理负载可独立管理
- 故障隔离：Game 服务崩溃不影响用户登录、注册等基础功能
- 技术栈最优：Go 写 API 高效，Python 写 AI 无缝集成 PyTorch

### 决策 2：AI 多难度通过 MCTS 模拟次数实现

**理由**：
- 只训练一个模型，部署和维护成本最低
- 不同难度使用不同模拟次数，简单直接
- 难度参数可动态调整，无需重新训练

### 决策 3：先传统 AI 后强化学习

**理由**：
- Phase 1：传统 Minimax + Alpha-Beta 剪枝，快速出可玩版本，验证整个系统
- Phase 2：当自我对弈积累足够数据后，用 AlphaZero 风格替换，逐步提升 AI 水平
- 降低初期复杂度，加快 MVP 交付

---

## 十一、后续事项

- [ ] 评审并确认架构方案
- [ ] 确定前端具体技术栈（Vue 3 或其他）
- [ ] 设计 AI 棋盘表示（输入层编码方案）
- [ ] 制定 AI 训练数据量目标和训练计划
- [ ] 规划 MVP 交付优先级（先出什么功能）
