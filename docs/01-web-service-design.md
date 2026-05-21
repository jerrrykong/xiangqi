# Web 服务详细设计（Go）

> 服务职责：用户认证、房间管理、ELO 匹配、管理后台、对局分配
> 技术栈：Go + Gin + GORM + Redis + PostgreSQL
> 文档版本：v1.0

---

## 一、项目结构

```
web-service/
├── cmd/
│   └── server/
│       └── main.go              # 程序入口
├── config/
│   └── config.go                # 配置加载（YAML）
├── internal/
│   ├── handler/                 # HTTP Handler
│   │   ├── auth.go             # 认证接口
│   │   ├── user.go            # 用户接口
│   │   ├── room.go            # 房间接口
│   │   ├── match.go           # 匹配接口
│   │   └── admin.go           # 管理后台接口
│   ├── middleware/             # 中间件
│   │   ├── auth.go           # JWT 认证
│   │   ├── ratelimit.go      # 限流
│   │   ├── admin.go          # 管理员权限
│   │   └── logger.go         # 日志
│   ├── service/               # 业务逻辑层
│   │   ├── user.go           # UserService
│   │   ├── room.go           # RoomService
│   │   ├── match.go          # MatchService（ELO 匹配引擎）
│   │   ├── admin.go          # AdminService
│   │   └── game_proxy.go     # GameProxy（调用 Game 服务）
│   ├── model/                 # 数据模型
│   │   ├── user.go
│   │   ├── room.go
│   │   ├── elo.go
│   │   └── game.go
│   ├── repository/           # 数据访问层
│   │   ├── user.go
│   │   ├── room.go
│   │   ├── elo.go
│   │   └── game.go
│   └── pkg/
│       ├── response/         # 统一响应封装
│       ├── jwt/              # JWT 工具
│       ├── errors/           # 错误定义
│       └── redis/            # Redis 客户端
├── migrations/               # SQL 迁移脚本
│   ├── 001_init.sql
│   └── 002_elo_history.sql
├── config.yaml              # 配置文件
└── go.mod / go.sum
```

---

## 二、数据模型定义

### 2.1 User

```go
// internal/model/user.go
package model

import (
    "time"
)

type User struct {
    ID           int64      `json:"id" gorm:"primaryKey;autoIncrement"`
    Username     string     `json:"username" gorm:"type:varchar(32);uniqueIndex;not null"`
    PasswordHash string     `json:"-" gorm:"column:password_hash;type:varchar(255);not null"`
    Nickname     string     `json:"nickname" gorm:"type:varchar(64)"`
    Avatar       string     `json:"avatar" gorm:"type:varchar(255)"`  // 头像 URL
    IsAdmin      bool       `json:"is_admin" gorm:"default:false"`
    IsBanned     bool       `json:"is_banned" gorm:"default:false"`
    CreatedAt    time.Time  `json:"created_at" gorm:"autoCreateTime"`
    UpdatedAt    time.Time  `json:"updated_at" gorm:"autoUpdateTime"`
    LastLoginAt  *time.Time `json:"last_login_at"`
}

func (User) TableName() string {
    return "users"
}
```

### 2.2 EloRating

```go
// internal/model/elo.go
package model

import "time"

type EloRating struct {
    UserID     int64     `json:"user_id" gorm:"primaryKey"`
    Rating     int       `json:"rating" gorm:"default:1500"`
    GamesCount int       `json:"games_count" gorm:"default:0"`
    UpdatedAt  time.Time `json:"updated_at" gorm:"autoUpdateTime"`
    User       *User     `json:"user,omitempty" gorm:"foreignKey:UserID"`
}

func (EloRating) TableName() string {
    return "elo_ratings"
}
```

### 2.3 Room

