# 中国象棋对战游戏 — 系统架构设计文档

> 文档版本：v2.0
> 创建时间：2026-05-12
> 更新时间：2026-05-21
> 状态：v2.0 架构重构 — 合并 Web 服务到 Game 服务，全 WebSocket 通信

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
- **所有客户端通信统一使用 WebSocket 长连接**
- AI 强化学习方向（AlphaZero 风格）

---

## 二、系统整体架构（v2.0 重构）

### 2.1 架构变更说明

**v1.0 → v2.0 核心变更：**

1. **取消 Web 服务（Go）**：将 Web 服务的登录认证、用户管理、房间管理、ELO 匹配全部合并到 Game 服务（Python）
2. **房间与游戏合并**：房间模块直接承载完整的游戏过程，不再有独立的 Game 分配环节
3. **匹配即房间**：ELO 匹配成功后自动创建房间，跳过准备阶段，直接进入 Playing
4. **全 WebSocket 通信**：所有客户端与服务端的交互（认证、房间、匹配、对局）均通过 WebSocket 长连接完成，取消 HTTP REST API

> ⚠️ **过渡策略**：旧的 Go Web 服务暂且保留运行，直到新的 Game 服务完成开发和验证后再下线。

### 2.2 服务划分（新）

系统由两个服务组成：

```
┌─────────────────────────────────────────────────────┐
│                   玩家浏览器（Web）                    │
│                    WebSocket 长连接                    │
└────────────────────────┬──────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
┌──────────────────────┐ ┌──────────────────────┐
│   Game 服务（统一）    │ │   训练服务            │
│   （Python）          │ │   （Python）          │
│                      │ │                      │
│ 认证 / 用户 / 积分    │ │ 自对弈 / 训练         │
│ 房间 / 匹配 / 对局    │ │ 模型更新             │
│ 棋盘引擎 / AI 推理    │ │                      │
│ 管理后台              │ │                      │
└──────────┬───────────┘ └──────────┬───────────┘
           │                        │
           └────────────┬───────────┘
                        ▼
               ┌────────────────┐
               │  PostgreSQL    │
               │                │
               │ 用户 / 积分     │
               │ 房间 / 对局     │
               │ 训练数据       │
               │ 模型版本        │
               └────────────────┘
```

### 2.3 服务职责（新）

| 服务 | 技术栈 | 职责 |
|---|---|---|
| **Game 服务（统一）** | Python + FastAPI + asyncio + PostgreSQL + PyTorch | 用户认证、房间管理、ELO 匹配、实时对局、棋盘规则、AI 推理、管理后台 |
| **训练服务** | Python + PyTorch | 自对弈数据生成、神经网络训练、模型验证与发布 |

### 2.4 通信方式（新）

```
客户端  ←→  Game 服务（Python）— 全 WebSocket 通信
               ├── 认证（登录 / 注册 / Token 刷新）
               ├── 用户（个人信息 / 排行榜 / 战绩）
               ├── 房间（创建 / 加入 / 离开 / 房间列表）
               ├── 匹配（加入队列 / 离开队列）
               ├── 对局（落子 / 认输 / 和棋 / 断线重连）
               └── 管理后台（用户管理 / 模型管理 / 运营数据）

Game 服务  →  AI 推理（Python 进程内调用，无网络开销）
               共享 PyTorch 模型，MCTS 推理

训练服务  →  Game 服务（共享模型文件，热加载通知）
```

### 2.5 旧 Web 服务（过渡期）

```
客户端  ←→  旧 Web 服务（Go）— 仍然运行，但不再新增功能
               HTTP REST（用户操作、房间管理）
               WebSocket（房间状态轮询）

⚠️ 过渡期结束后将下线此服务
```

---

## 三、Game 服务架构（统一服务 — Python）

### 3.1 技术选型

- **框架**：FastAPI + asyncio（异步网络、高并发）
- **WebSocket**：FastAPI 内置 WebSocket 支持
- **数据库**：PostgreSQL + asyncpg（异步数据库驱动）+ SQLAlchemy/GINO
- **认证**：JWT（无状态，WebSocket 连接时验证）
- **AI 推理**：PyTorch 模型 + MCTS 搜索（进程内调用）
- **通信协议**：**全部使用 WebSocket**，仅保留极少 HTTP 端点（健康检查、静态资源）

### 3.2 模块划分

