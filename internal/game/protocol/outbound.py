"""Outbound WebSocket messages to clients."""
from enum import Enum
from typing import Any, Optional, List
import json


class OutboundMessageType(str, Enum):
    """Server -> Client message types."""

    # 连接/状态
    GAME_START = "game_start"        # 对局开始
    STATE_SYNC = "state_sync"        # 状态同步（断线重连）
    GAME_OVER = "game_over"          # 对局结束
    ERROR = "error"                  # 错误通知

    # 对局中
    MOVE_RESULT = "move_result"      # 着法结果（自己的着法）
    OPPONENT_MOVE = "opponent_move"  # 对手落子通知
    CHECK = "check"                  # 将军通知
    AI_THINKING = "ai_thinking"       # AI 正在思考
    AI_MOVE = "ai_move"              # AI 落子
    TIMEOUT_WARNING = "timeout_warning"  # 超时预警

    # 和棋
    DRAW_REQUEST = "draw_request"    # 收到和棋请求
    DRAW_ANSWERED = "draw_answered"  # 和棋应答通知
    DRAW_RESULT = "draw_result"      # 和棋结果

    # 断线
    OPPONENT_LEFT = "opponent_left"  # 对手断线
    OPPONENT_REJOIN = "opponent_rejoin"  # 对手重连

    # 心跳
    PONG = "pong"                    # 心跳响应

    # 聊天
    CHAT = "chat"                    # 聊天消息


def error_message(code: int, message: str) -> dict:
    """Create an error message."""
    return {
        "type": OutboundMessageType.ERROR.value,
        "data": {"code": code, "message": message},
    }


def game_start_message(
    room_id: str,
    your_side: str,  # "red" or "black"
    red_time: int = 600,
    black_time: int = 600,
) -> dict:
    """Create a game start message."""
    return {
        "type": OutboundMessageType.GAME_START.value,
        "data": {
            "room_id": room_id,
            "your_side": your_side,
            "red_time": red_time,
            "black_time": black_time,
        },
    }


def state_sync_message(
    room_id: str,
    board: List[List[int]],
    turn: str,  # "red" or "black"
    move_no: int,
    red_time: int,
    black_time: int,
    your_side: str,
) -> dict:
    """Create a state sync message (for reconnection)."""
    return {
        "type": OutboundMessageType.STATE_SYNC.value,
        "data": {
            "room_id": room_id,
            "board": board,
            "turn": turn,
            "move_no": move_no,
            "red_time": red_time,
            "black_time": black_time,
            "your_side": your_side,
        },
    }


def move_result_message(
    player: str,  # "red" or "black"
    from_pos: str,
    to_pos: str,
    captured: int,  # 0 if no capture, else piece code
    check: bool,
    red_time: int,
    black_time: int,
) -> dict:
    """Create a move result message."""
    return {
        "type": OutboundMessageType.MOVE_RESULT.value,
        "data": {
            "player": player,
            "from": from_pos,
            "to": to_pos,
            "captured": captured,
            "check": check,
            "red_time": red_time,
            "black_time": black_time,
        },
    }


def opponent_move_message(
    player: str,
    from_pos: str,
    to_pos: str,
    captured: int,
    check: bool,
) -> dict:
    """Create an opponent move message."""
    return {
        "type": OutboundMessageType.OPPONENT_MOVE.value,
        "data": {
            "player": player,
            "from": from_pos,
            "to": to_pos,
            "captured": captured,
            "check": check,
        },
    }


def game_over_message(
    winner: str,  # "red", "black", or "none"
    result: str,
    reason: str,
) -> dict:
    """Create a game over message."""
    return {
        "type": OutboundMessageType.GAME_OVER.value,
        "data": {
            "winner": winner,
            "result": result,
            "reason": reason,
        },
    }


def check_message(
    by_piece: str,
    from_pos: str,
    to_pos: str,
) -> dict:
    """Create a check (将军) message."""
    return {
        "type": OutboundMessageType.CHECK.value,
        "data": {
            "by_piece": by_piece,
            "from": from_pos,
            "to": to_pos,
        },
    }


def opponent_left_message(
    reason: str = "disconnect",
    timeout: int = 60,
) -> dict:
    """Create an opponent left message."""
    return {
        "type": OutboundMessageType.OPPONENT_LEFT.value,
        "data": {
            "reason": reason,
            "timeout": timeout,
        },
    }


def opponent_rejoin_message(username: str) -> dict:
    """Create an opponent rejoin message."""
    return {
        "type": OutboundMessageType.OPPONENT_REJOIN.value,
        "data": {"username": username},
    }


def draw_request_message(from_side: str) -> dict:
    """Create a draw request message."""
    return {
        "type": OutboundMessageType.DRAW_REQUEST.value,
        "data": {"from": from_side},
    }


def draw_answered_message(from_side: str, accept: bool) -> dict:
    """Create a draw answered message."""
    return {
        "type": OutboundMessageType.DRAW_ANSWERED.value,
        "data": {"from": from_side, "accept": accept},
    }


def ai_thinking_message() -> dict:
    """Create an AI thinking message."""
    return {
        "type": OutboundMessageType.AI_THINKING.value,
        "data": {},
    }


def ai_move_message(from_pos: str, to_pos: str, captured: int) -> dict:
    """Create an AI move message."""
    return {
        "type": OutboundMessageType.AI_MOVE.value,
        "data": {
            "from": from_pos,
            "to": to_pos,
            "captured": captured,
        },
    }


def timeout_warning_message(remaining: int) -> dict:
    """Create a timeout warning message."""
    return {
        "type": OutboundMessageType.TIMEOUT_WARNING.value,
        "data": {"remaining": remaining},
    }


def pong_message() -> dict:
    """Create a pong response."""
    return {
        "type": OutboundMessageType.PONG.value,
        "data": {},
    }


def chat_message(from_side: str, content: str) -> dict:
    """Create a chat message."""
    return {
        "type": OutboundMessageType.CHAT.value,
        "data": {"from": from_side, "content": content},
    }