```go
// internal/model/room.go
package model

import (
    "database/sql"
    "time"
)

// RoomType 对局类型
type RoomType string

const (
    RoomTypePvP  RoomType = "pvp"  // 人人对战
    RoomTypePvE  RoomType = "pve"  // 人机对战
)

// RoomStatus 房间状态
type RoomStatus string

const (
    RoomStatusWaiting  RoomStatus = "waiting"  // 等待玩家加入
    RoomStatusReady   RoomStatus = "ready"    // 玩家已就绪
    RoomStatusPlaying RoomStatus = "playing"  // 对局中
    RoomStatusFinished RoomStatus = "finished" // 已结束
)

type Room struct {
    ID            string         `json:"id" gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
    Type         RoomType      `json:"type" gorm:"type:varchar(8);not null"`
    Status       RoomStatus     `json:"status" gorm:"type:varchar(16);not null;default:'waiting'"`
    Difficulty   sql.NullInt32  `json:"difficulty,omitempty" gorm:"type:int"` // PvE 难度
    RedUserID    sql.NullInt64  `json:"red_user_id,omitempty" gorm:"type:bigint"`
    BlackUserID  sql.NullInt64  `json:"black_user_id,omitempty" gorm:"type:bigint"`
    RedReady     bool           `json:"red_ready" gorm:"default:false"`
    BlackReady   bool           `json:"black_ready" gorm:"default:false"`
    Winner       sql.NullString `json:"winner,omitempty" gorm:"type:varchar(8)"`
    GameID       sql.NullString `json:"game_id,omitempty" gorm:"type:uuid"`  // Game 服务分配的对局 ID
    CreatedBy    int64          `json:"created_by" gorm:"type:bigint;not null"`
    CreatedAt    time.Time      `json:"created_at" gorm:"autoCreateTime"`
    StartedAt    *time.Time     `json:"started_at,omitempty"`
    EndedAt      *time.Time     `json:"ended_at,omitempty"`
}

func (Room) TableName() string {
    return "rooms"
}
```

### 2.4 GameHistory

```go
// internal/model/game.go
package model

type GameHistory struct {
    ID         int64     `json:"id" gorm:"primaryKey;autoIncrement"`
    RoomID     string    `json:"room_id" gorm:"type:uuid;not null;index"`
    Winner     string    `json:"winner" gorm:"type:varchar(8);not null"` // red/black/draw
    Result     int       `json:"result" gorm:"type:int;not null"`        // 见 GameResult 枚举
    TotalMoves int       `json:"total_moves" gorm:"not null"`
    StartTime  time.Time `json:"start_time" gorm:"not null"`
    EndTime    time.Time `json:"end_time" gorm:"not null"`
    PvELevel   *int      `json:"pve_level,omitempty" gorm:"type:int"`   // PvE 难度
    RedUserID  int64     `json:"red_user_id" gorm:"type:bigint"`
    BlackUserID int64    `json:"black_user_id" gorm:"type:bigint"`
}

func (GameHistory) TableName() string {
    return "game_history"
}
```

### 2.5 EloHistory

```go
// internal/model/elo.go
type EloHistory struct {
    ID        int64     `json:"id" gorm:"primaryKey;autoIncrement"`
    UserID    int64     `json:"user_id" gorm:"type:bigint;not null;index"`
    Rating    int       `json:"rating" gorm:"not null"`
    Change    int       `json:"change" gorm:"not null"`        // 本局积分变化（+10/-15）
    GameID    int64     `json:"game_id" gorm:"type:bigint"`    // 可选
    CreatedAt time.Time `json:"created_at" gorm:"autoCreateTime"`
}

func (EloHistory) TableName() string {
    return "elo_history"
}
```

### 2.6 ModelVersion（AI 模型版本）

```go
// internal/model/ai.go
package model

import "time"

type ModelStatus string

const (
    ModelStatusTraining   ModelStatus = "training"
    ModelStatusValidating ModelStatus = "validating"
    ModelStatusOnline     ModelStatus = "online"
    ModelStatusArchived   ModelStatus = "archived"
)

type ModelVersion struct {
    ID         int64       `json:"id" gorm:"primaryKey;autoIncrement"`
    Version    string      `json:"version" gorm:"type:varchar(32);uniqueIndex;not null"`
    ModelPath  string      `json:"model_path" gorm:"type:varchar(255);not null"`
    EloScore   *int        `json:"elo_score,omitempty" gorm:"type:int"` // 对比验证结果
    Status     ModelStatus `json:"status" gorm:"type:varchar(16);not null;default:'training'"`
    Note       string      `json:"note,omitempty" gorm:"type:text"`
    CreatedAt  time.Time   `json:"created_at" gorm:"autoCreateTime"`
}

func (ModelVersion) TableName() string {
    return "model_versions"
}
```

---

## 三、统一响应封装

### 3.1 响应结构

```go
// internal/pkg/response/response.go
package response

