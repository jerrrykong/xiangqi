#!/bin/bash
# restart_game_server.sh — Restart the Game WebSocket server with tests

set -e

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

echo "=========================================="
echo "🔄  Restarting Game Server..."
echo "=========================================="

# Kill existing server on port 8081
echo "📦  Stopping existing server on port 8081..."
lsof -ti:8081 | xargs kill -9 2>/dev/null || true
sleep 1

# Run tests
echo "🧪  Running tests..."
/usr/bin/python3 -m pytest -x -q || {
    echo "❌  Tests failed!"
    exit 1
}

# Start server in background
echo "🚀  Starting Game server on port 8081..."
nohup /usr/bin/python3 -m uvicorn internal.game.websocket_server:app \
    --host 0.0.0.0 \
    --port 8081 \
    --log-level info \
    > game_server.log 2>&1 &

echo "✅  Server started (PID: $!)"
echo "📝  Log file: $PROJECT_DIR/game_server.log"
echo "=========================================="
echo "💡  To view logs: tail -f game_server.log"
echo "=========================================="