```
Game 服务（统一）
├── WebSocket Gateway
│   ├── 连接管理器（ConnectionManager）
│   │   ├── 连接生命周期（建立、认证、心跳、断开）
│   │   ├── 连接状态机（UNAUTHENTICATED → AUTHENTICATED → IN_LOBBY / IN_ROOM / MATCHMAKING）
│   │   └── 断线重连（session_token 验证 + 状态恢复）
│   └── 消息路由器（MessageRouter）
│       ├── auth    → AuthHandler
│       ├── user    → UserHandler
│       ├── room    → RoomHandler
│       ├── match   → MatchHandler
│       ├── game    → GameHandler
│       └── admin   → AdminHandler
│
├── 认证模块（AuthModule）
│   ├── AuthService      登录 / 注册 / Token 生成与验证
│   ├── JWTManager       JWT 编解码 / 刷新
│   └── 密码加密（bcrypt）
│
├── 用户模块（UserModule）
│   ├── UserService      用户信息 / 积分 / ELO 计算
│   └── UserRepository   用户数据访问
│
├── 房间模块（RoomModule）— 统一房间 + 游戏
│   ├── RoomService      房间创建 / 加入 / 离开 / 列表查询
│   ├── RoomManager      房间生命周期管理（内存中活跃房间）
│   ├── Room             房间对象（包含游戏状态，完整游戏流程）
│   ├── PlayerSession    玩家连接会话
│   └── 计时器管理（思考超时 / 回合超时）
│
├── 匹配模块（MatchModule）
│   ├── MatchService     ELO 匹配引擎（后台匹配循环）
│   └── MatchQueue       匹配队列（内存 SortedSet）
│
├── 棋盘引擎（ChessEngine）— 复用
│   ├── Board            棋盘数据结构
│   ├── MoveGenerator    合法着法生成
│   ├── MoveValidator    着法验证
│   ├── WinChecker       胜负判定
│   └── GameState        游戏状态机
│
├── AI 推理模块（AIModule）— 复用
│   ├── AIProxy          AI 推理调用封装
│   └── DifficultyController 难度控制
│
├── 管理后台模块（AdminModule）
│   ├── AdminService     用户管理 / 模型管理 / 运营数据
│   └── AdminRepository  管理数据访问
│
└── 数据层
    ├── PostgreSQL       用户 / 积分 / 房间 / 对局记录
    └── 模型文件存储      AI 模型权重文件
```

### 3.3 WebSocket 连接状态机

```
客户端连接 WebSocket
       │
       ▼
  ┌──────────────┐
  │ UNAUTHENTICATED │ ← 未认证，只能发送 auth_* 消息
  └──────┬───────┘
         │ auth_login / auth_register / auth_token 成功
         ▼
  ┌──────────────┐
  │  AUTHENTICATED  │ ← 已认证，在大厅
  └──────┬───────┘
         │
    ┌────┼────────────┐
    │    │            │
    ▼    ▼            ▼
┌────────┐ ┌────────┐ ┌────────┐
│ IN_LOBBY│ │IN_ROOM │ │MATCHMAKING│
│ 浏览房间 │ │ 对局中  │ │ 匹配等待 │
└────┬───┘ └────┬───┘ └────┬───┘
     │          │          │
     │ room_join│ match_   │ match_found
     │          │ found    │ (自动→IN_ROOM)
     │          │          │
     └──────────┼──────────┘
                ▼
          ┌──────────┐
          │ IN_ROOM   │ ← 在房间中，发送 game_* 消息
          └─────┬────┘
                │ game_over / room_leave
                ▼
          ┌──────────┐
          │ IN_LOBBY  │ ← 回到大厅
          └──────────┘
```

### 3.4 ELO 匹配算法

匹配流程（全部通过 WebSocket）：
1. 玩家发送 `match_join` 消息
2. MatchService 将玩家加入匹配队列（内存 SortedSet，按 ELO 积分排序）
3. 后台 asyncio 协程定期扫描队列，匹配积分差值在阈值内的两位玩家
4. 匹配成功后：
   - 自动创建房间，分配红黑方
   - 房间状态直接设为 PLAYING（跳过准备阶段）
   - WebSocket 推送 `match_found` 给双方
   - 双方直接开始对局

```
阈值策略：
  - 初始玩家（games_count < 5）：差值放宽至 200
  - 正常玩家：差值 100 以内
  - 高分玩家（rating > 2000）：差值 150 以内
  - 超时未匹配：逐步放宽阈值（+50/30s）
  - 超时 180s：返回匹配超时错误
```

### 3.5 多难度实现

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

## 四、AI 服务架构（强化学习方向）