type Response struct {
    Code    int         `json:"code"`
    Message string      `json:"message"`
    Data    interface{} `json:"data,omitempty"`
}

// 成功响应
func OK(c *gin.Context, data interface{}) {
    c.JSON(http.StatusOK, Response{Code: 0, Message: "ok", Data: data})
}

// 失败响应
func Fail(c *gin.Context, httpStatus int, code int, message string) {
    c.JSON(httpStatus, Response{Code: code, Message: message, Data: nil})
}

// 常用快捷方法
func Unauthorized(c *gin.Context) {
    Fail(c, http.StatusUnauthorized, 1004, "unauthorized")
}

func BadRequest(c *gin.Context, msg string) {
    Fail(c, http.StatusBadRequest, 1003, msg)
}

func NotFound(c *gin.Context, msg string) {
    Fail(c, http.StatusNotFound, 3001, msg)
}

func InternalError(c *gin.Context) {
    Fail(c, http.StatusInternalServerError, 1000, "system error")
}
```

---

## 四、API 接口定义

### 4.1 认证模块

#### POST /auth/register — 用户注册

**请求体：**
```json
{
  "username": "player1",
  "password": "SecurePass123",
  "nickname": "象棋新手"
}
```

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user_id": 1,
    "username": "player1",
    "nickname": "象棋新手",
    "rating": 1500,
    "games_count": 0
  }
}
```

**验证规则：**
- `username`: 4~32 字符，字母/数字/下划线，不可重复
- `password`: 最少 8 字符，需包含字母和数字
- `nickname`: 1~64 字符，不允许空

---

#### POST /auth/login — 用户登录

**请求体：**
```json
{
  "username": "player1",
  "password": "SecurePass123"
}
```

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user_id": 1,
    "username": "player1",
    "nickname": "象棋新手",
    "rating": 1500,
    "games_count": 0,
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_at": "2026-05-13T22:00:00Z"
  }
}
```

---

#### POST /auth/refresh — 刷新 Token

**请求头：** `Authorization: Bearer {token}`

**响应：** 同登录

---

### 4.2 用户模块

#### GET /users/me — 当前用户信息

**请求头：** `Authorization: Bearer {token}`

**响应：**
```json
{
  "code": 0,
  "message": "ok",
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

---

#### PATCH /users/me — 修改个人信息

**请求体（可选字段）：**
```json
{
  "nickname": "象棋大师",
  "avatar": "https://..."
}
```

---

#### GET /users/rankings — 积分排行榜

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页数量（最大 100） |

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total": 1234,
    "page": 1,
    "page_size": 20,
    "rankings": [
      { "rank": 1, "user_id": 5, "username": "master", "rating": 2100, "games_count": 500 },
      { "rank": 2, "user_id": 8, "username": "pro", "rating": 2050, "games_count": 300 }
    ]
  }
}
```

---

#### GET /users/:id/history — 用户战绩

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页数量 |
| `type` | string | "" | 筛选：pvp/pve |

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total": 50,
    "history": [
      {
        "game_id": "uuid",
        "result": "win",
        "my_side": "red",
        "opponent": { "user_id": 2, "username": "player2", "rating": 1550 },
        "rating_change": +15,
        "total_moves": 82,
        "played_at": "2026-05-12T14:00:00Z"
      }
    ]
  }
}
```

---

### 4.3 房间模块

#### POST /rooms — 创建房间（人人对战）

**请求头：** `Authorization: Bearer {token}`

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "room_id": "uuid",
    "room_type": "pvp",
    "status": "waiting",
    "created_at": "2026-05-12T14:00:00Z"
  }
}
```

**业务规则：**
- 用户已在房间中（waiting/playing）则返回 3004 错误
- 创建后自动成为红方（先手）

---

#### GET /rooms — 获取等待中的房间列表

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页数量 |

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "rooms": [
      {
        "room_id": "uuid",
        "created_by": 2,
        "username": "player2",
        "created_at": "2026-05-12T14:00:00Z"
      }
    ]
  }
}
```

---

#### POST /rooms/:id/join — 加入房间

