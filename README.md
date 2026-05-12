# 中国象棋对战游戏 (XiangqiNet)

基于 Web 的中国象棋对战游戏，支持：

- 🆚 **人人对战 (PvP)**：玩家之间对战，带 ELO 积分匹配
- 🤖 **人机对战 (PvE)**：与 AI 对战，5 个难度等级
- 📊 **ELO 积分系统**：公平的积分计算与排行榜
- 🔄 **断线重连**：意外断开可重新连接继续对局

## 系统架构

```
┌─────────────┐     HTTP      ┌─────────────┐     HTTP Callback     ┌─────────────┐
│   Web 客户端  │◄────────────►│  Web 服务    │◄──────────────────►│  Game 服务   │
│  (浏览器)     │   WebSocket  │   (Go+Gin)   │                      │ (Python+FastAPI)│
└─────────────┘◄────────────►└─────────────┘                      └──────┬──────┘
                                                                        │
                                         ┌─────────────┐                 │
                                         │ AI 推理引擎  │◄────────────────┘
                                         │ (PyTorch)   │
                                         └─────────────┘
```

## 技术栈

- **Web 服务**: Go 1.21 + Gin + GORM + PostgreSQL + Redis
- **Game 服务**: Python 3.10 + FastAPI + asyncio + WebSocket
- **AI 引擎**: PyTorch 2.1 + AlphaZero 风格神经网络 + MCTS

## 快速开始

### 前置要求

- Go 1.21+
- Python 3.10+
- PostgreSQL 14+
- Redis 7+
- (可选) CUDA 12.1+ (用于 AI 训练)

### 安装

```bash
# 克隆仓库
git clone https://github.com/jerrykong/xiangqi.git
cd xiangqi

# 安装 Go 依赖
go mod download

# 安装 Python 依赖 (推荐使用 poetry)
poetry install

# 配置环境变量
cp .env.example .env
# 编辑 .env 填写数据库和 Redis 配置
```

### 运行

```bash
# 启动 Web 服务 (端口 8080)
go run cmd/web/main.go

# 启动 Game 服务 (端口 8081)
poetry run python -m cmd.game.main
```

## 目录结构

```
xiangqi/
├── cmd/                    # 服务入口
│   ├── web/               # Web 服务入口
│   ├── game/              # Game 服务入口
│   └── train/             # 训练服务入口
├── internal/              # 内部包
│   ├── chess/             # 核心棋类逻辑
│   ├── ai/                # AI 引擎
│   ├── game/              # Game 服务
│   └── web/               # Web 服务
├── shared/                # 共享协议和常量
├── pkg/                   # 公共包
├── proto/                 # Protobuf 定义
├── tests/                 # 测试
└── docs/                  # 设计文档
```

## 开发

### 运行测试

```bash
# Go 测试
go test ./...

# Python 测试
poetry run pytest

# 查看覆盖率
poetry run pytest --cov=internal --cov-report=html
```

### 代码规范

```bash
# Go 格式化
go fmt ./...

# Go lint
golangci-lint run

# Python 格式化
poetry run black .
poetry run isort .
poetry run mypy .
```

## 许可证

MIT License
