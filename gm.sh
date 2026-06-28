#!/usr/bin/env bash
# ============================================================
# gm.sh — Game Service Debug Tool
# 通过 /api/debug/trigger 端点调试超时、断线、DB异常等场景
#
# 使用前提：启动 game-service 时设置 GS_DEBUG_ENABLE=1
# 默认 API: http://localhost:8765
# ============================================================
set -euo pipefail

# ---- 配置 ----
API_BASE="${GM_API_BASE:-http://localhost:8765}"
DEBUG_URL="${API_BASE}/api/debug/trigger"
HEALTH_URL="${API_BASE}/health"

# ---- 颜色（用 $'...' 在赋值时解析转义，避免依赖 echo -e）----
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
BOLD=$'\033[1m'
NC=$'\033[0m' # No Color

# ---- 工具函数 ----

die() {
    printf '%s[ERROR]%s %s\n' "$RED" "$NC" "$*" >&2
    exit 1
}

info() {
    printf '%s[INFO]%s %s\n' "$GREEN" "$NC" "$*"
}

warn() {
    printf '%s[WARN]%s %s\n' "$YELLOW" "$NC" "$*"
}

api_call() {
    local action="$1"
    local payload="${2:-{}}"
    local endpoint="${DEBUG_URL}"

    # 如果传了完整 JSON，直接使用；否则构造 {"action":"...", ...extra}
    local body
    if echo "$payload" | python3 -c "import sys,json; json.loads(sys.stdin.read());" 2>/dev/null; then
        # payload 已经是有效 JSON
        if echo "$payload" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); exit(0 if 'action' in d else 1)" 2>/dev/null; then
            body="$payload"
        else
            body=$(echo "$payload" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); d['action']='$action'; print(json.dumps(d))")
        fi
    else
        # payload 是 key=value 对
        if [ -n "$payload" ] && [ "$payload" != "{}" ]; then
            # 用 python3 构建带 action 的 JSON
            body="{\"action\":\"$action\""
            IFS='&' read -ra PAIRS <<< "$payload"
            for pair in "${PAIRS[@]}"; do
                key="${pair%%=*}"
                val="${pair#*=}"
                # 判断 val 是数字还是字符串
                if [[ "$val" =~ ^[0-9]+$ ]]; then
                    body+=",\"$key\":$val"
                elif [ "$val" = "true" ] || [ "$val" = "false" ]; then
                    body+=",\"$key\":$val"
                else
                    body+=",\"$key\":\"$val\""
                fi
            done
            body+="}"
        else
            body="{\"action\":\"$action\"}"
        fi
    fi

    local resp
    resp=$(curl -sS -w "\n%{http_code}" -X POST "$endpoint" \
        -H "Content-Type: application/json" \
        -d "$body" 2>&1) || {
        warn "curl 请求失败，请确认 game-service 已启动且 GS_DEBUG_ENABLE=1"
        return 1
    }

    local http_code
    http_code=$(echo "$resp" | tail -1)
    local resp_body
    resp_body=$(echo "$resp" | sed '$d')

    if [ "$http_code" -eq 403 ]; then
        warn "Debug 未启用。请用 GS_DEBUG_ENABLE=1 启动 game-service"
        echo "$resp_body" | python3 -m json.tool 2>/dev/null || echo "$resp_body"
        return 1
    fi

    if [ "$http_code" -ge 400 ]; then
        warn "HTTP $http_code"
        echo "$resp_body" | python3 -m json.tool 2>/dev/null || echo "$resp_body"
        return 1
    fi

    echo "$resp_body" | python3 -m json.tool 2>/dev/null || echo "$resp_body"
}

check_health() {
    curl -sS "$HEALTH_URL" 2>/dev/null | python3 -m json.tool 2>/dev/null || {
        warn "无法连接 game-service ($API_BASE)"
        return 1
    }
}

# ---- 子命令实现 ----