**请求头：** `Authorization: Bearer {token}`

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "room_id": "uuid",
    "your_side": "black",
    "opponent": { "user_id": 2, "username": "player2" },
    "status": "ready"
  }
}
```

**业务规则：**
- 房间不存在 → 3001
- 房间已满（已有两名玩家）→ 3002
- 房间不在 waiting 状态 → 3003
- 不能加入自己创建的房间

---

#### POST /rooms/:id/ready — 玩家准备

**请求头：** `Authorization: Bearer {token}`

**说明：** 两人都 ready 后，Web 服务调用 Game 服务分配对局

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "room_id": "uuid",
    "red_ready": true,
    "black_ready": true,
    "game_started": true,
    "game_ws_url": "ws://game-service:8081/game/uuid",
    "game_token": "session-token-for-reconnect"
  }
}
```

---

#### DELETE /rooms/:id — 解散房间

**说明：** 仅房主可解散，房间必须处于 waiting 状态

---

### 4.4 匹配模块

#### POST /match/pvp — 加入 ELO 匹配队列

**请求头：** `Authorization: Bearer {token}`

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "queued",
    "queue_id": "uuid",
    "estimated_wait": 30
  }
}
```

**匹配成功后推送（WebSocket）：**
```json
{
  "type": "match_found",
  "data": {
    "room_id": "uuid",
    "opponent": { "user_id": 2, "username": "player2", "rating": 1520 },
    "your_side": "red",
    "game_ws_url": "ws://game-service:8081/game/uuid",
    "game_token": "session-token"
  }
}
```

**ELO 匹配算法（MatchService）：**
```
1. 玩家 ELO < 1200（games_count < 5）：允许差值 200 以内
2. 玩家 ELO 1200~1800：允许差值 100 以内
3. 玩家 ELO > 1800：允许差值 150 以内
4. 等待超时 60s：逐步放宽阈值（+50/30s）
5. 等待超时 180s：返回 3010 错误
```

---

#### POST /match/pve/:level — 开始人机对战

**路径参数：**
- `level`: 1~5，对应入门/简单/中等/困难/大师

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "room_id": "uuid",
    "difficulty": 3,
    "game_ws_url": "ws://game-service:8081/game/uuid",
    "game_token": "session-token",
    "your_side": "red"
  }
}
```

---

#### DELETE /match/pvp — 退出匹配队列

**说明：** 从 Redis 匹配队列中移除玩家

---

### 4.5 管理后台模块

#### GET /admin/users — 用户列表

**查询参数：** `page`, `page_size`, `search`（用户名搜索）, `banned`（筛选封禁用户）

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total": 5000,
    "users": [
      {
        "user_id": 1,
        "username": "player1",
        "rating": 1500,
        "games_count": 20,
        "is_banned": false,
        "created_at": "2026-05-01T10:00:00Z"
      }
    ]
  }
}
```

---

#### PATCH /admin/users/:id/ban — 封禁/解封用户

**请求体：**
```json
{ "banned": true, "reason": "使用外挂" }
```

---

#### GET /admin/stats — 全局运营数据

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total_users": 5000,
    "total_games": 50000,
    "today_games": 120,
    "online_users": 45,
    "avg_wait_time_seconds": 35,
    "ai_elo_rating": 2800
  }
}
```

---

#### POST /admin/models/upload — 上传新 AI 模型

**请求：** Multipart 表单上传 `.pt` 模型文件

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "model_id": 5,
    "version": "v1.2.3",
    "status": "training"
  }
}
```

---

#### PATCH /admin/models/:id/publish — 发布模型

**说明：** 将模型状态从 validating 改为 online，热更新 AI 推理服务

---

#### GET /admin/models — 模型列表

**响应：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "models": [
      { "id": 5, "version": "v1.2.3", "status": "online", "elo_score": 2850, "created_at": "..." },
      { "id": 4, "version": "v1.2.2", "status": "archived", "elo_score": 2800, "created_at": "..." }
    ]
  }
}
```

---

## 五、核心服务设计

### 5.1 UserService

```go
// internal/service/user.go
type UserService struct {
    repo *repository.UserRepository
    jwt  *jwt.JWTManager
}

func (s *UserService) Register(ctx context.Context, req *RegisterReq) (*User, error)
func (s *UserService) Login(ctx context.Context, req *LoginReq) (*LoginResp, error)
func (s *UserService) GetUser(ctx context.Context, userID int64) (*UserProfile, error)
func (s *UserService) UpdateProfile(ctx context.Context, userID int64, req *UpdateProfileReq) error
func (s *UserService) GetRankings(ctx context.Context, page, pageSize int) (*RankingsResp, error)
func (s *UserService) GetHistory(ctx context.Context, userID int64, req *HistoryReq) (*HistoryResp, error)
```