> 无变更，详见 [03-ai-service-design.md](03-ai-service-design.md)

### 4.1 AlphaZero 风格自学习闭环

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

---

## 五、数据库设计（PostgreSQL）

> 表结构基本不变，仅房间表调整（见标注）

### 5.1 核心表结构

```sql
-- 用户表
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    username    VARCHAR(32) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nickname    VARCHAR(64),
    avatar      VARCHAR(255),
    is_admin    BOOLEAN DEFAULT FALSE,
    is_banned   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);

-- ELO 积分表
CREATE TABLE elo_ratings (
    user_id     BIGINT PRIMARY KEY REFERENCES users(id),
    rating      INTEGER DEFAULT 1500,
    games_count INTEGER DEFAULT 0,
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- 房间表 [v2.0 变更] source 字段区分房间来源
CREATE TABLE rooms (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type        VARCHAR(8)  CHECK (type IN ('pvp', 'pve')),
    source      VARCHAR(16) CHECK (source IN ('manual', 'match')) DEFAULT 'manual',  -- [新增] manual=手动创建, match=匹配创建
    status      VARCHAR(16) CHECK (status IN ('waiting', 'playing', 'finished')),
    difficulty  INTEGER,                    -- PvE 难度等级，1-5
    red_user_id BIGINT REFERENCES users(id),
    black_user_id BIGINT REFERENCES users(id),
    winner      VARCHAR(8),                  -- 'red' / 'black' / 'draw'
    created_by  BIGINT REFERENCES users(id), -- [新增] 创建者
    created_at  TIMESTAMP DEFAULT NOW(),
    started_at  TIMESTAMP,
    ended_at    TIMESTAMP
);

-- 对局记录
CREATE TABLE game_history (
    id          BIGSERIAL PRIMARY KEY,
    room_id     UUID REFERENCES rooms(id),
    winner      VARCHAR(8) NOT NULL,
    result      INTEGER NOT NULL,              -- GameResult 枚举值
    total_moves INTEGER NOT NULL,
    start_time  TIMESTAMP NOT NULL,
    end_time    TIMESTAMP NOT NULL,
    pve_level   INTEGER,                       -- PvE 时记录 AI 难度
    red_user_id  BIGINT,
    black_user_id BIGINT,
    duration_seconds INTEGER                    -- [新增] 对局时长
);

-- 着法记录
CREATE TABLE moves (
    id          BIGSERIAL PRIMARY KEY,
    game_id     BIGINT REFERENCES game_history(id),
    move_no     INTEGER NOT NULL,
    player      VARCHAR(8) CHECK (player IN ('red', 'black')),
    from_pos    VARCHAR(4) NOT NULL,
    to_pos      VARCHAR(4) NOT NULL,
    move_uci    VARCHAR(8),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 自对弈数据（训练用）
CREATE TABLE selfplay_games (
    id            BIGSERIAL PRIMARY KEY,
    model_version VARCHAR(32) NOT NULL,
    winner        VARCHAR(8) NOT NULL,
    total_moves   INTEGER NOT NULL,
    moves_json    JSONB NOT NULL,
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

-- 用户历史积分
CREATE TABLE elo_history (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(id),
    rating      INTEGER NOT NULL,
    change      INTEGER NOT NULL,
    game_id     BIGINT REFERENCES game_history(id),
    created_at  TIMESTAMP DEFAULT NOW()
);
```

### 5.2 索引

```sql
CREATE INDEX idx_elo_ratings_rating ON elo_ratings(rating DESC);
CREATE INDEX idx_rooms_status ON rooms(status) WHERE status IN ('waiting', 'playing');
CREATE INDEX idx_rooms_source ON rooms(source);
CREATE INDEX idx_game_history_room_id ON game_history(room_id);
CREATE INDEX idx_moves_game_id ON moves(game_id);
CREATE INDEX idx_selfplay_games_version ON selfplay_games(model_version);
CREATE INDEX idx_elo_history_user_id ON elo_history(user_id, created_at DESC);
```

---

## 六、部署架构（单台 Linux 服务器）

```
┌─────────────────────────────────────────────┐
│                  Linux 服务器                 │
│                                             │
│  ┌──────────────────┐  ┌──────────────────┐ │
│  │ Game 服务（统一）  │  │   训练服务        │ │
│  │   (Python)       │  │   (Python)       │ │
│  │   :8080          │  │   后台进程        │ │
│  └────────┬─────────┘  └────────┬─────────┘ │
│           │                     │            │
│           └──────────┬──────────┘            │
│                      │                       │
│              ┌───────┴───────┐               │
│              │  PostgreSQL   │               │
│              │    :5432      │               │
│              └───────────────┘               │
└─────────────────────────────────────────────┘

Nginx（反向代理）
├── /ws           → Game 服务 :8080  （WebSocket）
├── /api/*        → 旧 Web 服务 :8081（过渡期）
└── /             → 前端静态文件
```

