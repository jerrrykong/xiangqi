#!/bin/bash
# Game Service v2.0 启动脚本
# 用法: ./start.sh          （开发模式，热重载）
#       ./start.sh prod      （生产模式，不重载）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
else
    echo "错误: 虚拟环境 .venv 不存在，请先运行: python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 读取 config.yaml 中的 host / port（降级到默认值）
HOST=$(python -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c['server']['host'])" 2>/dev/null || echo "0.0.0.0")
PORT=$(python -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c['server']['port'])" 2>/dev/null || echo "8765")

echo "Starting Game Service v2.0 on ${HOST}:${PORT}..."

if [ "$1" = "prod" ]; then
    uvicorn main:app --host "$HOST" --port "$PORT"
else
    uvicorn main:app --host "$HOST" --port "$PORT" --reload
fi