**Register 流程：**
```
1. 验证 username 唯一性（DB 查询）
2. 验证密码格式（8+ 字符，字母+数字）
3. bcrypt.hash(password) → password_hash
4. DB Insert User → 获得 user_id
5. DB Insert EloRating{ rating=1500, games_count=0 }
6. 返回 UserProfile
```

**Login 流程：**
```
1. DB 查询 User（username）
2. bcrypt.CompareHashAndPassword(password_hash, password)
3. 生成 JWT token（Claims: user_id, username, is_admin, exp=24h）
4. 更新 last_login_at
5. DB 查询 EloRating → rating, games_count
6. 返回 LoginResp{token, user_profile}
```

---

### 5.2 RoomService

```go
// internal/service/room.go
type RoomService struct {
    repo      *repository.RoomRepository
    gameProxy *GameProxy
    redis     *redis.Client
}

func (s *RoomService) CreateRoom(ctx context.Context, userID int64) (*Room, error)
func (s *RoomService) GetWaitingRooms(ctx context.Context, page, pageSize int) ([]RoomListItem, error)
func (s *RoomService) JoinRoom(ctx context.Context, roomID string, userID int64) (*JoinRoomResp, error)
func (s *RoomService) PlayerReady(ctx context.Context, roomID string, userID int64) (*ReadyResp, error)
func (s *RoomService) LeaveRoom(ctx context.Context, roomID string, userID int64) error
func (s *RoomService) DeleteRoom(ctx context.Context, roomID string, userID int64) error
func (s *RoomService) GetUserCurrentRoom(ctx context.Context, userID int64) (*Room, error)
```

**PlayerReady 核心流程：**
```
1. DB 查询 Room（验证存在、状态=waiting）
2. DB 更新 red_ready / black_ready
3. 如果双方都已 ready：
   a. DB 更新 room.status = "playing"
   b. 调用 gameProxy.AssignGame(room) → 获取 game_ws_url
   c. DB 更新 room.game_id
   d. 生成 session_token（用于断线重连）
4. 返回 ReadyResp{game_started, game_ws_url, game_token}
```

---

### 5.3 MatchService（ELO 匹配引擎）

```go
// internal/service/match.go
type MatchService struct {
    redis       *redis.Client
    roomService *RoomService
    gameProxy   *GameProxy
    eloService  *EloService
}

// 内部 goroutine 定期扫描匹配队列
func (s *MatchService) StartMatchLoop(ctx context.Context)
func (s *MatchService) JoinQueue(ctx context.Context, userID int64) (*QueueResp, error)
func (s *MatchService) LeaveQueue(ctx context.Context, userID int64) error
func (s *MatchService) findAndMatch()  // 每 2s 执行一次
```

**匹配循环（goroutine，后台运行）：**
```go
func (s *MatchService) StartMatchLoop(ctx context.Context) {
    ticker := time.NewTicker(2 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            s.findAndMatch()
        }
    }
}

func (s *MatchService) findAndMatch() {
    // 1. 从 Redis Sorted Set 读取所有等待玩家
    // 2. 按 ELO 积分排序
    // 3. 贪心匹配：遍历玩家，找积分差值在阈值内的另一玩家
    // 4. 匹配成功后：
    //    a. 从队列移除两人
    //    b. 调用 roomService.CreateRoom → room
    //    c. 更新房间玩家信息（red/black）
    //    d. 调用 gameProxy.AssignGame
    //    e. WebSocket 通知双方（match_found）
}
```

---

### 5.4 EloService

```go
// internal/service/elo.go
type EloService struct {
    repo *repository.EloRepository
    db   *gorm.DB
}

// CalculateElo 经典 ELO 公式
// K-factor：< 30 局 = 40，30~100 局 = 20，> 100 局 = 10
func (s *EloService) CalculateElo(rA, rB int, result float32) (changeA, changeB int) {
    K := 40 // 默认
    if gamesA := s.getGamesCount(rA); gamesA > 100 {
        K = 10
    } else if gamesA > 30 {
        K = 20
    }

    EA := 1.0 / (1.0 + math.Pow(10, float64(rB-rA)/400))
    changeA = int(K * (float32(result) - EA))

    EB := 1.0 / (1.0 + math.Pow(10, float64(rA-rB)/400))
    changeB = int(K * ((1.0 - float32(result)) - EB))
    return
}

// result: 胜=1.0, 负=0.0, 和=0.5
```