cmd_help() {
    cat <<EOF
${BOLD}gm.sh — Game Service 调试工具${NC}

${CYAN}用法:${NC}  ./gm.sh <command> [args...]

${CYAN}命令列表:${NC}

  ${BOLD}help${NC}                         显示本帮助信息

  ${BOLD}health${NC}                       检查 game-service 健康状态

  ${BOLD}list-rooms${NC}                   列出所有活跃房间
                              (获取 room_id / user_id)

  ${BOLD}timeout${NC} <room_id> <red|black>
                              立即触发指定房间的走棋超时
                              例: ./gm.sh timeout abc123 red

  ${BOLD}disconnect${NC} <user_id>         模拟玩家断线
                              例: ./gm.sh disconnect 42

  ${BOLD}crash-save${NC} <on|off>         开启/关闭 DB 保存异常模拟
                              (下次 game_over 时在评分后抛异常)
                              例: ./gm.sh crash-save on

  ${BOLD}crash-save-status${NC}            查看当前 crash-save 状态
                              (通过搜索活跃房间判断)

${CYAN}环境变量:${NC}
  GM_API_BASE       API 地址 (默认: http://localhost:8765)
                    例: GM_API_BASE=http://192.168.1.100:8765 ./gm.sh list-rooms

${CYAN}前提条件:${NC}
  启动 game-service 时需设置 GS_DEBUG_ENABLE=1
  例: GS_DEBUG_ENABLE=1 python3 main.py

${CYAN}典型测试流程:${NC}
  1. ./gm.sh list-rooms                    # 获取 room_id
  2. ./gm.sh crash-save on                 # 开启 DB 异常模拟
  3. ./gm.sh timeout <room_id> red         # 触发红方超时 → 验证广播仍收到
  4. ./gm.sh crash-save off                # 关闭模拟
EOF
}

cmd_health() {
    check_health
}

cmd_list_rooms() {
    check_health > /dev/null || return 1
    info "获取活跃房间列表..."
    api_call "list_rooms"
}

cmd_timeout() {
    local room_id="${1:-}"
    local side="${2:-}"

    if [ -z "$room_id" ]; then
        die "用法: ./gm.sh timeout <room_id> <red|black>"
    fi
    if [ "$side" != "red" ] && [ "$side" != "black" ]; then
        die "side 必须是 'red' 或 'black'，当前值: '$side'"
    fi

    check_health > /dev/null || return 1
    warn "即将触发超时: room=$room_id, side=$side"
    read -r -p "确认执行? [y/N] " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        info "已取消"
        return 0
    fi

    info "触发超时..."
    api_call "force_timeout" "room_id=$room_id&side=$side"
}

cmd_disconnect() {
    local user_id="${1:-}"

    if [ -z "$user_id" ]; then
        die "用法: ./gm.sh disconnect <user_id>"
    fi

    check_health > /dev/null || return 1
    warn "即将断线: user_id=$user_id"
    info "执行中断开连接..."
    api_call "force_disconnect" "user_id=$user_id"
}

cmd_crash_save() {
    local action="${1:-}"

    case "$action" in
        on|enable|true|1)
            check_health > /dev/null || return 1
            info "开启 DB 保存异常模拟..."
            api_call "crash_save" "enable=true"
            ;;
        off|disable|false|0)
            check_health > /dev/null || return 1
            info "关闭 DB 保存异常模拟..."
            api_call "crash_save" "enable=false"
            ;;
        *)
            die "用法: ./gm.sh crash-save <on|off>"
            ;;
    esac
}

cmd_crash_save_status() {
    check_health > /dev/null || return 1
    info "crash_save 状态通过 server 内存维护，当前值请查看最近一次设置输出"
    info "或通过 list-rooms 结果判断（暂无独立查询端点）"
}

# ---- 主入口 ----

main() {
    local cmd="${1:-help}"
    shift || true

    case "$cmd" in
        help|-h|--help)
            cmd_help
            ;;
        health)
            cmd_health
            ;;
        list-rooms|list_rooms|rooms)
            cmd_list_rooms
            ;;
        timeout)
            cmd_timeout "$@"
            ;;
        disconnect)
            cmd_disconnect "$@"
            ;;
        crash-save|crash_save)
            cmd_crash_save "$@"
            ;;
        crash-save-status|crash_save_status)
            cmd_crash_save_status
            ;;
        *)
            printf '%s未知命令:%s %s\n' "$RED" "$NC" "$cmd"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