### 6.1 进程管理

- 使用 **systemd** 管理各服务进程（自动重启、开机自启）
- 或使用 **Docker Compose** 容器化部署（推荐，便于环境隔离）

### 6.2 目录结构

```
/opt/chinese-chess/
├── game-service/          # Python 统一 Game 服务
│   ├── main.py
│   ├── config.yaml
│   ├── auth/              # 认证模块
│   ├── user/              # 用户模块
│   ├── room/              # 房间 + 游戏模块
│   ├── match/             # 匹配模块
│   ├── chess/             # 棋盘引擎
│   ├── ai/                # AI 推理模块
│   ├── admin/             # 管理后台模块
│   ├── migrations/        # SQL 迁移脚本
│   └── requirements.txt
├── training/              # Python 训练服务
│   ├── selfplay.py
│   ├── train.py
│   └── models/            # 模型文件目录
├── web-service/           # [过渡期] 旧 Go Web 服务，验证后下线
├── data/
│   ├── postgres/
│   └── selfplay_games/
└── nginx.conf
```

---

## 七、技术选型汇总

| 模块 | 选型 | 理由 |
|---|---|---|
| Web 前端 | Vue 3 + Vite | 响应式、组件化、生态成熟 |
| **Game 服务（统一）** | Python + FastAPI + asyncio | AI 原生集成、异步高并发、统一技术栈 |
| AI 推理/训练 | Python + PyTorch | 强化学习标准技术栈 |
| 数据库 | PostgreSQL | 全功能关系型数据库 |
| 网络协议 | **WebSocket（统一）** | 实时双向、低延迟、统一通信模型 |
| 进程管理 | systemd / Docker Compose | 单机部署首选 |
| 消息队列 | 无（单机直连） | 单机部署无需额外队列 |

---

## 八、关键设计决策

### 决策 1：合并 Web 服务到 Game 服务（v2.0 新决策）

**理由**：
- **简化架构**：一个服务处理所有逻辑，无需服务间通信和回调
- **全 WebSocket 统一体验**：认证、房间、匹配、对局在同一个连接上完成，用户体验更流畅
- **消除服务间延迟**：不再需要 Web 服务调用 Game 服务的 HTTP 请求和回调
- **统一技术栈**：Python 全栈，AI 推理零网络开销
- **匹配即房间**：匹配成功后直接在内存中创建房间并开始对局，无需分配和跳转

**权衡**：
- Go 的 HTTP 性能优势放弃，但单机场景 Python + asyncio 完全够用
- 认证和业务逻辑耦合度增加，但通过模块化分层可保持代码清晰

### 决策 2：房间即游戏（v2.0 新决策）

**理由**：
- 房间是游戏过程的完整载体，从创建到结束的生命周期都在房间内
- 消除了 Web 服务"分配对局"→ Game 服务"创建房间"的跨服务环节
- 匹配创建的房间直接进入 Playing，无需准备阶段
- 手动创建的房间在对手加入后也直接进入 Playing（简化流程）

### 决策 3：AI 多难度通过 MCTS 模拟次数实现

**理由**：
- 只训练一个模型，部署和维护成本最低
- 不同难度使用不同模拟次数，简单直接
- 难度参数可动态调整，无需重新训练

### 决策 4：先传统 AI 后强化学习

**理由**：
- Phase 1：传统 Minimax + Alpha-Beta 剪枝，快速出可玩版本，验证整个系统
- Phase 2：当自我对弈积累足够数据后，用 AlphaZero 风格替换，逐步提升 AI 水平
- 降低初期复杂度，加快 MVP 交付

---

## 九、后续事项

- [ ] 评审并确认 v2.0 架构方案
- [ ] 完成 Game 服务详细设计文档更新（02-game-service-design.md）
- [ ] 完成 WebSocket 协议定义更新（04-shared-protocols.md）
- [ ] 制定旧 Web 服务 → 新 Game 服务的迁移计划
- [ ] 前端改造：从 HTTP REST + WebSocket 混合 → 纯 WebSocket 通信
- [ ] 规划新服务开发优先级和交付里程碑