---

### 5.5 GameProxy（调用 Game 服务）

```go
// internal/service/game_proxy.go
type GameProxy struct {
    client  *http.Client
    baseURL string   // Game 服务地址
    secret  string   // Internal secret key
}

type AssignRequest struct {
    RoomID      string          `json:"room_id"`
    GameType    string          `json:"game_type"` // "pvp" / "pve"
    Players     []PlayerInfo    `json:"players"`
    Difficulty  *int            `json:"difficulty,omitempty"`
    CallbackURL string          `json:"callback_url"`
}

type PlayerInfo struct {
    UserID     int64  `json:"user_id"`
    Username   string `json:"username"`
    Side       string `json:"side"` // "red" / "black"
    WSSession  string `json:"ws_session"`
}

type AssignResponse struct {
    RoomID   string `json:"room_id"`
    WsURL    string `json:"ws_url"`    // WebSocket 连接地址
    GameID   string `json:"game_id"`
    SessionToken string `json:"session_token"` // 断线重连用
}

func (p *GameProxy) AssignGame(ctx context.Context, req *AssignRequest) (*AssignResponse, error)
func (p *GameProxy) GetGameState(ctx context.Context, gameID string) (*GameState, error)

// 处理 Game 服务回调（HTTP POST）
func (p *GameProxy) HandleGameResult(c *gin.Context)
```

**对局结束回调处理流程：**
```
POST /internal/game/result
1. 验证 X-Internal-Key
2. 解析 GameResultRequest
3. 写入 game_history
4. 调用 eloService.CalculateElo → 积分变化
5. 更新 elo_ratings 表
6. 写入 elo_history
7. 清理 Redis 房间缓存
8. 返回 200 OK
```

---

## 六、中间件设计

### 6.1 JWT 认证中间件

```go
// internal/middleware/auth.go
func JWTAuth() gin.HandlerFunc {
    return func(c *gin.Context) {
        authHeader := c.GetHeader("Authorization")
        if authHeader == "" {
            response.Unauthorized(c)
            c.Abort()
            return
        }

        parts := strings.SplitN(authHeader, " ", 2)
        if len(parts) != 2 || parts[0] != "Bearer" {
            response.Fail(c, http.StatusUnauthorized, 1004, "invalid token format")
            c.Abort()
            return
        }

        claims, err := jwtManager.ParseToken(parts[1])
        if err != nil {
            if errors.Is(err, jwt.ErrTokenExpired) {
                response.Fail(c, http.StatusUnauthorized, 2004, "token expired")
            } else {
                response.Fail(c, http.StatusUnauthorized, 2005, "token invalid")
            }
            c.Abort()
            return
        }

        // 注入上下文
        c.Set("user_id", claims.UserID)
        c.Set("username", claims.Username)
        c.Set("is_admin", claims.IsAdmin)
        c.Next()
    }
}
```

### 6.2 限流中间件（Redis + Token Bucket）

```go
// internal/middleware/ratelimit.go
func RateLimit(redis *redis.Client, maxReq int, window time.Duration) gin.HandlerFunc {
    return func(c *gin.Context) {
        key := fmt.Sprintf("ratelimit:%s:%s", c.ClientIP(), c.FullPath())
        count, err := redis.Incr(c.Request.Context(), key).Result()
        if err != nil {
            c.Next() // Redis 故障时放行
            return
        }

        if count == 1 {
            redis.Expire(c.Request.Context(), key, window)
        }

        if count > int64(maxReq) {
            response.Fail(c, http.StatusTooManyRequests, 1002, "rate limit exceeded")
            c.Abort()
            return
        }
        c.Next()
    }
}

// 使用示例：
// 公开接口：RateLimit(redis, 60, time.Minute)      // 60次/分钟
// 认证接口：RateLimit(redis, 300, time.Minute)     // 300次/分钟
// 登录接口：RateLimit(redis, 10, time.Minute)      // 10次/分钟
```

### 6.3 管理员权限中间件

```go
// internal/middleware/admin.go
func AdminOnly() gin.HandlerFunc {
    return func(c *gin.Context) {
        isAdmin, exists := c.Get("is_admin")
        if !exists || !isAdmin.(bool) {
            response.Fail(c, http.StatusForbidden, 1005, "forbidden")
            c.Abort()
            return
        }
        c.Next()
    }
}
```

### 6.4 Gin 路由注册

```go
// cmd/server/main.go
func setupRouter(srv *Server) *gin.Engine {
    r := gin.Default()

    // 公开接口
    public := r.Group("/auth")
    public.Use(RateLimit(redis, 10, time.Minute)) // 登录限流
    {
        public.POST("/register", h.AuthHandler.Register)
        public.POST("/login",    h.AuthHandler.Login)
    }

    // 需认证的接口
    auth := r.Group("")
    auth.Use(JWTAuth())
    auth.Use(RateLimit(redis, 300, time.Minute))
    {
        auth.POST("/auth/refresh", h.AuthHandler.Refresh)

        user := auth.Group("/users")
        {
            user.GET("/me", h.UserHandler.GetMe)
            user.PATCH("/me", h.UserHandler.UpdateProfile)
            user.GET("/rankings", h.UserHandler.GetRankings)
            user.GET("/users/:id/history", h.UserHandler.GetHistory)
        }

        room := auth.Group("/rooms")
        {
            room.POST("",       h.RoomHandler.CreateRoom)
            room.GET("",        h.RoomHandler.ListRooms)
            room.POST("/:id/join",  h.RoomHandler.JoinRoom)
            room.POST("/:id/ready", h.RoomHandler.PlayerReady)
            room.DELETE("/:id",     h.RoomHandler.DeleteRoom)
        }

        match := auth.Group("/match")
        {
            match.POST("/pvp",          h.MatchHandler.JoinPvP)
            match.POST("/pve/:level",  h.MatchHandler.JoinPvE)
            match.DELETE("/pvp",       h.MatchHandler.LeavePvP)
        }
    }

    // 管理后台接口
    admin := r.Group("/admin")
    admin.Use(JWTAuth(), AdminOnly())
    {
        admin.GET("/users",       h.AdminHandler.ListUsers)
        admin.PATCH("/users/:id/ban", h.AdminHandler.BanUser)
        admin.GET("/stats",       h.AdminHandler.GetStats)
        admin.POST("/models/upload",    h.AdminHandler.UploadModel)
        admin.PATCH("/models/:id/publish", h.AdminHandler.PublishModel)
        admin.GET("/models",      h.AdminHandler.ListModels)
    }

    // 内部回调接口（Game 服务回调）
    internal := r.Group("/internal")
    internal.Use(InternalAuth()) // X-Internal-Key 验证
    {
        internal.POST("/game/result", h.GameProxy.HandleGameResult)
    }

    return r
}
```

---

## 七、配置结构

```go
// config/config.go
type Config struct {
    Server   ServerConfig
    Database DatabaseConfig
    Redis    RedisConfig
    JWT      JWTConfig
    Internal InternalConfig
    GameService GameServiceConfig
}

type ServerConfig struct {
    Host string `yaml:"host"`
    Port int    `yaml:"port"`
}

type DatabaseConfig struct {
    Host     string `yaml:"host"`
    Port     int    `yaml:"port"`
    User     string `yaml:"user"`
    Password string `yaml:"password"`
    DBName   string `yaml:"dbname"`
    MaxOpen  int    `yaml:"max_open_conns"`
    MaxIdle  int    `yaml:"max_idle_conns"`
}

type JWTConfig struct {
    Secret     string        `yaml:"secret"`
    ExpireHours int          `yaml:"expire_hours"`
}

type InternalConfig struct {
    Secret string `yaml:"secret"`
}

type GameServiceConfig struct {
    BaseURL string `yaml:"base_url"` // e.g. "http://game-service:8081"
}
```

**config.yaml 示例：**
```yaml
server:
  host: "0.0.0.0"
  port: 8080

database:
  host: "localhost"
  port: 5432
  user: "postgres"
  password: "your_password"
  dbname: "chinese_chess"
  max_open_conns: 50
  max_idle_conns: 10

redis:
  host: "localhost"
  port: 6379
  password: ""
  db: 0

jwt:
  secret: "your-jwt-secret-change-in-production"
  expire_hours: 24

internal:
  secret: "internal-service-secret-key"

game_service:
  base_url: "http://localhost:8081"
```
